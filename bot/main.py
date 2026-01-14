"""
Главный файл для запуска Telegram бота.
"""
import asyncio
from aiogram import Bot, Dispatcher
from loguru import logger

from bot.config.settings import settings
from bot.utils.logger import setup_logger
from bot.handlers import register_handlers


async def main() -> None:
    """Главная функция для запуска бота."""
    # Настройка логирования
    setup_logger()
    
    # Валидация настроек
    settings.validate()
    
    logger.info("🚀 Запуск бота...")
    
    # Инициализация бота и диспетчера
    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
    dp = Dispatcher()
    
    # Регистрация обработчиков
    register_handlers(dp)
    logger.info("✅ Обработчики зарегистрированы")
    
    try:
        logger.info("✅ Бот запущен и готов к работе")
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        logger.info("⏹ Остановка бота по запросу пользователя")
    except Exception as e:
        logger.error(f"❌ Ошибка при работе бота: {e}", exc_info=True)
    finally:
        await bot.session.close()
        logger.info("👋 Бот остановлен")


if __name__ == "__main__":
    asyncio.run(main())
