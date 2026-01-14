"""
Обработчики команд для администраторов.
"""
from aiogram import Dispatcher
from aiogram.filters import Command
from aiogram.types import Message
from loguru import logger
from datetime import datetime

from bot.utils.auth import is_user_admin, set_user_admin
from bot.database.models import User, Task, TaskStatus
from bot.database.base import async_session_maker
from bot.services.task_service import get_all_tasks, get_task_statistics
from sqlalchemy import select


async def admin_list_handler(message: Message) -> None:
    """Показать список администраторов."""
    if not await is_user_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return
    
    async with async_session_maker() as session:
        stmt = select(User).where(User.is_admin == True)
        result = await session.execute(stmt)
        admins = result.scalars().all()
    
    if not admins:
        await message.answer("📋 Администраторы не найдены.")
        return
    
    admin_list = "📋 Список администраторов:\n\n"
    for admin in admins:
        username = f"@{admin.username}" if admin.username else "без username"
        admin_list += f"• {admin.first_name or ''} {admin.last_name or ''} ({username})\n"
        admin_list += f"  ID: {admin.telegram_id}\n\n"
    
    await message.answer(admin_list)


async def admin_add_handler(message: Message) -> None:
    """Добавить администратора."""
    if not await is_user_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return
    
    # Парсим ID из команды: /admin_add 123456789
    try:
        parts = message.text.split()
        if len(parts) < 2:
            await message.answer("❌ Использование: /admin_add <telegram_id>")
            return
        
        telegram_id = int(parts[1])
        success = await set_user_admin(telegram_id, is_admin=True)
        
        if success:
            await message.answer(f"✅ Пользователь {telegram_id} добавлен в администраторы.")
        else:
            await message.answer(f"❌ Пользователь {telegram_id} не найден в базе данных.")
    except ValueError:
        await message.answer("❌ Неверный формат ID. Используйте числовой ID.")
    except Exception as e:
        logger.error(f"Ошибка при добавлении администратора: {e}")
        await message.answer("❌ Произошла ошибка при добавлении администратора.")


async def admin_remove_handler(message: Message) -> None:
    """Удалить администратора."""
    if not await is_user_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return
    
    # Парсим ID из команды: /admin_remove 123456789
    try:
        parts = message.text.split()
        if len(parts) < 2:
            await message.answer("❌ Использование: /admin_remove <telegram_id>")
            return
        
        telegram_id = int(parts[1])
        
        # Нельзя удалить самого себя
        if telegram_id == message.from_user.id:
            await message.answer("❌ Вы не можете удалить себя из администраторов.")
            return
        
        success = await set_user_admin(telegram_id, is_admin=False)
        
        if success:
            await message.answer(f"✅ Пользователь {telegram_id} удален из администраторов.")
        else:
            await message.answer(f"❌ Пользователь {telegram_id} не найден в базе данных.")
    except ValueError:
        await message.answer("❌ Неверный формат ID. Используйте числовой ID.")
    except Exception as e:
        logger.error(f"Ошибка при удалении администратора: {e}")
        await message.answer("❌ Произошла ошибка при удалении администратора.")


async def tasks_history_handler(message: Message) -> None:
    """Показать историю задач."""
    if not await is_user_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return
    
    # Получаем статистику
    stats = await get_task_statistics()
    
    # Получаем последние задачи
    tasks = await get_all_tasks(limit=10)
    
    if not tasks:
        await message.answer("📋 История задач пуста.")
        return
    
    text = (
        f"📊 <b>Статистика задач</b>\n\n"
        f"Всего задач: <b>{stats['total']}</b>\n"
        f"Успешно: <b>{stats['completed']}</b>\n"
        f"С ошибками: <b>{stats['failed']}</b>\n"
        f"Успешность: <b>{stats['success_rate']:.1f}%</b>\n\n"
        f"<b>Последние 10 задач:</b>\n\n"
    )
    
    for task in tasks:
        status_emoji = {
            TaskStatus.COMPLETED: "✅",
            TaskStatus.FAILED: "❌",
            TaskStatus.PROCESSING: "⏳",
            TaskStatus.PENDING: "⏸",
            TaskStatus.CANCELLED: "🚫"
        }.get(task.status, "❓")
        
        task_type_emoji = "📝" if task.task_type == "text_input" else "📎"
        
        created_time = task.created_at.strftime("%d.%m.%Y %H:%M") if task.created_at else "N/A"
        
        text += (
            f"{status_emoji} {task_type_emoji} <b>Задача #{task.id}</b>\n"
            f"Пользователь: <code>{task.user_id}</code>\n"
            f"Статус: <b>{task.status.value}</b>\n"
            f"Обработано: {task.successful_count}/{task.processed_count}\n"
            f"Создана: {created_time}\n\n"
        )
    
    await message.answer(text, parse_mode="HTML")


async def my_tasks_handler(message: Message) -> None:
    """Показать мои задачи."""
    user_id = message.from_user.id
    
    from bot.services.task_service import get_user_tasks
    tasks = await get_user_tasks(user_id, limit=10)
    
    if not tasks:
        await message.answer("📋 У вас пока нет задач.")
        return
    
    text = f"📋 <b>Ваши последние задачи:</b>\n\n"
    
    for task in tasks:
        status_emoji = {
            TaskStatus.COMPLETED: "✅",
            TaskStatus.FAILED: "❌",
            TaskStatus.PROCESSING: "⏳",
            TaskStatus.PENDING: "⏸",
            TaskStatus.CANCELLED: "🚫"
        }.get(task.status, "❓")
        
        task_type_emoji = "📝" if task.task_type == "text_input" else "📎"
        
        created_time = task.created_at.strftime("%d.%m.%Y %H:%M") if task.created_at else "N/A"
        
        text += (
            f"{status_emoji} {task_type_emoji} <b>Задача #{task.id}</b>\n"
            f"Статус: <b>{task.status.value}</b>\n"
            f"Обработано: {task.successful_count}/{task.processed_count}\n"
            f"Создана: {created_time}\n\n"
        )
    
    await message.answer(text, parse_mode="HTML")


def register_admin_handlers(dp: Dispatcher) -> None:
    """Регистрирует обработчики команд администратора."""
    dp.message.register(admin_list_handler, Command("admin_list"))
    dp.message.register(admin_add_handler, Command("admin_add"))
    dp.message.register(admin_remove_handler, Command("admin_remove"))
    dp.message.register(tasks_history_handler, Command("tasks_history"))
    dp.message.register(my_tasks_handler, Command("my_tasks"))

