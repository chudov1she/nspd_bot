"""
Обработчик навигации и поиска на сайте nspd.gov.ru.
"""
import asyncio
from pathlib import Path
from typing import Optional
from loguru import logger

from bot.services.map_generator.exceptions import MapGeneratorError


class NavigationHandler:
    """Обработчик навигации по сайту nspd.gov.ru."""
    
    NSPD_MAP_URL = "https://nspd.gov.ru/map"
    
    def __init__(self, page):
        self._page = page
    
    async def open_map_page(self):
        """Открывает главную страницу карты."""
        logger.debug(f"Открываем страницу: {self.NSPD_MAP_URL}")
        # Увеличиваем таймаут для серверов (60 секунд)
        await self._page.goto(self.NSPD_MAP_URL, wait_until="networkidle", timeout=60000)
        # Дополнительное ожидание для полной загрузки страницы на сервере
        await asyncio.sleep(2)
        await self._close_modal_if_exists()
    
    async def _close_modal_if_exists(self):
        """Закрывает модальное окно с предупреждением о браузере, если оно появилось."""
        try:
            close_button = await self._page.wait_for_selector(
                "button:has-text('Закрыть'), .close-button, [aria-label='Закрыть'], .modal-close, button.close",
                timeout=3000
            )
            if close_button:
                await close_button.click()
                logger.debug("Закрыто модальное окно с предупреждением о браузере")
                await asyncio.sleep(1)
        except Exception:
            logger.debug("Модальное окно не найдено или уже закрыто")
    
    async def search_cadastral_number(self, cadastral_number: str):
        """
        Ищет кадастровый номер на странице.
        
        Args:
            cadastral_number: Кадастровый номер для поиска
            
        Raises:
            MapGeneratorError: При ошибках поиска
        """
        logger.debug("Ищем поле поиска...")
        try:
            # Увеличиваем таймаут для серверов (30 секунд вместо 10)
            # На серверах страница может загружаться медленнее
            search_input = await self._page.wait_for_selector(
                ".input-label input, label.input-label input, m-search-field input, form input[placeholder]",
                timeout=30000  # Увеличено с 10000 до 30000 (30 секунд)
            )
            
            if search_input:
                # Дополнительное ожидание для полной загрузки элемента
                await asyncio.sleep(1)
                
                # Кликаем на поле и очищаем его
                await search_input.click()
                await asyncio.sleep(0.5)  # Увеличено с 0.3 до 0.5
                
                # Очищаем поле (Ctrl+A и Delete)
                await search_input.press("Control+a")
                await asyncio.sleep(0.3)  # Увеличено с 0.2 до 0.3
                
                # Вводим кадастровый номер с задержкой
                await search_input.type(cadastral_number, delay=100)  # Увеличено с 50 до 100
                logger.debug(f"Введен кадастровый номер: {cadastral_number}")
                await asyncio.sleep(1.5)  # Увеличено с 1 до 1.5
                
                # Ищем и нажимаем кнопку поиска
                await self._click_search_button(search_input)
            else:
                raise Exception("Поле поиска не найдено")
                
        except Exception as e:
            logger.error(f"Ошибка при вводе кадастрового номера: {e}")
            raise MapGeneratorError(f"Не удалось ввести кадастровый номер в поиск: {str(e)}")
    
    async def _click_search_button(self, search_input):
        """Нажимает кнопку поиска или Enter."""
        try:
            search_button = await self._page.wait_for_selector(
                "form m-button[type='submit'], form button[type='submit'], m-button[variant='filled'][type='submit']",
                timeout=3000
            )
            if search_button:
                await search_button.click()
                logger.debug("Нажата кнопка поиска")
                await asyncio.sleep(2)
            else:
                # Пробуем нажать Enter в поле ввода
                await search_input.press("Enter")
                logger.debug("Нажат Enter для поиска")
                await asyncio.sleep(2)
        except Exception as e:
            logger.warning(f"Не удалось найти кнопку поиска, пробуем Enter: {e}")
            await search_input.press("Enter")
            await asyncio.sleep(2)
    
    async def wait_for_search_results(self, timeout: int = 45000):
        """
        Ждет появления результатов поиска.
        
        Args:
            timeout: Таймаут ожидания в миллисекундах
        """
        logger.debug("Ожидаем результаты поиска...")
        try:
            await self._page.wait_for_selector(
                ".accordion-container, .accordion-count, m-accordion",
                timeout=timeout
            )
            logger.debug("Результаты поиска появились")
            await asyncio.sleep(2)  # Дополнительное ожидание для полной загрузки
        except Exception as e:
            logger.warning(f"Результаты поиска не появились за отведенное время: {e}")
    
    async def save_debug_html(self, output_dir: Path, safe_cadastral: str):
        """
        Сохраняет HTML страницы и shadow DOM для отладки.
        
        Args:
            output_dir: Директория для сохранения
            safe_cadastral: Безопасное имя файла (без двоеточий)
        """
        try:
            html_content = await self._page.content()
            debug_html_file = output_dir / f"{safe_cadastral}_debug.html"
            with open(debug_html_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
            logger.info(f"📄 HTML страницы сохранен для отладки: {debug_html_file}")
            
            # Также сохраняем HTML shadow DOM для анализа
            shadow_html = await self._page.evaluate("""
                () => {
                    const accordions = document.querySelectorAll('m-accordion');
                    let result = [];
                    accordions.forEach((accordion, index) => {
                        const shadowRoot = accordion.shadowRoot;
                        if (shadowRoot) {
                            result.push({
                                index: index,
                                html: shadowRoot.innerHTML
                            });
                        }
                    });
                    return result;
                }
            """)
            if shadow_html:
                shadow_file = output_dir / f"{safe_cadastral}_shadow_dom.html"
                with open(shadow_file, 'w', encoding='utf-8') as f:
                    f.write("<!-- Shadow DOM содержимое -->\n")
                    for item in shadow_html:
                        f.write(f"\n<!-- Accordion {item['index']} -->\n")
                        f.write(item['html'])
                        f.write("\n")
                logger.info(f"📄 Shadow DOM сохранен: {shadow_file}")
        except Exception as e:
            logger.warning(f"Не удалось сохранить HTML для отладки: {e}")
    
    async def wait_for_map_load(self, timeout: int = 45000):
        """
        Ждет загрузки карты.
        
        Args:
            timeout: Таймаут ожидания в миллисекундах
        """
        logger.debug("Ожидаем загрузку карты...")
        try:
            await self._page.wait_for_selector(
                "canvas, .leaflet-container, .map-container, #map, [class*='map']",
                timeout=timeout
            )
            # Дополнительное ожидание для полной загрузки карты
            await asyncio.sleep(3)
            logger.debug("Карта загружена")
        except Exception as e:
            logger.warning(f"Карта не загрузилась за отведенное время: {e}")
            # Продолжаем - возможно карта уже загружена

