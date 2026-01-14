"""
Настройка логирования через loguru.
"""
import sys
from loguru import logger
from bot.config.settings import settings


def setup_logger() -> None:
    """Настраивает логирование через loguru."""
    
    # Удаляем стандартный обработчик
    logger.remove()
    
    # Консольный вывод с цветами
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=settings.LOG_LEVEL,
        colorize=True,
    )
    
    # Файловый вывод
    logger.add(
        settings.LOG_FILE,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level=settings.LOG_LEVEL,
        rotation=settings.LOG_ROTATION,
        retention=settings.LOG_RETENTION,
        compression="zip",
        encoding="utf-8",
    )
    
    logger.info("Логирование настроено")


# Экспорт настроенного логгера
__all__ = ["logger", "setup_logger"]

