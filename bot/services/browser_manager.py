"""
Общий менеджер браузера для всех сервисов.
Обеспечивает использование одного экземпляра браузера Playwright.
"""
import os
import platform
from typing import Optional
from loguru import logger

from playwright.async_api import Browser, BrowserContext, Playwright, Page


class BrowserManager:
    """Менеджер общего браузера Playwright для всех сервисов."""
    
    _instance: Optional['BrowserManager'] = None
    _playwright: Optional[Playwright] = None
    _browser: Optional[Browser] = None
    
    def __init__(self):
        """Приватный конструктор (singleton)."""
        if BrowserManager._instance is not None:
            raise RuntimeError("BrowserManager - это singleton. Используйте get_browser_manager()")
        BrowserManager._instance = self
    
    @classmethod
    async def get_instance(cls) -> 'BrowserManager':
        """Получить экземпляр менеджера браузера (singleton)."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    async def get_browser(self) -> Browser:
        """
        Получить общий экземпляр браузера.
        Создает браузер при первом вызове.
        
        Returns:
            Экземпляр браузера Playwright
        """
        if self._browser is None:
            await self._init_browser()
        return self._browser
    
    async def _init_browser(self):
        """Инициализирует браузер Playwright."""
        try:
            from playwright.async_api import async_playwright
            
            # Проверка DISPLAY на Linux (headless=False требует графический интерфейс)
            if platform.system() == "Linux" and not os.getenv("DISPLAY"):
                logger.warning(
                    "⚠️ DISPLAY не установлен! Браузеру нужен графический интерфейс.\n"
                    "Для Linux сервера используйте Xvfb:\n"
                    "  1. Установите: sudo apt-get install -y xvfb\n"
                    "  2. Запустите: xvfb-run -a python run.py\n"
                    "Или настройте systemd с Xvfb (см. README)"
                )
            
            if self._playwright is None:
                self._playwright = await async_playwright().start()
                logger.debug("Playwright инициализирован")
            
            if self._browser is None:
                # Используем Chromium (установленный через playwright install chromium)
                # headless=False - требуется графический интерфейс (Xvfb на Linux серверах)
                self._browser = await self._playwright.chromium.launch(
                    headless=False
                )
                logger.info("Общий браузер Playwright (Chromium) инициализирован")
                
        except ImportError:
            raise RuntimeError(
                "Playwright не установлен. Установите: pip install playwright && playwright install chromium"
            )
        except Exception as e:
            logger.error(f"Ошибка инициализации браузера: {e}")
            raise RuntimeError(f"Не удалось инициализировать браузер: {str(e)}")
    
    async def create_context(self, **kwargs) -> BrowserContext:
        """
        Создает новый контекст браузера.
        
        Args:
            **kwargs: Параметры для создания контекста (viewport, ignore_https_errors и т.д.)
        
        Returns:
            Новый контекст браузера
        """
        browser = await self.get_browser()
        
        # Устанавливаем значения по умолчанию
        context_options = {
            "ignore_https_errors": True,
            **kwargs
        }
        
        # Если viewport не указан, устанавливаем по умолчанию
        if "viewport" not in context_options:
            context_options["viewport"] = {"width": 1920, "height": 1080}
        
        context = await browser.new_context(**context_options)
        logger.debug("Создан новый контекст браузера")
        return context
    
    async def close(self):
        """Закрывает браузер и освобождает ресурсы."""
        if self._browser:
            try:
                await self._browser.close()
                self._browser = None
                logger.info("Общий браузер закрыт")
            except Exception as e:
                logger.warning(f"Ошибка при закрытии браузера: {e}")
        
        if self._playwright:
            try:
                await self._playwright.stop()
                self._playwright = None
                logger.debug("Playwright остановлен")
            except Exception as e:
                logger.warning(f"Ошибка при остановке Playwright: {e}")
        
        BrowserManager._instance = None


# Глобальные функции для удобства
_browser_manager: Optional[BrowserManager] = None


async def get_browser_manager() -> BrowserManager:
    """Получить глобальный экземпляр менеджера браузера."""
    global _browser_manager
    if _browser_manager is None:
        _browser_manager = await BrowserManager.get_instance()
    return _browser_manager


async def close_browser_manager():
    """Закрыть глобальный менеджер браузера."""
    global _browser_manager
    if _browser_manager:
        await _browser_manager.close()
        _browser_manager = None
