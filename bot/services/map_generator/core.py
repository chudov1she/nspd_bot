"""
Основной класс генератора карт с инициализацией браузера.
"""
import os
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
                
                logger.debug("Контекст и страница для MapGenerator созданы (используется общий браузер)")
                
                # Инициализируем обработчики
                self._navigation = NavigationHandler(self._page)
                self._click_handler = ClickHandler(self._page)
                self._screenshot_handler = ScreenshotHandler()
                # Импортируем сервис здесь, чтобы избежать циклического импорта
                from bot.services.map_generator.generator import MapGeneratorService
                self._service = MapGeneratorService(self)
        except ImportError as e:
            raise MapGeneratorError(
                f"Ошибка импорта: {e}. Установите: pip install playwright && playwright install chromium"
            )
        except Exception as e:
            logger.error(f"Ошибка инициализации браузера: {e}")
            raise MapGeneratorError(f"Не удалось инициализировать браузер: {str(e)}")
    
    async def close(self):
        """Закрывает контекст и освобождает ресурсы (браузер остается открытым для других сервисов)."""
        if self._context:
            try:
                await self._context.close()
                self._context = None
                logger.debug("Контекст MapGenerator закрыт")
            except Exception as e:
                logger.warning(f"Ошибка при закрытии контекста: {e}")
        
        # НЕ закрываем браузер - он общий и используется другими сервисами
        # Браузер закроется только при закрытии BrowserManager
        self._browser = None
        self._page = None
        self._navigation = None
        self._click_handler = None
        self._screenshot_handler = None
        self._service = None
    
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

