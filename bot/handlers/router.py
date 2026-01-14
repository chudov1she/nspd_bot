"""
Роутер сообщений по состояниям FSM.
"""
from aiogram import Dispatcher
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from bot.utils.auth import is_user_allowed, get_or_create_user
from bot.states.menu import MenuStates
from bot.handlers.rosreestr_text import handle_text_input
from bot.handlers.rosreestr_file import handle_file_upload


async def message_router(message: Message, state: FSMContext) -> None:
    """
    Роутер сообщений по состояниям FSM.
    Направляет запросы к соответствующим обработчикам в зависимости от текущего состояния.
    """
    user_id = message.from_user.id
    current_state = await state.get_state()
    
    # Регистрируем пользователя если его еще нет
    await get_or_create_user(
        telegram_id=user_id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name
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
    
    # Роутинг по состояниям FSM
    if current_state == MenuStates.rosreestr_text_input:
        # Обработка текстового ввода
        await handle_text_input(message, state)
        return
    
    elif current_state == MenuStates.rosreestr_file_upload:
        # Обработка загрузки файла
        await handle_file_upload(message, state)
        return
    
    # Если не в состоянии обработки - показываем подсказку
    if message.text:
        await message.answer(
            "💡 Используйте команду /menu для открытия главного меню "
            "или /start для начала работы."
        )
    else:
        await message.answer(
            "💡 Используйте команду /menu для открытия главного меню."
        )


def register_router(dp: Dispatcher) -> None:
    """Регистрирует роутер сообщений."""
    dp.message.register(message_router)

