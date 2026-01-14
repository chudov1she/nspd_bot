"""
Базовые настройки для работы с базой данных.
"""
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.orm import declarative_base
from pathlib import Path
from loguru import logger

from bot.config.settings import settings

# URL базы данных SQLite
DATABASE_URL = f"sqlite+aiosqlite:///{settings.BASE_DIR / 'bot.db'}"

# Создание асинхронного движка
engine = create_async_engine(
    DATABASE_URL,
    echo=False,  # Установите True для отладки SQL запросов
    future=True,
)

# Фабрика сессий
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Базовый класс для моделей
Base = declarative_base()


def get_session() -> AsyncSession:
    """
    Получить сессию базы данных.
    
    Usage:
        async with get_session() as session:
            # работа с БД
    """
    return async_session_maker()


async def init_db() -> None:
    """Инициализация базы данных - создание всех таблиц."""
    logger.info("Инициализация базы данных...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("✅ База данных инициализирована")


async def close_db() -> None:
    """Закрытие соединения с базой данных."""
    logger.info("Закрытие соединения с базой данных...")
    await engine.dispose()
    logger.info("✅ Соединение с базой данных закрыто")

