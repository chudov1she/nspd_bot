"""
Обработчик команды /start.
"""
from aiogram import Dispatcher
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from loguru import logger

from bot.utils.auth import get_or_create_user, is_user_allowed
from bot.states.menu import MenuStates
from bot.keyboards.menu import get_main_menu_keyboard


async def start_handler(message: Message, state: FSMContext) -> None:
    """Обработчик команды /start."""
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name
    
    # Регистрируем или обновляем пользователя в БД
    user = await get_or_create_user(
        telegram_id=user_id,
        username=username,
        first_name=first_name,
        last_name=last_name
    )
    
    # Проверка доступа (только администраторы)
    if not await is_user_allowed(user_id):
        await message.answer(
            "❌ <b>Доступ ограничен</b>\n\n"
            "Доступ к боту имеют только администраторы.\n\n"
            "Обратитесь к администратору для получения прав доступа.",
            parse_mode="HTML"
        )
        return
    
    # Очищаем предыдущее состояние
    await state.clear()
    await state.set_state(MenuStates.main_menu)
    
    # Приветственное сообщение (кратко)
    await message.answer(
        "🏠 <b>Главное меню</b>\n\n👇 Выберите нужный раздел:",
        reply_markup=get_main_menu_keyboard(),
        parse_mode="HTML"
    )
    logger.info(f"Пользователь {user_id} (@{username}) использовал команду /start")


def register_start_handler(dp: Dispatcher) -> None:
    """Регистрирует обработчик команды /start."""
    dp.message.register(start_handler, Command("start"))
