"""
Основной класс для работы с личным кабинетом Росреестра.
"""
import os
import platform
from pathlib import Path
from typing import Optional
from loguru import logger

from bot.services.rosreestr_lk.exceptions import RosreestrLKError
from bot.services.rosreestr_lk.captcha_recognizer import CaptchaRecognizer
from bot.services.rosreestr_lk.llm_captcha_recognizer import LLMCaptchaRecognizer


class RosreestrLKClient:
    """Клиент для работы с личным кабинетом Росреестра (lk.rosreestr.ru)."""
    
    # URL личного кабинета
    LK_URL = "https://lk.rosreestr.ru/eservices/real-estate-objects-online"
    
    def __init__(self, use_llm_for_captcha: bool = False):
        """
        Инициализация клиента.
        
        Args:
            use_llm_for_captcha: Использовать LLM для распознавания капчи вместо Tesseract
        """
        self._browser = None
        self._context = None
        self._page = None
        self._use_llm = use_llm_for_captcha
        self._recognizer = None
        self._llm_recognizer = None
        
        if use_llm_for_captcha:
            self._llm_recognizer = LLMCaptchaRecognizer()
        else:
            self._recognizer = CaptchaRecognizer()
    
    async def _init_browser(self):
        """Инициализирует браузер Playwright через общий менеджер."""
        try:
            from bot.services.browser_manager import get_browser_manager
            
            if self._browser is None:
                # Получаем общий браузер из менеджера
                browser_manager = await get_browser_manager()
                self._browser = await browser_manager.get_browser()
                
                # Создаем свой контекст для этого сервиса
                self._context = await browser_manager.create_context(
                    ignore_https_errors=True,
                    viewport={"width": 1920, "height": 1080}
                )
                
                # Создаем страницу в нашем контексте
                self._page = await self._context.new_page()
                
                # Устанавливаем заголовки для русского языка
                await self._page.set_extra_http_headers({"Accept-Language": "ru-RU,ru;q=0.9"})
                
                logger.debug("Контекст и страница для RosreestrLKClient созданы (используется общий браузер)")
                
        except ImportError as e:
            raise RosreestrLKError(
                f"Ошибка импорта: {e}. Установите: pip install playwright && playwright install chromium"
            )
        except Exception as e:
            logger.error(f"Ошибка инициализации браузера: {e}")
            raise RosreestrLKError(f"Не удалось инициализировать браузер: {str(e)}")
    
    async def open_lk_page(self) -> bool:
        """
        Открывает страницу личного кабинета Росреестра.
        
        Returns:
            True если страница успешно открыта, False иначе
        """
        try:
            # Инициализируем браузер, если еще не инициализирован
            if self._browser is None:
                await self._init_browser()
            
            logger.info(f"Открытие страницы личного кабинета: {self.LK_URL}")
            
            # Открываем страницу
            await self._page.goto(self.LK_URL, wait_until="domcontentloaded", timeout=30000)
            
            # Ждем загрузки страницы
            await self._page.wait_for_load_state("networkidle", timeout=10000)
            
            logger.info("Страница личного кабинета успешно открыта")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при открытии страницы личного кабинета: {e}")
            raise RosreestrLKError(f"Не удалось открыть страницу: {str(e)}")
    
    async def scroll_to_form(self) -> bool:
        """
        Прокручивает страницу до формы поиска и центрирует её на экране.
        
        Returns:
            True если форма найдена и прокрутка выполнена, False иначе
        """
        try:
            logger.info("Прокрутка к форме поиска...")
            
            # Ждем появления формы
            form_selector = ".realestateobjects-wrapper.card"
            await self._page.wait_for_selector(form_selector, timeout=10000)
            
            # Получаем элемент формы
            form_element = await self._page.query_selector(form_selector)
            
            if not form_element:
                logger.warning("Форма поиска не найдена на странице")
                return False
            
            # Прокручиваем к элементу и центрируем его
            await form_element.scroll_into_view_if_needed()
            
            # Центрируем элемент в видимой области через JavaScript
            await self._page.evaluate("""
                (element) => {
                    const elementRect = element.getBoundingClientRect();
                    const absoluteElementTop = elementRect.top + window.pageYOffset;
                    const middle = absoluteElementTop - (window.innerHeight / 2) + (elementRect.height / 2);
                    window.scrollTo({
                        top: middle,
                        behavior: 'smooth'
                    });
                }
            """, form_element)
            
            # Ждем завершения прокрутки
            await self._page.wait_for_timeout(500)
            
            logger.info("Форма поиска прокручена и отцентрирована")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при прокрутке к форме: {e}")
            raise RosreestrLKError(f"Не удалось прокрутить к форме: {str(e)}")
    
    async def get_captcha_image(self, save_path: Optional[Path] = None) -> Optional[Path]:
        """
        Получает изображение капчи и сохраняет его.
        
        Args:
            save_path: Путь для сохранения изображения. Если не указан, создается временный файл.
        
        Returns:
            Path к сохраненному файлу или None при ошибке
        """
        try:
            logger.info("Получение изображения капчи...")
            
            # Ждем появления изображения капчи
            captcha_selector = ".rros-ui-lib-captcha-content-img"
            await self._page.wait_for_selector(captcha_selector, timeout=10000)
            
            # Получаем элемент изображения через locator
            captcha_locator = self._page.locator(captcha_selector)
            
            if not await captcha_locator.count():
                logger.warning("Изображение капчи не найдено на странице")
                return None
            
            # Делаем скриншот элемента (это работает даже с blob URL)
            # Определяем путь для сохранения
            if save_path is None:
                from bot.config.settings import settings
                save_path = settings.DATA_DIR / "output" / "captcha.png"
                save_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Делаем скриншот элемента
            await captcha_locator.screenshot(path=str(save_path))
            
            logger.info(f"Изображение капчи сохранено: {save_path}")
            return save_path
            
        except Exception as e:
            logger.error(f"Ошибка при получении изображения капчи: {e}")
            raise RosreestrLKError(f"Не удалось получить изображение капчи: {str(e)}")
    
    async def fill_cadastral_number(self, cadastral_number: str) -> bool:
        """
        Заполняет поле "Адрес или кадастровый номер" кадастровым номером.
        
        Args:
            cadastral_number: Кадастровый номер для ввода
        
        Returns:
            True если поле успешно заполнено, False иначе
        """
        try:
            logger.info(f"Заполнение поля кадастрового номера: {cadastral_number}")
            
            # Ждем появления поля
            input_selector = "#query"
            await self._page.wait_for_selector(input_selector, timeout=10000)
            
            # Очищаем поле и вводим значение
            input_element = await self._page.query_selector(input_selector)
            if not input_element:
                logger.warning("Поле кадастрового номера не найдено")
                return False
            
            # Кликаем на поле
            await input_element.click()
            await self._page.wait_for_timeout(200)  # Задержка после клика
            
            # Очищаем поле
            await self._page.keyboard.press("Control+A")
            await self._page.wait_for_timeout(100)
            await self._page.keyboard.press("Delete")
            await self._page.wait_for_timeout(200)
            
            # Вводим кадастровый номер посимвольно для более естественного ввода
            for char in cadastral_number:
                await input_element.type(char, delay=50)  # Задержка 50мс между символами
                await self._page.wait_for_timeout(30)  # Дополнительная небольшая задержка
            
            # Задержка для применения изменений
            await self._page.wait_for_timeout(500)
            
            logger.info("Поле кадастрового номера успешно заполнено")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при заполнении поля кадастрового номера: {e}")
            raise RosreestrLKError(f"Не удалось заполнить поле: {str(e)}")
    
    async def fill_captcha(self, captcha_text: str) -> bool:
        """
        Заполняет поле капчи распознанным текстом.
        
        Args:
            captcha_text: Распознанный текст капчи
        
        Returns:
            True если поле успешно заполнено, False иначе
        """
        try:
            logger.info(f"Заполнение поля капчи: {captcha_text}")
            
            # Ждем появления поля капчи
            captcha_selector = "#captcha"
            await self._page.wait_for_selector(captcha_selector, timeout=10000)
            
            # Очищаем поле и вводим значение
            captcha_element = await self._page.query_selector(captcha_selector)
            if not captcha_element:
                logger.warning("Поле капчи не найдено")
                return False
            
            # Кликаем на поле
            await captcha_element.click()
            await self._page.wait_for_timeout(200)  # Задержка после клика
            
            # Очищаем поле
            await self._page.keyboard.press("Control+A")
            await self._page.wait_for_timeout(100)
            await self._page.keyboard.press("Delete")
            await self._page.wait_for_timeout(200)
            
            # Вводим текст капчи посимвольно для более естественного ввода
            for char in captcha_text:
                await captcha_element.type(char, delay=80)  # Задержка 80мс между символами
                await self._page.wait_for_timeout(40)  # Дополнительная небольшая задержка
            
            # Задержка для применения изменений
            await self._page.wait_for_timeout(500)
            
            logger.info("Поле капчи успешно заполнено")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при заполнении поля капчи: {e}")
            raise RosreestrLKError(f"Не удалось заполнить поле капчи: {str(e)}")
    
    async def check_captcha_error(self) -> bool:
        """
        Проверяет, есть ли ошибка в поле капчи (неверно введен текст).
        
        Returns:
            True если есть ошибка, False если ошибки нет
        """
        try:
            # Проверяем наличие класса ошибки на поле капчи
            captcha_selector = "#captcha"
            captcha_element = await self._page.query_selector(captcha_selector)
            
            if not captcha_element:
                return False
            
            # Проверяем класс ошибки
            has_error_class = await captcha_element.evaluate("""
                (element) => {
                    return element.classList.contains('rros-ui-lib-block--error') ||
                           element.closest('.rros-ui-lib-input-wrapper')?.classList.contains('rros-ui-lib-input-wrapper--error');
                }
            """)
            
            # Также проверяем наличие сообщения об ошибке
            error_message = await self._page.query_selector(".rros-ui-lib-input-message.rros-ui-lib-message--error")
            has_error_message = error_message is not None
            
            return has_error_class or has_error_message
            
        except Exception as e:
            logger.warning(f"Ошибка при проверке ошибки капчи: {e}")
            return False
    
    async def reload_captcha(self) -> bool:
        """
        Обновляет изображение капчи (клик по кнопке "Обновить картинку").
        
        Returns:
            True если капча успешно обновлена, False иначе
        """
        try:
            logger.info("Обновление изображения капчи...")
            
            # Ждем появления кнопки обновления
            reload_button_selector = ".rros-ui-lib-captcha-content-reload-btn"
            await self._page.wait_for_selector(reload_button_selector, timeout=10000)
            
            # Получаем кнопку
            reload_button = await self._page.query_selector(reload_button_selector)
            if not reload_button:
                logger.warning("Кнопка обновления капчи не найдена")
                return False
            
            # Кликаем по кнопке
            await reload_button.click()
            await self._page.wait_for_timeout(1000)  # Ждем обновления изображения
            
            # Ждем появления нового изображения капчи
            captcha_img_selector = ".rros-ui-lib-captcha-content-img"
            await self._page.wait_for_selector(captcha_img_selector, timeout=10000)
            await self._page.wait_for_timeout(500)  # Дополнительная задержка для загрузки
            
            logger.info("Изображение капчи обновлено")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при обновлении капчи: {e}")
            return False
    
    async def click_search_button(self) -> bool:
        """
        Кликает по кнопке "НАЙТИ" для выполнения поиска.
        
        Returns:
            True если кнопка успешно нажата, False иначе
        """
        try:
            logger.info("Клик по кнопке поиска...")
            
            # Ждем появления кнопки
            button_selector = "#realestateobjects-search"
            await self._page.wait_for_selector(button_selector, timeout=10000)
            
            # Получаем кнопку
            button_element = await self._page.query_selector(button_selector)
            if not button_element:
                logger.warning("Кнопка поиска не найдена")
                return False
            
            # Кликаем по кнопке
            await button_element.click()
            await self._page.wait_for_timeout(500)  # Задержка после клика
            
            logger.info("Кнопка поиска нажата")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при клике по кнопке поиска: {e}")
            raise RosreestrLKError(f"Не удалось нажать кнопку поиска: {str(e)}")
    
    async def wait_for_search_results(self, timeout: int = 30000) -> bool:
        """
        Ожидает появления результатов поиска.
        
        Args:
            timeout: Таймаут ожидания в миллисекундах
        
        Returns:
            True если результаты появились, False иначе
        """
        try:
            logger.info("Ожидание результатов поиска...")
            
            # Ждем появления таблицы результатов
            table_selector = ".rros-ui-lib-table"
            await self._page.wait_for_selector(table_selector, timeout=timeout)
            
            # Ждем загрузки данных (проверяем наличие строк или сообщения об отсутствии результатов)
            await self._page.wait_for_timeout(2000)  # Дополнительная задержка для загрузки
            
            logger.info("Результаты поиска загружены")
            return True
            
        except Exception as e:
            logger.warning(f"Результаты поиска не появились: {e}")
            return False
    
    async def scroll_to_results_table(self) -> bool:
        """
        Прокручивает страницу к таблице результатов.
        
        Returns:
            True если прокрутка выполнена, False иначе
        """
        try:
            logger.info("Прокрутка к таблице результатов...")
            
            # Ждем появления таблицы
            table_selector = ".rros-ui-lib-table-wrap"
            await self._page.wait_for_selector(table_selector, timeout=10000)
            
            # Получаем элемент таблицы
            table_element = await self._page.query_selector(table_selector)
            if not table_element:
                logger.warning("Таблица результатов не найдена")
                return False
            
            # Прокручиваем к элементу и центрируем его
            await table_element.scroll_into_view_if_needed()
            
            # Центрируем элемент в видимой области через JavaScript
            await self._page.evaluate("""
                (element) => {
                    const elementRect = element.getBoundingClientRect();
                    const absoluteElementTop = elementRect.top + window.pageYOffset;
                    const middle = absoluteElementTop - (window.innerHeight / 2) + (elementRect.height / 2);
                    window.scrollTo({
                        top: middle,
                        behavior: 'smooth'
                    });
                }
            """, table_element)
            
            # Ждем завершения прокрутки
            await self._page.wait_for_timeout(500)
            
            logger.info("Таблица результатов прокручена и отцентрирована")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при прокрутке к таблице результатов: {e}")
            raise RosreestrLKError(f"Не удалось прокрутить к таблице: {str(e)}")
    
    async def click_first_result(self) -> bool:
        """
        Кликает по первой найденной ссылке в результатах поиска.
        
        Returns:
            True если ссылка найдена и клик выполнен, False если результатов нет
        """
        try:
            logger.info("Поиск первой ссылки в результатах...")
            
            # Ждем появления таблицы
            await self._page.wait_for_selector(".rros-ui-lib-table", timeout=10000)
            
            # Ищем ссылку с кадастровым номером в первой строке
            # Селектор: ссылка внутри ячейки с кадастровым номером
            link_selector = ".rros-ui-lib-table__row:first-child .realestateobjects-wrapper__results__cadNumber a"
            
            # Проверяем наличие ссылки
            link_element = await self._page.query_selector(link_selector)
            
            if not link_element:
                logger.warning("Результаты поиска не найдены или таблица пуста")
                return False
            
            # Получаем текст ссылки для логирования
            link_text = await link_element.inner_text()
            logger.info(f"Найдена ссылка: {link_text}")
            
            # Прокручиваем к ссылке если нужно
            await link_element.scroll_into_view_if_needed()
            await self._page.wait_for_timeout(300)
            
            # Кликаем по ссылке
            await link_element.click()
            await self._page.wait_for_timeout(1000)  # Задержка после клика для загрузки страницы
            
            logger.info(f"Клик выполнен по ссылке: {link_text}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при клике по первой ссылке: {e}")
            raise RosreestrLKError(f"Не удалось кликнуть по ссылке: {str(e)}")
    
    async def wait_for_object_card(self, timeout: int = 30000) -> bool:
        """
        Ожидает загрузки карточки объекта после клика по ссылке.
        
        Args:
            timeout: Таймаут ожидания в миллисекундах
        
        Returns:
            True если карточка загружена, False иначе
        """
        try:
            logger.info("Ожидание загрузки карточки объекта...")
            
            # Ждем появления карточки объекта
            card_selector = ".build-card-wrapper"
            await self._page.wait_for_selector(card_selector, timeout=timeout)
            
            # Ждем загрузки данных
            await self._page.wait_for_timeout(2000)  # Дополнительная задержка для загрузки
            
            logger.info("Карточка объекта загружена")
            return True
            
        except Exception as e:
            logger.warning(f"Карточка объекта не загрузилась: {e}")
            return False
    
    async def extract_rights_and_restrictions(self) -> list[dict]:
        """
        Извлекает данные о правах и ограничениях (обременениях) из карточки объекта.
        
        Returns:
            Список словарей с данными о правах и ограничениях
        """
        try:
            logger.info("Извлечение данных о правах и ограничениях...")
            
            # Ждем появления карточки
            await self._page.wait_for_selector(".build-card-wrapper", timeout=10000)
            
            # Извлекаем данные через JavaScript
            data = await self._page.evaluate("""
                () => {
                    // Ищем все заголовки h3
                    const allH3 = document.querySelectorAll('.build-card-wrapper__info h3');
                    let targetSection = null;
                    
                    // Ищем нужный раздел по тексту заголовка
                    for (let h3 of allH3) {
                        if (h3.textContent.includes('Сведения о правах и ограничениях')) {
                            targetSection = h3.closest('.build-card-wrapper__info');
                            break;
                        }
                    }
                    
                    if (!targetSection) {
                        console.log('Раздел "Сведения о правах и ограничениях" не найден');
                        return [];
                    }
                    
                    const items = targetSection.querySelectorAll('.build-card-wrapper__info__ul__subinfo');
                    const result = [];
                    
                    items.forEach((item, index) => {
                        const nameElement = item.querySelector('.build-card-wrapper__info__ul__subinfo__name');
                        const optionsElements = item.querySelectorAll('.build-card-wrapper__info__ul__subinfo__options__item__line');
                        
                        if (nameElement) {
                            const name = nameElement.textContent.trim();
                            const values = Array.from(optionsElements).map(el => el.textContent.trim()).filter(v => v);
                            
                            console.log(`Элемент ${index}: name='${name}', values=[${values.join(', ')}]`);
                            
                            if (name && values.length > 0) {
                                result.push({
                                    name: name,
                                    values: values
                                });
                            }
                        }
                    });
                    
                    console.log(`Извлечено ${result.length} записей`);
                    return result;
                }
            """)
            
            logger.info(f"Извлечено {len(data)} записей о правах и ограничениях")
            if data:
                logger.debug(f"Извлеченные данные: {data}")
            return data
            
        except Exception as e:
            logger.error(f"Ошибка при извлечении данных о правах и ограничениях: {e}")
            raise RosreestrLKError(f"Не удалось извлечь данные: {str(e)}")
    
    def print_rights_table(self, rights_data: list[dict]) -> None:
        """
        Выводит данные о правах и ограничениях в виде таблицы в терминал.
        
        Args:
            rights_data: Список словарей с данными
        """
        if not rights_data:
            print("\n" + "=" * 80)
            print("Данные о правах и ограничениях не найдены")
            print("=" * 80)
            return
        
        print("\n" + "=" * 80)
        print("СВЕДЕНИЯ О ПРАВАХ И ОГРАНИЧЕНИЯХ (ОБРЕМЕНЕНИЯХ)")
        print("=" * 80)
        
        for idx, item in enumerate(rights_data, 1):
            print(f"\n{idx}. {item['name']}")
            print("-" * 80)
            for value in item['values']:
                print(f"   {value}")
        
        print("\n" + "=" * 80)
    
    async def recognize_captcha(self, captcha_path: Optional[Path] = None) -> Optional[str]:
        """
        Распознает текст с изображения капчи.
        
        Args:
            captcha_path: Путь к изображению капчи. Если не указан, используется последнее сохраненное.
        
        Returns:
            Распознанный текст или None при ошибке
        """
        try:
            if captcha_path is None:
                from bot.config.settings import settings
                captcha_path = settings.DATA_DIR / "output" / "captcha.png"
            
            if not captcha_path.exists():
                logger.warning(f"Файл капчи не найден: {captcha_path}")
                return None
            
            logger.info(f"Распознавание капчи из файла: {captcha_path}")
            
            if self._use_llm and self._llm_recognizer:
                # Используем LLM для распознавания
                text = await self._llm_recognizer.recognize(captcha_path)
            else:
                # Используем Tesseract
                text = self._recognizer.recognize(captcha_path)
            
            return text
            
        except Exception as e:
            logger.error(f"Ошибка при распознавании капчи: {e}")
            raise RosreestrLKError(f"Не удалось распознать капчу: {str(e)}")
    
    async def get_and_recognize_captcha(self, save_path: Optional[Path] = None) -> tuple[Optional[Path], Optional[str]]:
        """
        Получает изображение капчи и сразу распознает его.
        
        Args:
            save_path: Путь для сохранения изображения. Если не указан, создается автоматически.
        
        Returns:
            Кортеж (путь к файлу, распознанный текст) или (None, None) при ошибке
        """
        try:
            # Получаем изображение капчи
            captcha_path = await self.get_captcha_image(save_path)
            
            if not captcha_path:
                return None, None
            
            # Распознаем текст
            text = await self.recognize_captcha(captcha_path)
            
            return captcha_path, text
            
        except Exception as e:
            logger.error(f"Ошибка при получении и распознавании капчи: {e}")
            raise RosreestrLKError(f"Не удалось получить и распознать капчу: {str(e)}")
    
    async def navigate_to_search_page(self) -> bool:
        """
        Возвращается на страницу поиска для обработки следующего объекта.
        
        Returns:
            True если успешно, False иначе
        """
        try:
            logger.debug("Возврат на страницу поиска...")
            
            # Проверяем, что браузер инициализирован
            if self._page is None:
                logger.warning("Браузер не инициализирован, открываем страницу заново")
                return await self.open_lk_page()
            
            # Проверяем, что страница еще жива
            try:
                # Пробуем получить URL текущей страницы
                current_url = self._page.url
                if "real-estate-objects-online" in current_url:
                    # Уже на странице поиска, просто обновляем
                    await self._page.reload(wait_until="domcontentloaded", timeout=30000)
                else:
                    # Переходим на страницу поиска
                    await self._page.goto(self.LK_URL, wait_until="domcontentloaded", timeout=30000)
            except Exception as e:
                logger.warning(f"Страница недоступна, перезапускаем браузер: {e}")
                await self.restart_browser()
                return await self.open_lk_page()
            
            # Ждем загрузки страницы
            await self._page.wait_for_load_state("networkidle", timeout=10000)
            
            # Прокручиваем к форме
            await self.scroll_to_form()
            
            logger.debug("Успешно вернулись на страницу поиска")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при возврате на страницу поиска: {e}")
            # Пытаемся перезапустить браузер
            try:
                await self.restart_browser()
                return await self.open_lk_page()
            except Exception as restart_error:
                logger.error(f"Не удалось перезапустить браузер: {restart_error}")
                return False
    
    async def restart_browser(self) -> bool:
        """
        Перезапускает контекст браузера (создает новый контекст и страницу).
        Используется при ошибках сессии. Браузер остается общим.
        
        Returns:
            True если успешно, False иначе
        """
        try:
            logger.info("Перезапуск контекста браузера...")
            
            # Закрываем текущий контекст (браузер остается открытым)
            if self._context:
                try:
                    await self._context.close()
                except Exception as e:
                    logger.warning(f"Ошибка при закрытии контекста: {e}")
            
            # Очищаем ссылки на контекст и страницу
            self._context = None
            self._page = None
            
            # Получаем общий браузер и создаем новый контекст
            from bot.services.browser_manager import get_browser_manager
            browser_manager = await get_browser_manager()
            self._browser = await browser_manager.get_browser()
            
            # Создаем новый контекст
            self._context = await browser_manager.create_context(
                ignore_https_errors=True,
                viewport={"width": 1920, "height": 1080}
            )
            
            # Создаем новую страницу
            self._page = await self._context.new_page()
            
            # Устанавливаем заголовки
            await self._page.set_extra_http_headers({"Accept-Language": "ru-RU,ru;q=0.9"})
            
            logger.info("Контекст браузера успешно перезапущен")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при перезапуске контекста: {e}")
            # Очищаем ссылки
            self._browser = None
            self._context = None
            self._page = None
            return False
    
    async def close(self):
        """Закрывает контекст и освобождает ресурсы (браузер остается открытым для других сервисов)."""
        if self._context:
            try:
                await self._context.close()
                self._context = None
                logger.debug("Контекст RosreestrLKClient закрыт")
            except Exception as e:
                logger.warning(f"Ошибка при закрытии контекста: {e}")
        
        # НЕ закрываем браузер - он общий и используется другими сервисами
        # Браузер закроется только при закрытии BrowserManager
        self._browser = None
        self._page = None
        self._playwright = None  # Больше не храним ссылку на playwright
        
        # Закрываем LLM распознаватель если используется
        if self._llm_recognizer:
            try:
                await self._llm_recognizer.close()
            except Exception as e:
                logger.warning(f"Ошибка при закрытии LLM распознавателя: {e}")
    
    @property
    def page(self):
        """Получить объект страницы Playwright."""
        if self._page is None:
            raise RosreestrLKError("Браузер не инициализирован. Вызовите open_lk_page() сначала.")
        return self._page
    
    async def __aenter__(self):
        """Поддержка async context manager."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Поддержка async context manager."""
        await self.close()
