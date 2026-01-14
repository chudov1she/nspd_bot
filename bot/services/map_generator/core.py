"""
Основной класс генератора карт с инициализацией браузера.
"""
from pathlib import Path
from typing import Optional
from loguru import logger

from typing import TYPE_CHECKING

from bot.services.map_generator.exceptions import MapGeneratorError
from bot.services.map_generator.navigation import NavigationHandler
from bot.services.map_generator.click_handler import ClickHandler
from bot.services.map_generator.screenshot import ScreenshotHandler

if TYPE_CHECKING:
    from bot.services.map_generator.generator import MapGeneratorService


class MapGenerator:
    """Генератор карт земельных участков с сайта nspd.gov.ru."""
    
    # Базовый URL картографического сервиса
    NSPD_MAP_URL = "https://nspd.gov.ru/map"
    
    def __init__(self):
        self._browser = None
        self._context = None
        self._page = None
        self._navigation = None
        self._click_handler = None
        self._screenshot_handler = None
        self._service = None
    
    async def _init_browser(self):
        """Инициализирует браузер Playwright."""
        try:
            from playwright.async_api import async_playwright
            
            if self._browser is None:
                playwright = await async_playwright().start()
                # Используем Chrome (рекомендуется сайтом nspd.gov.ru)
                self._browser = await playwright.chromium.launch(
                    headless=False,
                    channel="chrome"  # Используем установленный Chrome, если есть
                )
                # Создаем контекст с игнорированием SSL ошибок
                self._context = await self._browser.new_context(
                    ignore_https_errors=True
                )
                self._page = await self._context.new_page()
                # Устанавливаем размер окна (увеличиваем для большего масштаба карты)
                await self._page.set_viewport_size({"width": 1920, "height": 1080})
                # Устанавливаем масштаб страницы (zoom out для более широкого обзора)
                await self._page.set_extra_http_headers({"Accept-Language": "ru-RU,ru;q=0.9"})
                logger.debug("Браузер Playwright (Chrome) инициализирован")
                
                # Инициализируем обработчики
                self._navigation = NavigationHandler(self._page)
                self._click_handler = ClickHandler(self._page)
                self._screenshot_handler = ScreenshotHandler()
                # Импортируем сервис здесь, чтобы избежать циклического импорта
                from bot.services.map_generator.generator import MapGeneratorService
                self._service = MapGeneratorService(self)
        except ImportError:
            raise MapGeneratorError(
                "Playwright не установлен. Установите: pip install playwright && playwright install chromium"
            )
        except Exception as e:
            logger.error(f"Ошибка инициализации браузера: {e}")
            raise MapGeneratorError(f"Не удалось инициализировать браузер: {str(e)}")
    
    async def close(self):
        """Закрывает браузер и освобождает ресурсы."""
        if self._context:
            try:
                await self._context.close()
                self._context = None
            except Exception as e:
                logger.warning(f"Ошибка при закрытии контекста: {e}")
        
        if self._browser:
            try:
                await self._browser.close()
                self._browser = None
                self._page = None
                self._navigation = None
                self._click_handler = None
                self._screenshot_handler = None
                self._service = None
                logger.debug("Браузер Playwright закрыт")
            except Exception as e:
                logger.warning(f"Ошибка при закрытии браузера: {e}")
    
    @property
    def page(self):
        """Получить объект страницы Playwright."""
        return self._page
    
    @property
    def navigation(self) -> NavigationHandler:
        """Получить обработчик навигации."""
        if self._navigation is None:
            raise MapGeneratorError("Браузер не инициализирован")
        return self._navigation
    
    @property
    def click_handler(self) -> ClickHandler:
        """Получить обработчик кликов."""
        if self._click_handler is None:
            raise MapGeneratorError("Браузер не инициализирован")
        return self._click_handler
    
    @property
    def screenshot_handler(self) -> ScreenshotHandler:
        """Получить обработчик скриншотов."""
        if self._screenshot_handler is None:
            raise MapGeneratorError("Браузер не инициализирован")
        return self._screenshot_handler
    
    async def generate_map(
        self,
        cadastral_number: str,
        coordinates: Optional[dict] = None,
        output_dir: Optional[Path] = None
    ) -> Optional[Path]:
        """Генерирует карту земельного участка (поиск по кадастровому номеру)."""
        if self._service is None:
            from bot.services.map_generator.generator import MapGeneratorService
            self._service = MapGeneratorService(self)
        return await self._service.generate_map(cadastral_number, coordinates, output_dir)
    
    async def generate_map_batch(
        self,
        land_plots: list,
        output_dir: Optional[Path] = None
    ) -> dict:
        """Генерирует карты для нескольких земельных участков."""
        if self._service is None:
            from bot.services.map_generator.generator import MapGeneratorService
            self._service = MapGeneratorService(self)
        return await self._service.generate_map_batch(land_plots, output_dir)

