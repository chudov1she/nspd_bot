"""
Обработчик загрузки файлов с кадастровыми номерами для Росреестра.
"""
from pathlib import Path
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from loguru import logger

from bot.utils.auth import is_user_allowed, get_or_create_user
from bot.keyboards.menu import get_cancel_keyboard
from bot.services.parser import (
    extract_cadastral_numbers_from_excel,
    CadastralParserError,
)
from bot.services.task_service import create_task, update_task_file_path
from bot.services.queue import get_task_queue
from bot.config.settings import settings
from bot.database.models import TaskType


async def handle_file_upload(message: Message, state: FSMContext) -> None:
    """
    Обрабатывает загрузку файла с кадастровыми номерами.
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
    
    if not message.document:
        await message.answer(
            "❌ Пожалуйста, загрузите XLS или XLSX файл.",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    # Проверяем расширение файла
    file_name = message.document.file_name or ""
    if not file_name.lower().endswith(('.xlsx', '.xls')):
        await message.answer(
            "❌ <b>Неподдерживаемый формат файла</b>\n\n"
            "Пожалуйста, загрузите файл в формате <b>XLS</b> или <b>XLSX</b>.",
            reply_markup=get_cancel_keyboard(),
            parse_mode="HTML"
        )
        return
    
    file_path = None
    try:
        # Создаем задачу в БД
        task = await create_task(
            user_id=user_id,
            task_type=TaskType.FILE_UPLOAD,
            input_data=file_name
        )
        
        # Скачиваем файл
        file_info = await message.bot.get_file(message.document.file_id)
        input_dir = settings.INPUT_DIR
        input_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = input_dir / file_name
        await message.bot.download_file(file_info.file_path, destination=file_path)
        
        # Обновляем задачу с путем к файлу
        await update_task_file_path(task.id, input_file_path=str(file_path))
        
        logger.info(f"Файл {file_name} скачан от пользователя {user_id}")
        
        # Парсим кадастровые номера из файла
        numbers = extract_cadastral_numbers_from_excel(file_path)
        
        if not numbers:
            await message.answer(
                "❌ <b>Кадастровые номера не найдены в файле</b>\n\n"
                "Бот ищет кадастровые номера во всех ячейках всех листов файла.\n\n"
                "💡 <b>Проверьте:</b>\n"
                "• Файл содержит кадастровые номера в формате <code>XX:XX:XXXXXXX:XXXX</code>\n"
                "• Номера находятся в любых ячейках (не обязательно в отдельной колонке)\n"
                "• Формат файла: XLS или XLSX",
                reply_markup=get_cancel_keyboard(),
                parse_mode="HTML"
            )
            # Удаляем файл если номера не найдены
            try:
                if file_path.exists():
                    file_path.unlink()
            except Exception as e:
                logger.warning(f"Не удалось удалить файл {file_path}: {e}")
            return
        
        # Обновляем задачу с номерами
        from bot.services.task_service import update_task_cadastral_numbers
        await update_task_cadastral_numbers(task.id, numbers)
        
        # Добавляем задачу в очередь
        queue = get_task_queue()
        queue_position = await queue.add_task(task.id)
        
        # Уведомляем пользователя
        numbers_text = "номер" if len(numbers) == 1 else "номеров"
        queue_text = "Обработка начнется сразу" if queue_position == 1 else f"В очереди: #{queue_position}"
        
        await message.answer(
            f"✅ <b>Задача принята!</b>\n\n"
            f"🆔 <b>Номер задачи:</b> #{task.id}\n"
            f"📎 <b>Файл:</b> {file_name}\n"
            f"📊 <b>Найдено:</b> {len(numbers)} {numbers_text}\n"
            f"📍 <b>Позиция в очереди:</b> {queue_text}\n\n"
            f"⏳ Обработка начнется автоматически. Вы получите уведомление когда задача будет выполнена.",
            parse_mode="HTML"
        )
        
        logger.info(
            f"Задача {task.id} добавлена в очередь пользователем {user_id}, "
            f"файл: {file_name}, номеров: {len(numbers)}, позиция: {queue_position}"
        )
            
    except CadastralParserError as e:
        logger.error(f"Ошибка парсинга файла от {user_id}: {e}")
        await message.answer(
            f"❌ Ошибка: {str(e)}",
            reply_markup=get_cancel_keyboard(),
            parse_mode="HTML"
        )
        # Удаляем файл при ошибке
        try:
            if file_path and file_path.exists():
                file_path.unlink()
        except Exception as e:
            logger.warning(f"Не удалось удалить файл {file_path}: {e}")
    except Exception as e:
        logger.error(f"Ошибка при обработке файла от {user_id}: {e}", exc_info=True)
        await message.answer(
            f"❌ Ошибка: {str(e)}",
            reply_markup=get_cancel_keyboard(),
            parse_mode="HTML"
        )
        # Удаляем файл при ошибке
        try:
            if file_path and file_path.exists():
                file_path.unlink()
        except Exception as e:
            logger.warning(f"Не удалось удалить файл {file_path}: {e}")
