"""
Точка входа для запуска бота.
Запуск: python run.py
"""
import asyncio
import sys
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from loguru import logger

from bot.config.settings import settings
from bot.utils.logger import setup_logger
from bot.handlers import register_handlers
from bot.database.base import init_db, close_db
from bot.services.api_client import close_api_client
from bot.services.map_generator import close_map_generator
from bot.services.rosreestr_lk import close_lk_client
from bot.services.browser_manager import close_browser_manager
from bot.services.worker import get_task_worker


async def main() -> None:
    """Главная функция для запуска бота."""
    # Настройка логирования
    setup_logger()
    
    # Валидация настроек
    settings.validate()
    
    logger.info("🚀 Запуск бота...")
    
    # Инициализация базы данных
    await init_db()
    
    # Инициализация администраторов из .env
    from bot.utils.auth import init_admins_from_env
    await init_admins_from_env()
    
    # Инициализация FSM storage
    storage = MemoryStorage()
    
    # Инициализация бота и диспетчера
    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
    dp = Dispatcher(storage=storage)
    
    # Регистрация обработчиков
    register_handlers(dp)
    logger.info("✅ Обработчики зарегистрированы")
    
    # Запуск воркера для обработки задач из очереди
    worker = get_task_worker(bot)
    await worker.start()
    logger.info("✅ Воркер задач запущен")
    
    try:
        logger.info("✅ Бот запущен и готов к работе")
        logger.info("💡 Нажмите Ctrl+C для остановки")
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        logger.info("⏹ Получен сигнал прерывания (Ctrl+C), завершаю работу...")
    except asyncio.CancelledError:
        logger.info("⏹ Получен запрос на отмену, завершаю работу...")
    except Exception as e:
        logger.error(f"❌ Ошибка при работе бота: {e}", exc_info=True)
    finally:
        # Корректное завершение
        logger.info("🔄 Закрываю соединения...")
        
        # Останавливаем polling (если еще не остановлен)
        try:
            if dp._polling:
                await dp.stop_polling()
        except (AttributeError, Exception):
            pass
        
        # Закрываем диспетчер
        try:
            await dp.fsm.storage.close()
        except (AttributeError, Exception):
            pass
        
        # Закрываем сессию бота
        try:
            await bot.session.close()
        except Exception as e:
            logger.debug(f"Ошибка при закрытии сессии бота: {e}")
        
        # Закрываем БД
        try:
            await close_db()
        except Exception as e:
            logger.debug(f"Ошибка при закрытии БД: {e}")
        
        # Останавливаем воркер
        try:
            worker = get_task_worker(bot)
            await worker.stop()
        except Exception as e:
            logger.debug(f"Ошибка при остановке воркера: {e}")
        
        # Закрываем API клиент
        try:
            await close_api_client()
        except Exception as e:
            logger.debug(f"Ошибка при закрытии API клиента: {e}")
        
        # Закрываем генератор карт (закрывает только свой контекст, браузер остается)
        try:
            await close_map_generator()
        except Exception as e:
            logger.debug(f"Ошибка при закрытии генератора карт: {e}")
        
        # Закрываем клиент личного кабинета Росреестра (закрывает только свой контекст, браузер остается)
        try:
            await close_lk_client()
        except Exception as e:
            logger.debug(f"Ошибка при закрытии клиента ЛК: {e}")
        
        # Закрываем общий менеджер браузера (последним, так как он используется другими сервисами)
        # Это закроет общий браузер для всех сервисов
        try:
            await close_browser_manager()
        except Exception as e:
            logger.debug(f"Ошибка при закрытии менеджера браузера: {e}")
        
        logger.info("👋 Бот успешно остановлен")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # Дополнительная обработка на случай, если исключение не было поймано
        logger.info("👋 Завершение работы...")
        sys.exit(0)

