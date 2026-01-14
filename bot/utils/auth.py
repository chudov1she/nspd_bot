"""
Утилиты для авторизации и проверки доступа.
"""
from bot.database.models import User
from bot.database.base import async_session_maker
from loguru import logger
from sqlalchemy import select


async def get_or_create_user(telegram_id: int, username: str = None, 
                            first_name: str = None, last_name: str = None) -> User:
    """
    Получить пользователя из БД или создать нового.
    
    Args:
        telegram_id: ID пользователя Telegram
        username: Имя пользователя
        first_name: Имя
        last_name: Фамилия
        
    Returns:
        Объект User
    """
    async with async_session_maker() as session:
        # Поиск существующего пользователя
        stmt = select(User).where(User.telegram_id == telegram_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        
        if user:
            # Обновляем информацию о пользователе
            user.username = username
            user.first_name = first_name
            user.last_name = last_name
            await session.commit()
            await session.refresh(user)
            return user
        
        # Создаем нового пользователя
        user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            is_admin=False
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        logger.info(f"Создан новый пользователь: {telegram_id} (@{username})")
        return user


async def is_user_allowed(user_id: int) -> bool:
    """
    Проверяет, разрешен ли доступ пользователю.
    Только администраторы могут пользоваться ботом.
    
    Args:
        user_id: ID пользователя Telegram
        
    Returns:
        True если пользователь является администратором, False иначе
    """
    async with async_session_maker() as session:
        stmt = select(User).where(User.telegram_id == user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            logger.warning(f"Попытка доступа от неавторизованного пользователя: {user_id}")
            return False
        
        if not user.is_admin:
            logger.warning(f"Попытка доступа от пользователя без прав администратора: {user_id}")
            return False
        
        return True


async def is_user_admin(user_id: int) -> bool:
    """
    Проверяет, является ли пользователь администратором.
    
    Args:
        user_id: ID пользователя Telegram
        
    Returns:
        True если пользователь является администратором, False иначе
    """
    async with async_session_maker() as session:
        stmt = select(User).where(User.telegram_id == user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            return False
        
        return user.is_admin


async def set_user_admin(telegram_id: int, is_admin: bool = True) -> bool:
    """
    Устанавливает статус администратора для пользователя.
    
    Args:
        telegram_id: ID пользователя Telegram
        is_admin: Статус администратора
        
    Returns:
        True если операция успешна, False если пользователь не найден
    """
    async with async_session_maker() as session:
        stmt = select(User).where(User.telegram_id == telegram_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            return False
        
        user.is_admin = is_admin
        await session.commit()
        logger.info(f"Пользователь {telegram_id} установлен как {'администратор' if is_admin else 'обычный пользователь'}")
        return True


async def init_admins_from_env() -> None:
    """
    Инициализирует администраторов из переменной окружения ADMIN_IDS.
    Создает пользователей, если их нет, и устанавливает им статус администратора.
    """
    from bot.config.settings import settings
    
    admin_ids = settings.get_admin_ids()
    if not admin_ids:
        logger.debug("ADMIN_IDS не задан в .env, пропускаю инициализацию администраторов")
        return
    
    logger.info(f"Инициализация администраторов из .env: {admin_ids}")
    
    async with async_session_maker() as session:
        for telegram_id in admin_ids:
            stmt = select(User).where(User.telegram_id == telegram_id)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()
            
            if user:
                # Обновляем существующего пользователя
                if not user.is_admin:
                    user.is_admin = True
                    await session.commit()
                    logger.info(f"✅ Пользователь {telegram_id} установлен как администратор")
                else:
                    logger.debug(f"Пользователь {telegram_id} уже является администратором")
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
        
        logger.info(f"✅ Инициализация администраторов завершена: {len(admin_ids)} администраторов")

