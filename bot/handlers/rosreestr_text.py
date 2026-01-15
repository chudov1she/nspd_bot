"""
Обработчик текстового ввода кадастровых номеров для Росреестра.
"""
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from loguru import logger

from bot.utils.auth import is_user_allowed, get_or_create_user
from bot.keyboards.menu import get_cancel_keyboard
from bot.services.parser import extract_cadastral_numbers_from_text
from bot.services.task_service import create_task
from bot.services.queue import get_task_queue
from bot.database.models import TaskType


async def handle_text_input(message: Message, state: FSMContext) -> None:
    """
    Обрабатывает текстовый ввод с кадастровыми номерами.
    Добавляет задачу в очередь для обработки.
    
    Args:
        message: Сообщение от пользователя
        state: Контекст FSM
    """
    user_id = message.from_user.id
    
    # Регистрируем пользователя если его еще нет
    await get_or_create_user(
        telegram_id=user_id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name
    )
    
    # Проверка доступа
    if not await is_user_allowed(user_id):
        await message.answer(
            "❌ <b>Доступ ограничен</b>\n\n"
            "Доступ к боту имеют только администраторы.\n\n"
            "Обратитесь к администратору для получения прав доступа.",
            parse_mode="HTML"
        )
        return
    
    if not message.text:
        await message.answer(
            "❌ Пожалуйста, отправьте текстовое сообщение с кадастровыми номерами.",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    try:
        # Извлекаем кадастровые номера из текста
        numbers = extract_cadastral_numbers_from_text(message.text)
        
        if not numbers:
            await message.answer(
                "❌ <b>Кадастровые номера не найдены</b>\n\n"
                "Пожалуйста, отправьте текст с кадастровыми номерами в формате:\n"
                "<code>XX:XX:XXXXXXX:XXXX</code>\n\n"
                "📋 <b>Примеры:</b>\n"
                "• <code>78:38:0022629:1115</code>\n"
                "• <code>78:38:0022629:1115, 78:38:0022629:1006</code>\n"
                "• <code>78:38:0022629:1115\n78:38:0022629:1006</code>",
                reply_markup=get_cancel_keyboard(),
                parse_mode="HTML"
            )
            return
        
        # Создаем задачу в БД
        task = await create_task(
            user_id=user_id,
            task_type=TaskType.TEXT_INPUT,
            input_data=message.text[:500],  # Первые 500 символов
            cadastral_numbers=numbers
        )
        
        # Добавляем задачу в очередь
        queue = get_task_queue()
        queue_position = await queue.add_task(task.id)
        
        # Уведомляем пользователя
        numbers_text = "номер" if len(numbers) == 1 else "номеров"
        queue_text = "Обработка начнется сразу" if queue_position == 1 else f"В очереди: #{queue_position}"
        
        await message.answer(
            f"✅ <b>Задача принята!</b>\n\n"
            f"🆔 <b>Номер задачи:</b> #{task.id}\n"
            f"📊 <b>Найдено:</b> {len(numbers)} {numbers_text}\n"
            f"⏳ Обработка начнется автоматически. Вы получите уведомление когда задача будет выполнена.",
            parse_mode="HTML"
        )
        
        logger.info(
            f"Задача {task.id} добавлена в очередь пользователем {user_id}, "
            f"номеров: {len(numbers)}, позиция: {queue_position}"
        )
        
    except Exception as e:
        logger.error(f"Ошибка при обработке текста от {user_id}: {e}", exc_info=True)
        await message.answer(
            f"❌ Ошибка: {str(e)}",
            reply_markup=get_cancel_keyboard(),
            parse_mode="HTML"
        )
