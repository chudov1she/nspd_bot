"""
Скрипт для добавления первого администратора в базу данных.
Использование: python scripts/add_admin.py <telegram_id>
"""
import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bot.database.base import init_db, async_session_maker
from bot.database.models import User
from bot.utils.auth import set_user_admin
from sqlalchemy import select
from loguru import logger


async def add_admin(telegram_id: int) -> None:
    """Добавить администратора в базу данных."""
    # Инициализация БД
    await init_db()
    
    async with async_session_maker() as session:
        # Проверяем, существует ли пользователь
        stmt = select(User).where(User.telegram_id == telegram_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        
        if user:
            # Обновляем существующего пользователя
            user.is_admin = True
            await session.commit()
            logger.info(f"✅ Пользователь {telegram_id} установлен как администратор")
        else:
            # Создаем нового пользователя-администратора
            user = User(
                telegram_id=telegram_id,
                username=None,
                first_name=None,
                last_name=None,
                is_admin=True
            )
            session.add(user)
            await session.commit()
            logger.info(f"✅ Создан новый администратор с ID {telegram_id}")


async def main() -> None:
    """Главная функция."""
    if len(sys.argv) < 2:
        print("Использование: python scripts/add_admin.py <telegram_id>")
        print("\nПример:")
        print("  python scripts/add_admin.py 123456789")
        sys.exit(1)
    
    try:
        telegram_id = int(sys.argv[1])
        await add_admin(telegram_id)
        print(f"\n✅ Администратор {telegram_id} успешно добавлен!")
    except ValueError:
        print("❌ Ошибка: telegram_id должен быть числом")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        print(f"❌ Произошла ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

