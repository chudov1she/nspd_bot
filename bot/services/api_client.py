"""
API клиент для работы с Росреестром через api-cloud.ru.
"""
import aiohttp
import asyncio
import random
from urllib.parse import urlencode
from typing import List, Optional, Dict, Any
from loguru import logger

from bot.config.settings import settings
from bot.models.cadastral import RealEstateObject


class APIError(Exception):
    """Базовое исключение для ошибок API."""
    pass


class APINotConfiguredError(APIError):
    """API ключ не настроен."""
    pass


class APIConnectionError(APIError):
    """Ошибка подключения к API."""
    pass


class APIResponseError(APIError):
    """Ошибка ответа от API."""
    def __init__(self, message: str, code: Optional[str] = None, status_code: Optional[int] = None):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


class RosreestrAPIClient:
    """Клиент для работы с API Росреестра через api-cloud.ru."""
    
    # URL API согласно документации
    ROSREESTR_API_URL = "https://api-cloud.ru/api/rosreestr.php"
    LK_API_URL = "https://api-cloud.ru/api/apilk.php"
    
    def __init__(self):
        self.api_key = settings.API_ROSREESTR_KEY
        # TIMEOUT минимум 120 секунд согласно документации
        timeout_seconds = max(settings.API_ROSREESTR_TIMEOUT, 120)
        self.timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Получить или создать сессию HTTP."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self.timeout)
        return self._session
    
    async def close(self):
        """Закрыть сессию HTTP."""
        if self._session and not self._session.closed:
            await self._session.close()
    
    def _check_api_key(self):
        """Проверяет наличие API ключа."""
        if not self.api_key:
            raise APINotConfiguredError(
                "API ключ не настроен. Установите переменную окружения API_ROSREESTR_KEY."
            )
    
    def _get_headers(self) -> Dict[str, str]:
        """
        Получить заголовки для запросов.
        Токен можно передавать в заголовке Token: согласно документации.
        """
        return {
            "Token": self.api_key,
        }
    
    async def get_cadastral_data(
        self, 
        cadastral_number: str
    ) -> RealEstateObject:
        """
        Получить данные по кадастровому номеру.
        
        Согласно документации:
        GET https://api-cloud.ru/api/rosreestr.php?type=object&cadastr={номер}&token={ключ}
        
        Args:
            cadastral_number: Кадастровый номер
            
        Returns:
            Объект RealEstateObject с данными
            
        Raises:
            APINotConfiguredError: Если API ключ не настроен
            APIConnectionError: Если ошибка подключения
            APIResponseError: Если ошибка ответа от API
        """
        # Режим симуляции - возвращаем тестовые данные
        if settings.API_SIMULATION_MODE:
            return await self._simulate_get_cadastral_data(cadastral_number)
        
        self._check_api_key()
        
        # Формируем параметры запроса
        params = {
            "type": "object",
            "cadastr": cadastral_number,
            "token": self.api_key,  # Можно передавать в параметрах или заголовке
        }
        
        headers = self._get_headers()
        
        try:
            session = await self._get_session()
            logger.debug(f"Запрос к API Росреестра для номера: {cadastral_number}")
            
            async with session.get(
                self.ROSREESTR_API_URL,
                params=params,
                headers=headers
            ) as response:
                response_data = await response.json()
                
                # Выводим полный ответ API в терминал для отладки
                import json
                print("\n" + "=" * 80)
                print(f"📡 ОТВЕТ API для кадастрового номера: {cadastral_number}")
                print("=" * 80)
                print(json.dumps(response_data, ensure_ascii=False, indent=2))
                print("=" * 80 + "\n")
                
                # Проверяем статус ответа
                status = response_data.get("status")
                
                if status == 200:
                    found = response_data.get("found", False)
                    
                    if found:
                        # Данные найдены
                        object_data = response_data.get("object", {})
                        inquiry = response_data.get("inquiry", {})
                        
                        # Извлекаем баланс из inquiry если есть
                        balance = inquiry.get("balance")
                        
                        return self._parse_response(cadastral_number, object_data, balance)
                    else:
                        # Данные не найдены, но запрос успешен
                        inquiry = response_data.get("inquiry", {})
                        balance = inquiry.get("balance")
                        
                        logger.warning(
                            f"Данные для кадастрового номера {cadastral_number} не найдены в API, пробуем получить с карты"
                        )
                        
                        # Пытаемся получить данные с карты
                        map_data = await self._try_get_data_from_map(cadastral_number)
                        if map_data:
                            logger.info(f"Данные для {cadastral_number} успешно получены с карты")
                            map_data.api_balance = balance
                            return map_data
                        
                        # Если не удалось получить с карты, возвращаем ошибку
                        return RealEstateObject(
                            cadastral_number=cadastral_number,
                            error="Данные не найдены",
                            error_code="NOT_FOUND",
                            api_balance=balance
                        )
                else:
                    # Ошибка API
                    error_code = response_data.get("error", "UNKNOWN_ERROR")
                    error_message = response_data.get("message", f"Ошибка API: {error_code}")
                    
                    logger.error(
                        f"Ошибка API для {cadastral_number}: {error_message} (код: {error_code})"
                    )
                    
                    # Извлекаем баланс если есть
                    inquiry = response_data.get("inquiry", {})
                    balance = inquiry.get("balance")
                    
                    return RealEstateObject(
                        cadastral_number=cadastral_number,
                        error=error_message,
                        error_code=str(error_code),
                        api_balance=balance
                    )
                    
        except aiohttp.ClientError as e:
            logger.error(f"Ошибка подключения к API для {cadastral_number}: {e}")
            raise APIConnectionError(f"Не удалось подключиться к API: {str(e)}") from e
        except Exception as e:
            logger.error(f"Неожиданная ошибка при запросе к API для {cadastral_number}: {e}")
            raise APIError(f"Ошибка при запросе к API: {str(e)}") from e
    
    async def get_cadastral_data_batch(
        self,
        cadastral_numbers: List[str]
    ) -> List[RealEstateObject]:
        """
        Получить данные по нескольким кадастровым номерам.
        
        Args:
            cadastral_numbers: Список кадастровых номеров
            
        Returns:
            Список объектов RealEstateObject
        """
        results = []
        
        for number in cadastral_numbers:
            try:
                result = await self.get_cadastral_data(number)
                results.append(result)
            except (APINotConfiguredError, APIConnectionError) as e:
                # Для критических ошибок создаем объект с ошибкой
                results.append(RealEstateObject(
                    cadastral_number=number,
                    error=str(e),
                    error_code="API_ERROR"
                ))
            except Exception as e:
                logger.error(f"Ошибка при получении данных для {number}: {e}")
                results.append(RealEstateObject(
                    cadastral_number=number,
                    error=f"Ошибка: {str(e)}",
                    error_code="UNKNOWN_ERROR"
                ))
        
        return results
    
    async def _try_get_data_from_map(self, cadastral_number: str) -> Optional[RealEstateObject]:
        """
        Пытается получить данные об объекте с карты nspd.gov.ru.
        
        Args:
            cadastral_number: Кадастровый номер
            
        Returns:
            RealEstateObject с данными или None если не удалось получить
        """
        try:
            from bot.services.map_generator import get_map_generator
            from bot.services.map_generator.data_extractor import MapDataExtractor
            from bot.services.map_generator.navigation import NavigationHandler
            from bot.services.map_generator.click_handler import ClickHandler
            from bot.services.map_generator.exceptions import MapGeneratorError, CadastralPlotNotFoundError
            
            logger.info(f"Попытка получить данные для {cadastral_number} с карты nspd.gov.ru")
            
            # Получаем генератор карт
            map_generator = get_map_generator()
            
            # Инициализируем браузер если нужно
            if map_generator._browser is None:
                await map_generator._init_browser()
            
            # Получаем страницу
            page = map_generator._page
            
            # Создаем обработчики
            navigation = NavigationHandler(page)
            click_handler = ClickHandler(page)
            data_extractor = MapDataExtractor(page)
            
            # Открываем страницу карты
            await navigation.open_map_page()
            
            # Ищем кадастровый номер
            await navigation.search_cadastral_number(cadastral_number)
            
            # Ждем результатов поиска
            await navigation.wait_for_search_results()
            
            # Кликаем на кнопку с кадастровым номером
            button_clicked = await click_handler.click_cadastral_button(cadastral_number)
            
            if not button_clicked:
                logger.warning(f"Не удалось найти кнопку для {cadastral_number} на карте")
                return None
            
            # Ждем загрузки карты и панели с информацией
            await navigation.wait_for_map_load()
            await asyncio.sleep(2)  # Дополнительное ожидание для загрузки данных
            
            # Извлекаем данные
            result = await data_extractor.extract_object_data(cadastral_number)
            
            if result:
                logger.info(f"Данные для {cadastral_number} успешно извлечены с карты")
                return result
            else:
                logger.warning(f"Не удалось извлечь данные для {cadastral_number} с карты")
                return None
                
        except (MapGeneratorError, CadastralPlotNotFoundError) as e:
            logger.warning(f"Ошибка при получении данных с карты для {cadastral_number}: {e}")
            return None
        except Exception as e:
            logger.error(f"Неожиданная ошибка при получении данных с карты для {cadastral_number}: {e}", exc_info=True)
            return None
    
    def _parse_response(
        self, 
        cadastral_number: str, 
        object_data: Dict[str, Any],
        balance: Optional[float] = None
    ) -> RealEstateObject:
        """
        Парсит ответ API в объект RealEstateObject.
        
        Согласно документации структура ответа:
        {
            "object": {
                "address": {...},
                "cadNumber": "...",
                "ObjectType": "...",
                "purpose": "...",
                "area": "...",
                "cadCost": "...",
                "land": {...},
                "permittedUse": [...],
                "rights": [...],
                "encumbrances": [...],
                ...
            }
        }
        """
        # Парсим адрес
        address_obj = object_data.get("address", {})
        readable_address = address_obj.get("readableAddress", "")
        
        # Парсим категорию земли (для земельных участков)
        land_obj = object_data.get("land", {})
        land_category = land_obj.get("landCategory")
        if land_category and land_category != "null":
            category = land_category
        else:
            category = None
        
        # Парсим разрешенное использование
        permitted_use_list = object_data.get("permittedUse", [])
        permitted_use_text = None
        if permitted_use_list:
            # Берем первый элемент и его transcript
            first_use = permitted_use_list[0] if isinstance(permitted_use_list, list) else None
            if first_use and isinstance(first_use, dict):
                permitted_use_text = first_use.get("transcript", "")
        
        # Парсим площадь
        area_str = object_data.get("area", "")
        area = None
        if area_str:
            try:
                area = float(area_str)
            except (ValueError, TypeError):
                pass
        
        # Если area не найдена, пробуем mainCharacters
        if area is None:
            main_chars = object_data.get("mainCharacters", {})
            if main_chars:
                area_value = main_chars.get("value")
                if area_value is not None:
                    try:
                        area = float(area_value)
                    except (ValueError, TypeError):
                        pass
        
        # Парсим кадастровую стоимость
        cad_cost_str = object_data.get("cadCost", "")
        cadastral_value = None
        if cad_cost_str:
            try:
                cadastral_value = float(cad_cost_str)
            except (ValueError, TypeError):
                pass
        
        # Парсим права
        rights_list = object_data.get("rights", [])
        rights_text = None
        if rights_list:
            rights_parts = []
            for right in rights_list:
                if isinstance(right, dict):
                    right_type = right.get("rightTypeDesc", "")
                    part = right.get("part")
                    if right_type:
                        if part:
                            rights_parts.append(f"{right_type} ({part})")
                        else:
                            rights_parts.append(right_type)
            if rights_parts:
                rights_text = "; ".join(rights_parts)
        
        # Парсим обременения
        encumbrances_list = object_data.get("encumbrances", [])
        encumbrances_text = None
        if encumbrances_list:
            encum_parts = []
            for encum in encumbrances_list:
                if isinstance(encum, dict):
                    encum_type = encum.get("typeDesc", "")
                    if encum_type:
                        encum_parts.append(encum_type)
            if encum_parts:
                encumbrances_text = "; ".join(encum_parts)
        
        # Статус объекта
        status = object_data.get("status", "")
        status_text = "Актуально" if status == "1" else "Не актуально" if status else None
        
        # Этаж
        level = object_data.get("level", "")
        level_text = level if level else None
        
        # Назначение (purpose)
        purpose = object_data.get("purpose", "")
        purpose_text = purpose if purpose else None
        
        # Дата регистрации права
        reg_date = object_data.get("regDate", "")
        reg_date_text = reg_date if reg_date else None
        
        # Дата обновления информации
        info_update_date = object_data.get("infoUpdate", "")
        info_update_text = info_update_date if info_update_date else None
        
        # Старый кадастровый номер
        old_numbers_list = object_data.get("oldNumbers", [])
        old_cadastral_number = None
        if old_numbers_list:
            # Берем первый старый номер
            first_old = old_numbers_list[0] if isinstance(old_numbers_list, list) else None
            if first_old and isinstance(first_old, dict):
                old_cadastral_number = first_old.get("numValue", "")
        
        # Дата кадастровой стоимости
        cad_cost_date = object_data.get("cadCostDate", "")
        cad_cost_date_text = cad_cost_date if cad_cost_date else None
        
        # Парсим координаты (для земельных участков)
        coordinates = None
        object_type = object_data.get("ObjectType", "")
        is_land_plot = object_type and "земельный участок" in object_type.lower()
        
        if is_land_plot:
            logger.debug(f"Обнаружен земельный участок {cadastral_number}, ищем координаты...")
            
            # Пробуем разные варианты полей с координатами
            # Вариант 1: geometry или coordinates
            geometry = object_data.get("geometry") or object_data.get("coordinates")
            if geometry:
                logger.debug(f"Найдено поле geometry/coordinates: {type(geometry)}")
                if isinstance(geometry, dict):
                    # Может быть centerPoint, centroid, или массив координат
                    center = geometry.get("centerPoint") or geometry.get("centroid")
                    if center:
                        logger.debug(f"Найден center/centroid: {type(center)}")
                        if isinstance(center, (list, tuple)) and len(center) >= 2:
                            coordinates = {"x": float(center[0]), "y": float(center[1])}
                            logger.info(f"✅ Координаты найдены из массива: x={coordinates['x']}, y={coordinates['y']}")
                        elif isinstance(center, dict):
                            x = center.get("x") or center.get("lon") or center.get("longitude")
                            y = center.get("y") or center.get("lat") or center.get("latitude")
                            if x is not None and y is not None:
                                coordinates = {"x": float(x), "y": float(y)}
                                logger.info(f"✅ Координаты найдены из словаря: x={coordinates['x']}, y={coordinates['y']}")
                elif isinstance(geometry, (list, tuple)) and len(geometry) >= 2:
                    # Прямой массив координат
                    coordinates = {"x": float(geometry[0]), "y": float(geometry[1])}
                    logger.info(f"✅ Координаты найдены из прямого массива: x={coordinates['x']}, y={coordinates['y']}")
            
            # Вариант 2: centerPoint в корне объекта
            if not coordinates:
                center_point = object_data.get("centerPoint") or object_data.get("centroid")
                if center_point:
                    logger.debug(f"Найден centerPoint/centroid в корне: {type(center_point)}")
                    if isinstance(center_point, (list, tuple)) and len(center_point) >= 2:
                        coordinates = {"x": float(center_point[0]), "y": float(center_point[1])}
                        logger.info(f"✅ Координаты найдены из корневого массива: x={coordinates['x']}, y={coordinates['y']}")
                    elif isinstance(center_point, dict):
                        x = center_point.get("x") or center_point.get("lon") or center_point.get("longitude")
                        y = center_point.get("y") or center_point.get("lat") or center_point.get("latitude")
                        if x is not None and y is not None:
                            coordinates = {"x": float(x), "y": float(y)}
                            logger.info(f"✅ Координаты найдены из корневого словаря: x={coordinates['x']}, y={coordinates['y']}")
            
            # Вариант 3: Прямые поля x, y, lon, lat в корне или в land объекте
            if not coordinates:
                land_obj = object_data.get("land", {})
                # Пробуем в land объекте
                x = land_obj.get("x") or land_obj.get("lon") or land_obj.get("longitude")
                y = land_obj.get("y") or land_obj.get("lat") or land_obj.get("latitude")
                if x is not None and y is not None:
                    coordinates = {"x": float(x), "y": float(y)}
                    logger.info(f"✅ Координаты найдены в land объекте: x={coordinates['x']}, y={coordinates['y']}")
                else:
                    # Пробуем в корне объекта
                    x = object_data.get("x") or object_data.get("lon") or object_data.get("longitude")
                    y = object_data.get("y") or object_data.get("lat") or object_data.get("latitude")
                    if x is not None and y is not None:
                        coordinates = {"x": float(x), "y": float(y)}
                        logger.info(f"✅ Координаты найдены в корне объекта: x={coordinates['x']}, y={coordinates['y']}")
            
            if not coordinates:
                logger.warning(f"⚠️ Координаты не найдены для земельного участка {cadastral_number}. Доступные ключи: {list(object_data.keys())[:20]}")
        
        return RealEstateObject(
            cadastral_number=cadastral_number,
            object_type=object_data.get("ObjectType"),
            address=readable_address,
            area=area,
            category=category,
            permitted_use=permitted_use_text,
            cadastral_value=cadastral_value,
            rights=rights_text,
            owner=None,  # ФИО собственника отсутствует согласно документации
            encumbrances=encumbrances_text,
            status=status_text,
            level=level_text,
            purpose=purpose_text,
            reg_date=reg_date_text,
            info_update_date=info_update_text,
            old_cadastral_number=old_cadastral_number,
            cadastral_cost_date=cad_cost_date_text,
            date_assigned=reg_date_text,
            engineering_communications=None,  # Не указано в документации
            form=None,  # Будет заполнено позже при генерации карты
            coordinates=coordinates,  # Координаты из API (если есть)
            api_balance=balance
        )
    
    async def get_balance(self) -> Optional[float]:
        """
        Получить текущий баланс API через личный кабинет.
        
        Согласно документации:
        GET https://api-cloud.ru/api/apilk.php?type=balance&token={ключ}
        
        Returns:
            Баланс или None если не удалось получить
            
        Raises:
            APINotConfiguredError: Если API ключ не настроен
        """
        # Режим симуляции
        if settings.API_SIMULATION_MODE:
            return self._simulate_get_balance()
        
        self._check_api_key()
        
        params = {
            "type": "balance",
            "token": self.api_key,
        }
        
        headers = self._get_headers()
        
        try:
            session = await self._get_session()
            logger.debug("Запрос баланса через API личного кабинета")
            
            async with session.get(
                self.LK_API_URL,
                params=params,
                headers=headers
            ) as response:
                if response.status == 200:
                    response_data = await response.json()
                    status = response_data.get("status")
                    
                    if status == 200:
                        balance = response_data.get("balance")
                        if balance is not None:
                            return float(balance)
                        else:
                            logger.warning("Баланс не найден в ответе API")
                            return None
                    else:
                        error_code = response_data.get("error", "UNKNOWN_ERROR")
                        error_message = response_data.get("message", f"Ошибка: {error_code}")
                        logger.warning(f"Не удалось получить баланс: {error_message}")
                        return None
                else:
                    logger.warning(f"Ошибка при получении баланса: HTTP {response.status}")
                    return None
                    
        except Exception as e:
            logger.error(f"Ошибка при получении баланса: {e}")
            return None
    
    async def check_availability(self) -> bool:
        """
        Проверяет доступность API через запрос баланса.
        
        Returns:
            True если API доступен, False иначе
        """
        # В режиме симуляции всегда доступен
        if settings.API_SIMULATION_MODE:
            return True
        
        if not self.api_key:
            return False
        
        try:
            # Пробуем получить баланс как простой способ проверки
            balance = await self.get_balance()
            return balance is not None
        except Exception as e:
            logger.debug(f"API недоступен: {e}")
            return False
    
    async def _simulate_get_cadastral_data(self, cadastral_number: str) -> RealEstateObject:
        """
        Симулирует получение данных по кадастровому номеру.
        Возвращает тестовые данные для разработки без реального API ключа.
        
        Args:
            cadastral_number: Кадастровый номер
            
        Returns:
            Объект RealEstateObject с тестовыми данными
        """
        # Симулируем задержку сети (1-3 секунды)
        await asyncio.sleep(random.uniform(1.0, 3.0))
        
        logger.info(f"[СИМУЛЯЦИЯ] Получение данных для {cadastral_number}")
        
        # Специальная обработка для известных номеров
        # 78:38:0022629:1115 - земельный участок
        if cadastral_number == "78:38:0022629:1115" or cadastral_number.endswith(":1115"):
            object_type = "Земельный участок"
        else:
            # Определяем тип объекта по номеру (для разнообразия)
            # Используем последнюю цифру для выбора типа
            last_digit = int(cadastral_number[-1]) if cadastral_number[-1].isdigit() else 0
            
            object_types = [
                "Земельный участок",
                "Здание",
                "Помещение",
                "Сооружение",
                "Земельный участок",
                "Здание",
                "Помещение",
                "Сооружение",
                "Земельный участок",
                "Здание",
            ]
            object_type = object_types[last_digit % len(object_types)]
        
        # Генерируем тестовые данные в зависимости от типа
        if "земельный участок" in object_type.lower():
            # Специальные данные для 78:38:0022629:1115
            if cadastral_number == "78:38:0022629:1115" or cadastral_number.endswith(":1115"):
                return RealEstateObject(
                    cadastral_number=cadastral_number,
                    object_type=object_type,
                    address="г. Санкт-Петербург, п. Ушково, ш. Приморское, д. 613, литера В, ЗУ3",
                    area=2956.0,  # 2.956 кв.м
                    category="Земли населённых пунктов",
                    permitted_use="Для размещения дач",
                    cadastral_value=24224607.11,  # 24.224.607,11
                    rights="Право общей долевой собственности",
                    owner=None,
                    encumbrances="Доверительное управление",
                    status="Актуально",
                    date_assigned="01.01.2020",
                    engineering_communications="Отсутствуют",
                    form="Близка к прямоугольной",
                    coordinates={"x": 3297753.127473602, "y": 8443359.318326155},
                    api_balance=round(random.uniform(1000.0, 10000.0), 2)
                )
            
            # Данные для других земельных участков
            return RealEstateObject(
                cadastral_number=cadastral_number,
                object_type=object_type,
                address=f"Российская Федерация, г. Санкт-Петербург, ул. Тестовая, д. {random.randint(1, 100)}",
                area=round(random.uniform(500.0, 5000.0), 2),
                category="Земли населённых пунктов",
                permitted_use="Для размещения объектов жилой застройки",
                cadastral_value=round(random.uniform(1000000.0, 10000000.0), 2),
                rights="Право собственности",
                owner=None,  # ФИО собственника отсутствует согласно документации
                encumbrances=None,
                status="Актуально",
                date_assigned="01.01.2020",
                engineering_communications="Отсутствуют",
                form="Близка к прямоугольной",
                coordinates={"x": random.uniform(3000000, 4000000), "y": random.uniform(8000000, 9000000)},
                api_balance=round(random.uniform(1000.0, 10000.0), 2)
            )
        elif "помещение" in object_type.lower():
            # Данные для помещения
            return RealEstateObject(
                cadastral_number=cadastral_number,
                object_type=object_type,
                address=f"Российская Федерация, г. Санкт-Петербург, ул. Тестовая, д. {random.randint(1, 100)}, кв. {random.randint(1, 200)}",
                area=round(random.uniform(30.0, 150.0), 2),
                category=None,
                permitted_use="Жилое помещение",
                cadastral_value=round(random.uniform(2000000.0, 15000000.0), 2),
                rights="Право собственности",
                owner=None,
                encumbrances=None,
                status="Актуально",
                date_assigned="01.01.2020",
                engineering_communications="Присутствуют",
                form=None,
                coordinates=None,
                api_balance=round(random.uniform(1000.0, 10000.0), 2)
            )
        elif "здание" in object_type.lower():
            # Данные для здания
            return RealEstateObject(
                cadastral_number=cadastral_number,
                object_type=object_type,
                address=f"Российская Федерация, г. Санкт-Петербург, ул. Тестовая, д. {random.randint(1, 100)}",
                area=round(random.uniform(500.0, 5000.0), 2),
                category=None,
                permitted_use="Нежилое здание",
                cadastral_value=round(random.uniform(5000000.0, 50000000.0), 2),
                rights="Право собственности",
                owner=None,
                encumbrances=None,
                status="Актуально",
                date_assigned="01.01.2020",
                engineering_communications="Присутствуют",
                form=None,
                coordinates=None,
                api_balance=round(random.uniform(1000.0, 10000.0), 2)
            )
        else:
            # Данные для сооружения
            return RealEstateObject(
                cadastral_number=cadastral_number,
                object_type=object_type,
                address=f"Российская Федерация, г. Санкт-Петербург, ул. Тестовая, д. {random.randint(1, 100)}",
                area=round(random.uniform(100.0, 1000.0), 2),
                category=None,
                permitted_use="Для размещения объектов специального назначения",
                cadastral_value=round(random.uniform(1000000.0, 20000000.0), 2),
                rights="Право собственности",
                owner=None,
                encumbrances=None,
                status="Актуально",
                date_assigned="01.01.2020",
                engineering_communications="Присутствуют",
                form=None,
                coordinates=None,
                api_balance=round(random.uniform(1000.0, 10000.0), 2)
            )
    
    def _simulate_get_balance(self) -> float:
        """
        Симулирует получение баланса API.
        
        Returns:
            Тестовый баланс
        """
        # Возвращаем случайный баланс от 1000 до 10000 рублей
        balance = round(random.uniform(1000.0, 10000.0), 2)
        logger.info(f"[СИМУЛЯЦИЯ] Баланс API: {balance} руб.")
        return balance


# Глобальный экземпляр клиента
_api_client: Optional[RosreestrAPIClient] = None


def get_api_client() -> RosreestrAPIClient:
    """Получить глобальный экземпляр API клиента."""
    global _api_client
    if _api_client is None:
        _api_client = RosreestrAPIClient()
    return _api_client


async def close_api_client():
    """Закрыть глобальный API клиент."""
    global _api_client
    if _api_client:
        await _api_client.close()
        _api_client = None
