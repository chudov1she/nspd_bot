"""
Воркер для обработки задач из очереди.
"""
import asyncio
import json
from pathlib import Path
from typing import List, Optional
from loguru import logger

from aiogram import Bot
from bot.database.models import Task, TaskStatus
from bot.services.queue import get_task_queue
from bot.services.api_client import get_api_client, APINotConfiguredError, APIConnectionError
from bot.services.excel_handler import create_output_excel, ExcelHandlerError
from bot.services.task_service import update_task_status, update_task_results
from bot.services.map_task_service import (
    get_pending_map_tasks,
    update_map_task_status,
    update_map_task_result,
    get_map_task_by_cadastral,
    get_map_task_by_id,
)
from bot.database.models import MapGenerationStatus
from bot.models.cadastral import RealEstateObject
from bot.handlers.rosreestr_common import (
    get_api_balance,
    format_response_text,
)
from bot.config.settings import settings


class TaskWorker:
    """Воркер для обработки задач из очереди."""
    
    def __init__(self, bot: Bot):
        self.bot = bot
        self.queue = get_task_queue()
        self._running = False
        self._task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Запускает воркер."""
        if self._running:
            logger.warning("Воркер уже запущен")
            return
        
        self._running = True
        self._task = asyncio.create_task(self._worker_loop())
        logger.info("Воркер задач запущен")
    
    async def stop(self):
        """Останавливает воркер."""
        self._running = False
        if self._task:
            await self._task
        logger.info("Воркер задач остановлен")
    
    async def _worker_loop(self):
        """Основной цикл воркера."""
        while self._running:
            try:
                # Получаем следующую задачу из очереди
                task = await self.queue.get_next_task()
                
                if task:
                    await self._process_task(task)
                else:
                    # Если очередь пуста, ждем перед следующей проверкой
                    await asyncio.sleep(2)
                    
            except Exception as e:
                logger.error(f"Ошибка в цикле воркера: {e}", exc_info=True)
                await asyncio.sleep(5)  # Ждем перед повтором при ошибке
    
    async def _process_task(self, task: Task):
        """
        Обрабатывает одну задачу.
        
        Args:
            task: Задача для обработки
        """
        logger.info(f"Начата обработка задачи {task.id} (пользователь {task.user_id})")
        
        try:
            # Парсим кадастровые номера
            numbers = await self._parse_cadastral_numbers(task)
            
            if not numbers:
                await update_task_status(
                    task.id, 
                    TaskStatus.FAILED, 
                    "Кадастровые номера не найдены"
                )
                await self._notify_user(
                    task.user_id,
                    f"❌ <b>Задача #{task.id} завершена с ошибкой</b>\n\n"
                    "⚠️ <b>Данные не найдены</b>\n\n"
                    "Кадастровые номера не найдены в предоставленных данных.\n\n"
                    "💡 <b>Проверьте:</b>\n"
                    "• Правильность формата номеров (XX:XX:XXXXXXX:XXXX)\n"
                    "• Наличие номеров в тексте или файле"
                )
                return
            
            # Проверяем доступность API
            if not await self._check_api_for_task(task, numbers):
                return
            
            # Уведомление о начале обработки
            numbers_count = len(numbers)
            numbers_text = "номер" if numbers_count == 1 else "номеров"
            
            await self._notify_user(
                task.user_id,
                f"🔄 <b>Задача #{task.id} в работе</b>\n\n"
                f"📊 <b>Найдено номеров:</b> {numbers_count}\n"
                f"🌐 <b>Получение данных из Росреестра...</b>\n\n"
                f"⏳ Это может занять некоторое время."
            )
            
            # Получаем данные через API
            results = await self._fetch_api_data(numbers, task.id)
            
            # Обрабатываем результаты
            await self._process_results(task, numbers, results)
            
            # Закрываем браузер после завершения задачи, чтобы новая задача создавала новый экземпляр
            await self._close_browser_after_task()
            
            logger.info(f"Задача {task.id} успешно обработана")
            
        except Exception as e:
            logger.error(f"Ошибка при обработке задачи {task.id}: {e}", exc_info=True)
            await update_task_status(
                task.id,
                TaskStatus.FAILED,
                f"Ошибка обработки: {str(e)}"
            )
            
            error_msg = str(e)
            # Ограничиваем длину сообщения об ошибке
            if len(error_msg) > 300:
                error_msg = error_msg[:300] + "..."
            
            await self._notify_user(
                task.user_id,
                f"❌ <b>Задача #{task.id} завершена с ошибкой</b>\n\n"
                "⚠️ <b>Произошла ошибка при обработке</b>\n\n"
                f"<code>{error_msg}</code>\n\n"
                "Обратитесь к администратору, если проблема повторяется."
            )
        finally:
            # Закрываем браузер после завершения задачи (успешной или с ошибкой)
            # чтобы новая задача создавала новый экземпляр
            await self._close_browser_after_task()
    
    async def _parse_cadastral_numbers(self, task: Task) -> List[str]:
        """Парсит кадастровые номера из задачи."""
        from bot.services.parser import (
            extract_cadastral_numbers_from_text,
            extract_cadastral_numbers_from_excel,
        )
        
        if task.task_type.value == "text_input":
            # Парсим из текста
            if task.input_data:
                return extract_cadastral_numbers_from_text(task.input_data)
        
        elif task.task_type.value == "file_upload":
            # Парсим из файла
            if task.input_file_path:
                file_path = Path(task.input_file_path)
                if file_path.exists():
                    return extract_cadastral_numbers_from_excel(file_path)
        
        # Если номера уже сохранены в БД
        if task.cadastral_numbers:
            try:
                return json.loads(task.cadastral_numbers)
            except json.JSONDecodeError:
                pass
        
        return []
    
    async def _check_api_for_task(self, task: Task, numbers: List[str]) -> bool:
        """Проверяет доступность API для задачи."""
        # Создаем временное сообщение для проверки API
        # (функция check_api_availability требует Message)
        # Используем прямую проверку
        
        api_client = get_api_client()
        
        if not settings.is_api_configured():
            await update_task_status(task.id, TaskStatus.FAILED, "API ключ не задан")
            await self._notify_user(
                task.user_id,
                f"❌ <b>Задача #{task.id} завершена с ошибкой</b>\n\n"
                "🔑 <b>API ключ не настроен</b>\n\n"
                "Для получения данных необходимо настроить API ключ.\n\n"
                "Обратитесь к администратору для настройки API."
            )
            return False
        
        is_available = await api_client.check_availability()
        if not is_available:
            await update_task_status(task.id, TaskStatus.FAILED, "API недоступен")
            await self._notify_user(
                task.user_id,
                f"❌ <b>Задача #{task.id} завершена с ошибкой</b>\n\n"
                "🌐 <b>API Росреестра недоступен</b>\n\n"
                "Сервис временно недоступен. Попробуйте повторить запрос позже.\n\n"
                "Если проблема сохраняется, обратитесь к администратору."
            )
            return False
        
        return True
    
    async def _fetch_api_data(
        self, 
        numbers: List[str], 
        task_id: int
    ) -> List[RealEstateObject]:
        """
        Получает данные через API для всех номеров.
        
        Args:
            numbers: Список кадастровых номеров
            task_id: ID задачи для логирования
            
        Returns:
            Список результатов
        """
        api_client = get_api_client()
        results = []
        
        total = len(numbers)
        for idx, number in enumerate(numbers, 1):
            try:
                logger.info(f"[Задача {task_id}] Обработка {idx}/{total}: {number}")
                result = await api_client.get_cadastral_data(number)
                results.append(result)
                
                # Периодически отправляем прогресс (каждые 10 номеров или в конце)
                if idx % 10 == 0 or idx == total:
                    await self._notify_progress(task_id, idx, total)
                    
            except Exception as e:
                logger.error(f"[Задача {task_id}] Ошибка для {number}: {e}")
                results.append(RealEstateObject(
                    cadastral_number=number,
                    error=str(e),
                    error_code="API_ERROR"
                ))
        
        return results
    
    async def _close_browser_after_lk(self):
        """
        Закрывает браузер после работы с личным кабинетом Росреестра.
        Это гарантирует, что для генерации карт будет создан новый экземпляр браузера.
        """
        try:
            from bot.services.browser_manager import close_browser_manager
            from bot.services.rosreestr_lk import get_lk_client
            
            logger.debug("Закрытие браузера после работы с ЛК...")
            
            # Закрываем контекст ЛК клиента
            try:
                lk_client = get_lk_client()
                if lk_client._context is not None:
                    await lk_client.close()
                    logger.debug("Контекст RosreestrLKClient закрыт")
            except Exception as e:
                logger.debug(f"Ошибка при закрытии RosreestrLKClient: {e}")
            
            # Закрываем общий браузер (это также сбросит singleton)
            await close_browser_manager()
            logger.info("Браузер закрыт после работы с ЛК, для генерации карт будет создан новый экземпляр")
            
        except Exception as e:
            logger.warning(f"Ошибка при закрытии браузера после ЛК: {e}")
    
    async def _close_browser_after_maps(self):
        """
        Закрывает браузер после генерации карт.
        Это гарантирует, что следующая задача начнет с чистого состояния.
        """
        try:
            from bot.services.browser_manager import close_browser_manager
            from bot.services.map_generator import get_map_generator
            
            logger.debug("Закрытие браузера после генерации карт...")
            
            # Закрываем контекст генератора карт
            try:
                map_generator = get_map_generator()
                if map_generator._context is not None:
                    await map_generator.close()
                    logger.debug("Контекст MapGenerator закрыт")
            except Exception as e:
                logger.debug(f"Ошибка при закрытии MapGenerator: {e}")
            
            # Закрываем общий браузер (это также сбросит singleton)
            await close_browser_manager()
            logger.info("Браузер закрыт после генерации карт, следующая задача создаст новый экземпляр")
            
        except Exception as e:
            logger.warning(f"Ошибка при закрытии браузера после генерации карт: {e}")
    
    async def _close_browser_after_task(self):
        """
        Закрывает браузер после завершения задачи.
        Это позволяет новой задаче создать новый экземпляр браузера.
        """
        try:
            from bot.services.browser_manager import close_browser_manager
            from bot.services.map_generator import get_map_generator
            from bot.services.rosreestr_lk import get_lk_client
            
            logger.debug("Закрытие браузера после завершения задачи...")
            
            # Закрываем контексты сервисов (если они открыты)
            try:
                map_generator = get_map_generator()
                if map_generator._context is not None:
                    await map_generator.close()
                    logger.debug("Контекст MapGenerator закрыт")
            except Exception as e:
                logger.debug(f"Ошибка при закрытии MapGenerator: {e}")
            
            try:
                lk_client = get_lk_client()
                if lk_client._context is not None:
                    await lk_client.close()
                    logger.debug("Контекст RosreestrLKClient закрыт")
            except Exception as e:
                logger.debug(f"Ошибка при закрытии RosreestrLKClient: {e}")
            
            # Закрываем общий браузер (это также сбросит singleton)
            await close_browser_manager()
            logger.info("Браузер закрыт после завершения задачи, новая задача создаст новый экземпляр")
            
        except Exception as e:
            logger.warning(f"Ошибка при закрытии браузера после задачи: {e}")
    
    def _parse_rights_data(self, rights_data: List[dict]) -> tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Парсит данные о правах и ограничениях из личного кабинета.
        
        Args:
            rights_data: Список словарей с данными о правах и ограничениях
        
        Returns:
            Кортеж (передаваемые права, правообладатель, обременения)
            - передаваемые права: полная информация о виде права (вид + номер + дата)
            - правообладатель: ФИО или название организации (если есть в данных)
            - обременения: полная информация об обременениях (вид + номер + дата)
        """
        rights = None
        owner = None
        encumbrances = None
        
        # Детальное логирование для отладки
        logger.info(f"Парсинг данных о правах: {len(rights_data)} записей")
        for idx, item in enumerate(rights_data):
            name = item.get('name', '')
            name_lower = name.lower()
            values = item.get('values', [])
            
            logger.info(f"  Запись {idx + 1}: name='{name}', values={values}")
            
            if not values:
                logger.warning(f"  Запись {idx + 1}: пропущена (нет значений)")
                continue
            
            # Ищем информацию о праве через "Вид, номер и дата государственной регистрации права"
            # Это должно идти в колонку "Передаваемые права" (self.rights)
            # Проверяем различные варианты названия (более гибкое условие)
            # Название может быть: "Вид, номер и дата государственной регистрации права"
            # Или просто содержать ключевые слова
            if 'вид' in name_lower:
                # Если есть "вид" и (есть "регистрация" или "право" или "государственной" или ("номер" и "дата"))
                if 'регистрация' in name_lower or 'право' in name_lower or \
                   'государственной' in name_lower or ('номер' in name_lower and 'дата' in name_lower):
                    # Объединяем все значения (вид права + номер + дата)
                    rights = '; '.join(values)
                    logger.info(f"  ✅ Запись {idx + 1}: найдены права из '{name}': '{rights}'")
                else:
                    logger.warning(f"  ⚠️ Запись {idx + 1}: содержит 'вид', но не подходит под условие: '{name}'")
            else:
                # Если нет "вид", но есть другие ключевые слова - тоже может быть информация о праве
                if ('номер' in name_lower and 'дата' in name_lower and 'регистрация' in name_lower) or \
                   ('государственной' in name_lower and 'регистрация' in name_lower):
                    rights = '; '.join(values)
                    logger.info(f"  ✅ Запись {idx + 1}: найдены права (альтернативное условие) из '{name}': '{rights}'")
            
            # Ищем обременения через "Ограничение прав и обременение объекта недвижимости"
            # Это должно идти в колонку "Обременения (ограничения)" (self.encumbrances)
            if 'обременение' in name_lower or 'ограничение' in name_lower:
                # Объединяем все значения (вид обременения + номер + дата)
                encumbrances = '; '.join(values)
                logger.info(f"  ✅ Запись {idx + 1}: найдены обременения из '{name}': '{encumbrances}'")
            
            # Правообладатель (ФИО или название организации) обычно не содержится
            # в разделе "Сведения о правах и ограничениях", поэтому оставляем None
            # Если в будущем появятся данные о конкретном правообладателе, их можно
            # извлечь здесь по соответствующему ключу
        
        logger.info(f"Результат парсинга: rights='{rights}', owner='{owner}', encumbrances='{encumbrances}'")
        return rights, owner, encumbrances
    
    async def _enrich_data_from_lk(
        self,
        results: List[RealEstateObject],
        task_id: int
    ) -> List[RealEstateObject]:
        """
        Дополняет данные объектов информацией из личного кабинета Росреестра.
        
        Args:
            results: Список объектов с данными из API
            task_id: ID задачи для логирования
        
        Returns:
            Обновлённый список объектов
        """
        from bot.services.rosreestr_lk import get_lk_client
        
        # Фильтруем объекты, которые нужно дополнить
        # ПРИОРИТЕТ: Сначала используем детальные данные из API (если есть номера и даты)
        # Только если данных из API нет или они неполные (без номеров и дат) - обращаемся к ЛК
        objects_to_enrich = []
        
        for obj in results:
            if obj.has_error():
                continue
            
            # Проверяем, есть ли детальные данные из API
            # Детальные данные содержат "№" (номер) и "от" (дата)
            has_detailed_rights = obj.rights and "№" in obj.rights and "от" in obj.rights
            has_detailed_encumbrances = obj.encumbrances and "№" in obj.encumbrances and "от" in obj.encumbrances
            
            # Если нет детальных данных по правам или обременениям - добавляем в список для дополнения
            if not has_detailed_rights or not has_detailed_encumbrances:
                objects_to_enrich.append(obj)
                logger.debug(
                    f"[Задача {task_id}] Объект {obj.cadastral_number} требует дополнения из ЛК: "
                    f"rights детальные={has_detailed_rights} (значение: '{obj.rights}'), "
                    f"encumbrances детальные={has_detailed_encumbrances} (значение: '{obj.encumbrances}')"
                )
            else:
                logger.debug(
                    f"[Задача {task_id}] Объект {obj.cadastral_number} имеет детальные данные из API, "
                    f"дополнение из ЛК не требуется. rights: '{obj.rights}', encumbrances: '{obj.encumbrances}'"
                )
        
        # Логируем, какие объекты будут дополнены
        logger.info(
            f"[Задача {task_id}] Объекты для дополнения из ЛК: {len(objects_to_enrich)} из {len([r for r in results if not r.has_error()])}. "
            f"Текущие значения rights (первые 3): "
            f"{[f'{obj.cadastral_number}: {obj.rights[:50] if obj.rights else None}...' for obj in objects_to_enrich[:3]]}"
        )
        
        if not objects_to_enrich:
            logger.info(f"[Задача {task_id}] Нет объектов для дополнения из ЛК")
            return results
        
        logger.info(f"[Задача {task_id}] Дополнение данных из ЛК для {len(objects_to_enrich)} объектов")
        
        # Получаем глобальный экземпляр клиента
        lk_client = get_lk_client()
        
        try:
            # Инициализируем браузер если нужно
            if lk_client._browser is None:
                await lk_client.open_lk_page()
                await lk_client.scroll_to_form()
            
            # Обрабатываем каждый объект
            for idx, obj in enumerate(objects_to_enrich, 1):
                max_retries = 3
                retry_count = 0
                success = False
                
                while retry_count < max_retries and not success:
                    try:
                        logger.info(
                            f"[Задача {task_id}] Дополнение {idx}/{len(objects_to_enrich)}: "
                            f"{obj.cadastral_number} (попытка {retry_count + 1}/{max_retries})"
                        )
                        
                        # Проверяем, что браузер еще работает
                        try:
                            if lk_client._page is None:
                                raise Exception("Страница не инициализирована")
                            # Пробуем получить URL для проверки доступности
                            _ = lk_client._page.url
                        except Exception as browser_error:
                            logger.warning(
                                f"[Задача {task_id}] Браузер недоступен, перезапускаем: {browser_error}"
                            )
                            if not await lk_client.restart_browser():
                                raise Exception("Не удалось перезапустить браузер")
                            await lk_client.open_lk_page()
                            await lk_client.scroll_to_form()
                        
                        # Сначала заполняем кадастровый номер
                        await lk_client.fill_cadastral_number(obj.cadastral_number)
                        
                        # Теперь работаем с капчей (до 5 попыток)
                        captcha_attempts = 0
                        max_captcha_attempts = 5
                        captcha_success = False
                        
                        while captcha_attempts < max_captcha_attempts and not captcha_success:
                            captcha_attempts += 1
                            
                            # Получаем и распознаем капчу
                            captcha_path, captcha_text = await lk_client.get_and_recognize_captcha()
                            
                            if not captcha_text:
                                logger.warning(
                                    f"[Задача {task_id}] Не удалось распознать капчу для {obj.cadastral_number} "
                                    f"(попытка {captcha_attempts}/{max_captcha_attempts})"
                                )
                                if captcha_attempts < max_captcha_attempts:
                                    # Обновляем капчу и пробуем снова
                                    await lk_client.reload_captcha()
                                    await asyncio.sleep(1)
                                continue
                            
                            # Заполняем капчу
                            await lk_client.fill_captcha(captcha_text)
                            await lk_client._page.wait_for_timeout(500)  # Небольшая задержка после ввода капчи
                            
                            # Пробуем кликнуть по кнопке поиска
                            search_button_clicked = await lk_client.click_search_button()
                            
                            if not search_button_clicked:
                                # Кнопка не найдена - проверяем ошибку капчи
                                await lk_client._page.wait_for_timeout(1000)  # Ждем проверки капчи на сервере
                                has_captcha_error = await lk_client.check_captcha_error()
                                
                                if has_captcha_error:
                                    logger.warning(
                                        f"[Задача {task_id}] Ошибка капчи для {obj.cadastral_number} "
                                        f"(попытка {captcha_attempts}/{max_captcha_attempts})"
                                    )
                                    if captcha_attempts < max_captcha_attempts:
                                        # Обновляем капчу и пробуем снова
                                        await lk_client.reload_captcha()
                                        await lk_client._page.wait_for_timeout(1000)
                                    continue
                                else:
                                    # Кнопка не найдена, но ошибки капчи нет - другая проблема
                                    logger.warning(
                                        f"[Задача {task_id}] Кнопка поиска не найдена для {obj.cadastral_number}"
                                    )
                                    retry_count += 1
                                    if retry_count < max_retries:
                                        await lk_client.navigate_to_search_page()
                                        await asyncio.sleep(2)
                                    break
                            
                            # Проверяем ошибку капчи после клика
                            await lk_client._page.wait_for_timeout(1000)  # Ждем проверки капчи на сервере
                            has_captcha_error = await lk_client.check_captcha_error()
                            
                            if has_captcha_error:
                                logger.warning(
                                    f"[Задача {task_id}] Ошибка капчи для {obj.cadastral_number} "
                                    f"(попытка {captcha_attempts}/{max_captcha_attempts})"
                                )
                                if captcha_attempts < max_captcha_attempts:
                                    # Обновляем капчу и пробуем снова
                                    await lk_client.reload_captcha()
                                    await asyncio.sleep(1)
                                continue
                            
                            # Капча введена правильно, проверяем результаты
                            captcha_success = True
                        
                        if not captcha_success:
                            logger.error(
                                f"[Задача {task_id}] Не удалось ввести капчу для {obj.cadastral_number} "
                                f"после {max_captcha_attempts} попыток"
                            )
                            retry_count += 1
                            if retry_count < max_retries:
                                await lk_client.navigate_to_search_page()
                                await asyncio.sleep(2)
                            continue
                        
                        # Ждем результатов
                        if not await lk_client.wait_for_search_results():
                            logger.warning(
                                f"[Задача {task_id}] Результаты не найдены для {obj.cadastral_number}"
                            )
                            retry_count += 1
                            if retry_count < max_retries:
                                await lk_client.navigate_to_search_page()
                                await asyncio.sleep(2)
                            continue
                        
                        # Кликаем по первой ссылке
                        if not await lk_client.click_first_result():
                            logger.warning(
                                f"[Задача {task_id}] Ссылка не найдена для {obj.cadastral_number}"
                            )
                            retry_count += 1
                            if retry_count < max_retries:
                                await lk_client.navigate_to_search_page()
                                await asyncio.sleep(2)
                            continue
                        
                        # Ждем карточки
                        if not await lk_client.wait_for_object_card():
                            logger.warning(
                                f"[Задача {task_id}] Карточка не загрузилась для {obj.cadastral_number}"
                            )
                            retry_count += 1
                            if retry_count < max_retries:
                                await lk_client.navigate_to_search_page()
                                await asyncio.sleep(2)
                            continue
                        
                        # Извлекаем данные
                        rights_data = await lk_client.extract_rights_and_restrictions()
                        
                        logger.debug(
                            f"[Задача {task_id}] Извлеченные данные из ЛК для {obj.cadastral_number}: {rights_data}"
                        )
                        
                        if rights_data:
                            # Парсим данные и заполняем поля
                            rights, owner, encumbrances = self._parse_rights_data(rights_data)
                            
                            logger.debug(
                                f"[Задача {task_id}] Распарсенные данные для {obj.cadastral_number}: "
                                f"rights='{rights}', owner='{owner}', encumbrances='{encumbrances}'"
                            )
                            
                            # Заполняем передаваемые права (полная информация о виде права)
                            # ВАЖНО: Данные из ЛК перезаписывают данные из API, так как они более полные
                            if rights:
                                old_rights = obj.rights
                                obj.rights = rights
                                logger.info(
                                    f"[Задача {task_id}] ✅ Обновлено поле rights для {obj.cadastral_number}: "
                                    f"было: '{old_rights}', стало: '{obj.rights}'"
                                )
                            else:
                                logger.warning(
                                    f"[Задача {task_id}] ⚠️ Права из ЛК не найдены для {obj.cadastral_number}. "
                                    f"Текущее значение из API: '{obj.rights}'"
                                )
                            
                            # Заполняем правообладателя (если есть конкретные данные)
                            if owner:
                                obj.owner = owner
                                logger.debug(
                                    f"[Задача {task_id}] Обновлено поле owner для {obj.cadastral_number}: "
                                    f"'{obj.owner}'"
                                )
                            
                            # Заполняем обременения (полная информация об обременениях)
                            # ВАЖНО: Данные из ЛК перезаписывают данные из API
                            if encumbrances:
                                obj.encumbrances = encumbrances
                                logger.debug(
                                    f"[Задача {task_id}] Обновлено поле encumbrances для {obj.cadastral_number}: "
                                    f"'{obj.encumbrances}'"
                                )
                            
                            logger.info(
                                f"[Задача {task_id}] Данные дополнены для {obj.cadastral_number}: "
                                f"rights={bool(rights)} (значение: '{rights[:50] if rights else None}...'), "
                                f"owner={bool(owner)}, encumbrances={bool(encumbrances)}"
                            )
                            success = True
                        else:
                            logger.warning(
                                f"[Задача {task_id}] Данные о правах не найдены для {obj.cadastral_number}"
                            )
                            success = True  # Считаем успешным, даже если данных нет
                        
                        # Возвращаемся на страницу поиска для следующего объекта
                        await lk_client.navigate_to_search_page()
                        
                    except Exception as e:
                        retry_count += 1
                        logger.error(
                            f"[Задача {task_id}] Ошибка при дополнении {obj.cadastral_number} "
                            f"(попытка {retry_count}/{max_retries}): {e}"
                        )
                        
                        if retry_count < max_retries:
                            # Пытаемся перезапустить браузер при критических ошибках
                            if "timeout" in str(e).lower() or "navigation" in str(e).lower():
                                logger.info(f"[Задача {task_id}] Перезапуск браузера из-за ошибки: {e}")
                                try:
                                    await lk_client.restart_browser()
                                    await lk_client.open_lk_page()
                                    await lk_client.scroll_to_form()
                                except Exception as restart_error:
                                    logger.error(
                                        f"[Задача {task_id}] Не удалось перезапустить браузер: {restart_error}"
                                    )
                            else:
                                # Для других ошибок просто возвращаемся на страницу поиска
                                try:
                                    await lk_client.navigate_to_search_page()
                                except:
                                    pass
                            
                            await asyncio.sleep(3)  # Задержка перед повтором
                        else:
                            # Все попытки исчерпаны
                            logger.error(
                                f"[Задача {task_id}] Не удалось дополнить данные для {obj.cadastral_number} "
                                f"после {max_retries} попыток"
                            )
                
                # Небольшая задержка между объектами
                if idx < len(objects_to_enrich):
                    await asyncio.sleep(1)
            
            logger.info(f"[Задача {task_id}] Дополнение данных из ЛК завершено")
            
        except Exception as e:
            logger.error(f"[Задача {task_id}] Критическая ошибка при дополнении из ЛК: {e}", exc_info=True)
            # Возвращаем исходные результаты без дополнения
        finally:
            # ВАЖНО: Закрываем браузер после работы с ЛК
            # Это гарантирует, что для генерации карт будет создан новый экземпляр
            await self._close_browser_after_lk()
        
        return results
    
    async def _create_map_tasks_for_land_plots(
        self,
        task: Task,
        results: List[RealEstateObject]
    ) -> None:
        """
        Создает задачи генерации карт в БД для земельных участков.
        Проверяет дубликаты и существующие карты.
        """
        from bot.services.map_task_service import create_map_task
        
        # Фильтруем земельные участки (координаты не требуются - поиск по кадастровому номеру)
        land_plots = [r for r in results if r.is_land_plot() and not r.has_error()]
        
        if not land_plots:
            logger.debug("Нет земельных участков в результатах")
            return
        
        logger.info(f"Создание задач генерации карт для {len(land_plots)} земельных участков")
        
        created_count = 0
        skipped_count = 0
        
        for plot in land_plots:
            try:
                # Используем координаты из API если есть, иначе пустой словарь (поиск по номеру)
                coordinates = plot.coordinates or {}
                map_task = await create_map_task(
                    user_id=task.user_id,
                    cadastral_number=plot.cadastral_number,
                    coordinates=coordinates,
                    parent_task_id=task.id,
                    max_retries=1  # Без повторных попыток - сразу FAILED при ошибке
                )
                
                if map_task:
                    created_count += 1
                    logger.debug(f"Создана задача генерации карты {map_task.id} для {plot.cadastral_number}")
                else:
                    skipped_count += 1
                    # Проверяем, есть ли уже готовая карта
                    from bot.services.map_task_service import get_map_task_by_cadastral
                    from bot.database.models import MapGenerationStatus
                    existing_task = await get_map_task_by_cadastral(
                        plot.cadastral_number,
                        status=MapGenerationStatus.COMPLETED
                    )
                    if existing_task and existing_task.map_file_path:
                        from pathlib import Path
                        if Path(existing_task.map_file_path).exists():
                            plot.map_image_path = existing_task.map_file_path
                            logger.debug(f"Использована существующая карта для {plot.cadastral_number}")
                    
            except Exception as e:
                logger.error(f"Ошибка при создании задачи генерации карты для {plot.cadastral_number}: {e}", exc_info=True)
        
        logger.info(
            f"Задачи генерации карт: создано {created_count}, пропущено {skipped_count} "
            f"(дубликаты или существующие карты)"
        )
    
    async def _notify_user_if_map_failed(
        self,
        map_task,
        error_message: str
    ) -> None:
        """
        Отправляет пользователю уведомление, если задача генерации карты окончательно провалилась.
        
        Args:
            map_task: Задача генерации карты (до обновления)
            error_message: Сообщение об ошибке
        """
        try:
            # Получаем обновленную задачу из БД, чтобы проверить её статус
            updated_task = await get_map_task_by_id(map_task.id)
            if not updated_task:
                return
            
            # Отправляем сообщение только если задача окончательно провалилась (FAILED)
            if updated_task.status == MapGenerationStatus.FAILED:
                # Формируем сообщение с конкретной причиной ошибки
                error_lower = error_message.lower()
                if "не найден" in error_lower or "не найден" in error_message:
                    title = "❌ <b>Кадастровый участок не найден</b>"
                    message_text = (
                        f"{title}\n\n"
                        f"Кадастровый номер: <code>{map_task.cadastral_number}</code>\n\n"
                        f"{error_message}"
                    )
                elif "координат" in error_lower:
                    title = "❌ <b>Отсутствуют координаты</b>"
                    message_text = (
                        f"{title}\n\n"
                        f"Кадастровый номер: <code>{map_task.cadastral_number}</code>\n\n"
                        f"{error_message}"
                    )
                elif "timeout" in error_lower or "превышен" in error_lower:
                    title = "❌ <b>Превышено время ожидания</b>"
                    message_text = (
                        f"{title}\n\n"
                        f"Кадастровый номер: <code>{map_task.cadastral_number}</code>\n\n"
                        f"{error_message}"
                    )
                else:
                    # Для других ошибок показываем сообщение как есть
                    message_text = (
                        f"❌ <b>{error_message}</b>\n\n"
                        f"Кадастровый номер: <code>{map_task.cadastral_number}</code>"
                    )
                
                try:
                    await self.bot.send_message(
                        chat_id=map_task.user_id,
                        text=message_text,
                        parse_mode="HTML"
                    )
                    logger.info(
                        f"Отправлено уведомление пользователю {map_task.user_id} "
                        f"об ошибке генерации карты для {map_task.cadastral_number}"
                    )
                except Exception as e:
                    logger.error(
                        f"Ошибка при отправке уведомления пользователю {map_task.user_id}: {e}"
                    )
        except Exception as e:
            logger.error(f"Ошибка при проверке статуса задачи {map_task.id}: {e}", exc_info=True)
    
    async def _process_map_generation_tasks(
        self,
        results: List[RealEstateObject]
    ) -> None:
        """
        Обрабатывает задачи генерации карт из БД и обновляет пути к картам в results.
        """
        # Получаем задачи в ожидании (повторных попыток больше нет)
        pending_tasks = await get_pending_map_tasks(limit=50)
        
        all_tasks = pending_tasks
        
        if not all_tasks:
            return
        
        logger.info(f"Обработка {len(all_tasks)} задач генерации карт")
        
        try:
            from bot.services.map_generator import get_map_generator
            map_generator = get_map_generator()
            
            for map_task in all_tasks:
                try:
                    # Обновляем статус на "обрабатывается"
                    await update_map_task_status(map_task.id, MapGenerationStatus.PROCESSING)
                    
                    # Подготавливаем данные для генерации (координаты опциональны - поиск по номеру)
                    coordinates = {}
                    if map_task.coordinate_x and map_task.coordinate_y:
                        try:
                            coordinates = {
                                'x': float(map_task.coordinate_x),
                                'y': float(map_task.coordinate_y)
                            }
                        except (ValueError, TypeError):
                            coordinates = {}
                    
                    # Генерируем карту (поиск выполняется по кадастровому номеру)
                    plots_data = [{
                        'cadastral_number': map_task.cadastral_number,
                        'coordinates': coordinates  # Может быть пустым - поиск по номеру
                    }]
                    
                    map_results = await map_generator.generate_map_batch(plots_data)
                    map_path = map_results.get(map_task.cadastral_number)
                    
                    if map_path:
                        # Успешно сгенерирована
                        await update_map_task_result(
                            map_task.id,
                            map_file_path=str(map_path)
                        )
                        
                        # Обновляем путь к карте в results
                        for result in results:
                            if result.cadastral_number == map_task.cadastral_number:
                                result.map_image_path = str(map_path)
                                break
                        
                        logger.info(f"Карта сгенерирована для {map_task.cadastral_number}: {map_path}")
                    else:
                        # Ошибка генерации
                        error_msg = "Не удалось сгенерировать карту"
                        await update_map_task_result(
                            map_task.id,
                            error_message=error_msg
                        )
                        # Проверяем, окончательно ли провалилась задача (все попытки исчерпаны)
                        await self._notify_user_if_map_failed(map_task, error_msg)
                        
                except Exception as e:
                    error_msg = str(e)
                    logger.error(
                        f"Ошибка при обработке задачи генерации карты {map_task.id} "
                        f"для {map_task.cadastral_number}: {error_msg}",
                        exc_info=True
                    )
                    await update_map_task_result(
                        map_task.id,
                        error_message=error_msg
                    )
                    # Проверяем, окончательно ли провалилась задача (все попытки исчерпаны)
                    await self._notify_user_if_map_failed(map_task, error_msg)
                    
        except Exception as e:
            logger.error(f"Ошибка при обработке задач генерации карт: {e}", exc_info=True)
        finally:
            # ВАЖНО: Закрываем браузер после генерации карт
            # Это гарантирует, что следующая задача начнет с чистого состояния
            await self._close_browser_after_maps()
    
    async def _process_results(
        self,
        task: Task,
        numbers: List[str],
        results: List[RealEstateObject]
    ):
        """Обрабатывает результаты и отправляет файл пользователю."""
        # Дополняем данные из личного кабинета Росреестра (если нужно)
        results = await self._enrich_data_from_lk(results, task.id)
        
        # Создаем задачи генерации карт в БД для земельных участков
        await self._create_map_tasks_for_land_plots(task, results)
        
        # Обрабатываем задачи генерации карт (если есть) и обновляем пути к картам в results
        await self._process_map_generation_tasks(results)
        
        # Подсчитываем статистику
        successful = [r for r in results if not r.has_error()]
        failed = [r for r in results if r.has_error()]
        
        # Получаем баланс
        balance = await get_api_balance(results)
        
        # Формируем Excel файлы
        try:
            source_file_path = None
            if task.input_file_path:
                source_file_path = Path(task.input_file_path)
                if not source_file_path.exists():
                    source_file_path = None
            
            # Создаем основной файл с данными
            if source_file_path:
                output_file = create_output_excel(results, source_file_path=source_file_path)
            else:
                output_file = create_output_excel(results)
            
            # Карты теперь добавляются в основной файл, отдельный файл не создаём
            
            # Обновляем задачу с результатами
            await update_task_results(
                task_id=task.id,
                processed_count=len(numbers),
                successful_count=len(successful),
                failed_count=len(failed),
                output_file_path=str(output_file),
                api_balance=balance
            )
            
            # Формируем текст ответа
            response_text = format_response_text(successful, failed, balance)
            
            # Отправляем основной файл пользователю
            from aiogram.types import FSInputFile
            document = FSInputFile(output_file)
            
            # Формируем детальную информацию о результатах
            total = len(results)
            successful_count = len(successful)
            failed_count = len(failed)
            
            # Формируем единое сообщение со всей информацией
            message_text = f"✅ <b>Задача #{task.id} завершена!</b>\n\n"
            message_text += f"📊 <b>Статистика:</b>\n"
            message_text += f"• Успешно обработано: <b>{successful_count}</b>\n"
            if failed_count > 0:
                message_text += f"• С ошибками: <b>{failed_count}</b>\n"
            message_text += f"• Всего: <b>{total}</b>\n"
            
            if balance:
                try:
                    balance_float = float(balance)
                    message_text += f"\n💰 <b>Текущий баланс API:</b> {balance_float:,.2f} руб."
                except:
                    pass
            
            
            # Отправляем текстовое сообщение со всей информацией
            await self.bot.send_message(
                chat_id=task.user_id,
                text=message_text,
                parse_mode="HTML"
            )
            
            # Отправляем основной файл без caption (информация уже в текстовом сообщении)
            await self.bot.send_document(
                chat_id=task.user_id,
                document=document
            )
            
            logger.info(f"Основной файл отправлен пользователю {task.user_id} для задачи {task.id}")
            
            # Удаляем временный основной файл
            try:
                output_file.unlink()
            except Exception as e:
                logger.warning(f"Не удалось удалить временный файл {output_file}: {e}")
            
            # Удаляем исходный файл если есть
            if task.input_file_path:
                try:
                    input_path = Path(task.input_file_path)
                    if input_path.exists():
                        input_path.unlink()
                except Exception as e:
                    logger.warning(f"Не удалось удалить исходный файл {input_path}: {e}")
                    
        except ExcelHandlerError as e:
            logger.error(f"Ошибка при создании Excel файла для задачи {task.id}: {e}")
            await update_task_status(
                task.id,
                TaskStatus.FAILED,
                f"Ошибка создания файла: {str(e)}"
            )
            await self._notify_user(
                task.user_id,
                f"❌ <b>Задача #{task.id} завершена с ошибкой</b>\n\n"
                "📄 <b>Ошибка при создании файла</b>\n\n"
                f"Не удалось создать Excel файл с результатами.\n\n"
                f"<code>{str(e)[:200]}</code>\n\n"
                "Обратитесь к администратору, если проблема повторяется."
            )
        except Exception as e:
            logger.error(f"Неожиданная ошибка при обработке результатов задачи {task.id}: {e}", exc_info=True)
            await update_task_status(
                task.id,
                TaskStatus.FAILED,
                f"Ошибка: {str(e)}"
            )
            await self._notify_user(
                task.user_id,
                f"❌ <b>Задача #{task.id} завершена с ошибкой</b>\n\n"
                f"<code>{str(e)}</code>"
            )
    
    async def _notify_user(self, user_id: int, message: str):
        """Отправляет уведомление пользователю."""
        try:
            await self.bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.warning(f"Не удалось отправить уведомление пользователю {user_id}: {e}")
    
    async def _notify_progress(self, task_id: int, current: int, total: int):
        """Отправляет уведомление о прогрессе (опционально, можно отключить для частых обновлений)."""
        # Можно добавить логику отправки прогресса, но не будем спамить пользователя
        # Логируем в консоль
        logger.info(f"[Задача {task_id}] Прогресс: {current}/{total} ({current*100//total}%)")


# Глобальный экземпляр воркера
_task_worker: Optional[TaskWorker] = None


def get_task_worker(bot: Bot) -> TaskWorker:
    """Получить глобальный экземпляр воркера."""
    global _task_worker
    if _task_worker is None:
        _task_worker = TaskWorker(bot)
    return _task_worker

