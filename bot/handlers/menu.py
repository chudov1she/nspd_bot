"""
Обработчики меню бота.
"""
from aiogram import Dispatcher
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from loguru import logger

from bot.states.menu import MenuStates
from bot.keyboards.menu import (
    get_main_menu_keyboard,
    get_rosreestr_menu_keyboard,
    get_back_to_main_keyboard,
    get_cancel_keyboard,
    get_my_tasks_keyboard,
)
from bot.utils.auth import is_user_allowed
from bot.services.task_service import get_user_tasks, get_task_by_id
from pathlib import Path
from aiogram.types import FSInputFile


async def menu_handler(message: Message, state: FSMContext) -> None:
    """Обработчик команды /menu - показывает главное меню."""
    user_id = message.from_user.id
    
    # Проверка доступа (только администраторы)
    if not await is_user_allowed(user_id):
        await message.answer(
            "❌ <b>Доступ ограничен</b>\n\n"
            "Доступ к боту имеют только администраторы.\n\n"
            "Обратитесь к администратору для получения прав доступа.",
            parse_mode="HTML"
        )
        return
    
    # Устанавливаем состояние главного меню
    await state.set_state(MenuStates.main_menu)
    
    text = (
        "🏠 <b>Главное меню</b>\n\n"
        "👇 Выберите нужный раздел:"
    )
    
    await message.answer(
        text,
        reply_markup=get_main_menu_keyboard(),
        parse_mode="HTML"
    )
    logger.info(f"Пользователь {user_id} открыл главное меню")


async def callback_main_menu(callback: CallbackQuery, state: FSMContext) -> None:
    """Обработчик возврата в главное меню."""
    await state.set_state(MenuStates.main_menu)
    
    text = (
        "🏠 <b>Главное меню</b>\n\n"
        "👇 Выберите нужный раздел:"
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=get_main_menu_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()
    logger.info(f"Пользователь {callback.from_user.id} вернулся в главное меню")


async def callback_rosreestr_menu(callback: CallbackQuery, state: FSMContext) -> None:
    """Обработчик перехода в меню Росреестр."""
    await state.set_state(MenuStates.rosreestr_menu)
    
    text = (
        "🏠 <b>Росреестр</b>\n\n"
        "📋 <b>Выберите способ ввода:</b>\n\n"
        "🔹 <b>Ввести текст</b>\n"
        "   Отправьте кадастровые номера текстом\n"
        "   (один или несколько через запятую)\n\n"
        "🔹 <b>Загрузить файл</b>\n"
        "   Загрузите Excel файл с кадастровыми номерами\n"
        "   (номера будут найдены автоматически во всех ячейках)"
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=get_rosreestr_menu_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()
    logger.info(f"Пользователь {callback.from_user.id} открыл меню Росреестр")


async def callback_rosreestr_text_input(callback: CallbackQuery, state: FSMContext) -> None:
    """Обработчик выбора ввода текста для Росреестра."""
    await state.set_state(MenuStates.rosreestr_text_input)
    
    text = (
        "✍️ <b>Ввод кадастровых номеров</b>\n\n"
        "📝 Отправьте кадастровые номера текстом\n"
        "   (один или несколько через запятую)"
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()
    logger.info(f"Пользователь {callback.from_user.id} выбрал ввод текста для Росреестра")


async def callback_rosreestr_file_upload(callback: CallbackQuery, state: FSMContext) -> None:
    """Обработчик выбора загрузки файла для Росреестра."""
    await state.set_state(MenuStates.rosreestr_file_upload)
    
    text = (
        "📎 <b>Загрузка файла</b>\n\n"
        "📋 <b>Требования к файлу:</b>\n"
        "• Формат: <b>XLS</b> или <b>XLSX</b>\n"
        "• Кадастровые номера могут быть в любых ячейках\n"
        "• Бот найдет все номера автоматически\n\n"
        "📤 <b>Отправьте файл:</b>\n"
        "   Просто загрузите файл в этот чат\n\n"
        "✅ <b>После обработки:</b>\n"
        "   Вы получите файл с заполненными данными из Росреестра"
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()
    logger.info(f"Пользователь {callback.from_user.id} выбрал загрузку файла для Росреестра")


async def callback_company_report_menu(callback: CallbackQuery, state: FSMContext) -> None:
    """Обработчик меню отчетности компании (пока не реализовано)."""
    await state.set_state(MenuStates.company_report_menu)
    
    text = (
        "📊 <b>Отчетность компании</b>\n\n"
        "⏳ <b>В разработке</b>\n\n"
        "Этот функционал скоро будет доступен.\n"
        "Следите за обновлениями!"
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=get_back_to_main_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer("⏳ Функционал в разработке", show_alert=True)
    logger.info(f"Пользователь {callback.from_user.id} открыл меню отчетности компании")


async def callback_pts_menu(callback: CallbackQuery, state: FSMContext) -> None:
    """Обработчик меню ПТС выгрузка (пока не реализовано)."""
    await state.set_state(MenuStates.pts_menu)
    
    text = (
        "🚗 <b>ПТС выгрузка</b>\n\n"
        "⏳ <b>В разработке</b>\n\n"
        "Этот функционал скоро будет доступен.\n"
        "Следите за обновлениями!"
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=get_back_to_main_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer("⏳ Функционал в разработке", show_alert=True)
    logger.info(f"Пользователь {callback.from_user.id} открыл меню ПТС")


async def callback_my_tasks(callback: CallbackQuery, state: FSMContext) -> None:
    """Обработчик просмотра задач (все завершенные задачи с пагинацией)."""
    user_id = callback.from_user.id
    
    try:
        from bot.services.task_service import get_all_completed_tasks
        
        # Получаем первую страницу всех завершенных задач
        tasks, total_count = await get_all_completed_tasks(offset=0, limit=5)
        
        if not tasks:
            text = (
                "📋 <b>Задачи</b>\n\n"
                "Нет завершенных задач."
            )
            keyboard = get_back_to_main_keyboard()
        else:
            # Вычисляем количество страниц
            total_pages = (total_count + 4) // 5  # 5 задач на страницу
            
            text = f"📋 <b>Задачи</b>\n\n"
            text += f"📊 Всего задач: <b>{total_count}</b>\n"
            if total_pages > 1:
                text += f"📄 Страница 1 из {total_pages}\n"
            text += "\n👇 Выберите задачу для просмотра:"
            
            # Создаём клавиатуру с кнопками задач и пагинацией
            keyboard = get_my_tasks_keyboard(tasks, page=0, total_pages=total_pages)
        
        await callback.message.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка при просмотре задач пользователя {user_id}: {e}", exc_info=True)
        await callback.answer("❌ Ошибка при загрузке задач", show_alert=True)


async def callback_tasks_page(callback: CallbackQuery, state: FSMContext) -> None:
    """Обработчик пагинации задач."""
    user_id = callback.from_user.id
    
    try:
        # Извлекаем номер страницы из callback_data (формат: "tasks:page:1")
        page = int(callback.data.split(":")[-1])
        
        from bot.services.task_service import get_all_completed_tasks
        
        # Получаем задачи для указанной страницы
        limit = 5
        offset = page * limit
        tasks, total_count = await get_all_completed_tasks(offset=offset, limit=limit)
        
        if not tasks:
            await callback.answer("Нет задач на этой странице", show_alert=True)
            return
        
        # Вычисляем количество страниц
        total_pages = (total_count + limit - 1) // limit
        
        text = f"📋 <b>Задачи</b>\n\n"
        text += f"📊 Всего задач: <b>{total_count}</b> (успешные и с ошибками)\n"
        if total_pages > 1:
            text += f"📄 Страница {page + 1} из {total_pages}\n"
        text += "\n👇 Выберите задачу для просмотра:"
        
        # Создаём клавиатуру с кнопками задач и пагинацией
        keyboard = get_my_tasks_keyboard(tasks, page=page, total_pages=total_pages)
        
        await callback.message.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка при пагинации задач пользователя {user_id}: {e}", exc_info=True)
        await callback.answer("❌ Ошибка при загрузке страницы", show_alert=True)


async def callback_task_view(callback: CallbackQuery, state: FSMContext) -> None:
    """Обработчик просмотра деталей задачи."""
    user_id = callback.from_user.id
    
    try:
        # Извлекаем ID задачи из callback_data (формат: "task:view:123")
        task_id = int(callback.data.split(":")[-1])
        
        from bot.services.task_service import get_task_by_id
        
        # Получаем задачу (без фильтрации по пользователю, так как показываем все задачи)
        task = await get_task_by_id(task_id, user_id=None)
        
        if not task:
            await callback.answer("❌ Задача не найдена", show_alert=True)
            return
        
        # Формируем детальную сводку
        task_type_emoji = "📝" if task.task_type.value == "text_input" else "📎"
        
        import json
        cadastral_count = 0
        if task.cadastral_numbers:
            try:
                numbers = json.loads(task.cadastral_numbers)
                cadastral_count = len(numbers) if isinstance(numbers, list) else 0
            except:
                pass
        
        # Форматируем даты
        from datetime import datetime
        created_str = ""
        if task.created_at:
            if isinstance(task.created_at, str):
                created_str = task.created_at[:10]
            else:
                created_str = task.created_at.strftime('%d.%m.%Y %H:%M')
        
        completed_str = ""
        if task.completed_at:
            if isinstance(task.completed_at, str):
                completed_str = task.completed_at[:10]
            else:
                completed_str = task.completed_at.strftime('%d.%m.%Y %H:%M')
        
        # Время выполнения
        duration_str = ""
        if task.started_at and task.completed_at:
            if not isinstance(task.started_at, str) and not isinstance(task.completed_at, str):
                duration = task.completed_at - task.started_at
                total_seconds = int(duration.total_seconds())
                minutes = total_seconds // 60
                seconds = total_seconds % 60
                if minutes > 0:
                    duration_str = f"{minutes} мин {seconds} сек"
                else:
                    duration_str = f"{seconds} сек"
        
        text = f"{task_type_emoji} <b>Задача #{task.id}</b>\n\n"
        
        # Тип задачи
        task_type_text = "Ввод текста" if task.task_type.value == "text_input" else "Загрузка файла"
        text += f"📋 Тип: <b>{task_type_text}</b>\n"
        
        # Количество номеров
        if cadastral_count > 0:
            text += f"📊 Номеров: <b>{cadastral_count}</b>\n"
        
        # Статистика обработки
        if task.processed_count > 0:
            text += f"✅ Успешно: <b>{task.successful_count}</b>\n"
            if task.failed_count > 0:
                text += f"❌ С ошибками: <b>{task.failed_count}</b>\n"
            text += f"📈 Всего обработано: <b>{task.processed_count}</b>\n"
        
        # Баланс API
        if task.api_balance:
            try:
                balance = float(task.api_balance)
                text += f"💰 Баланс API: <b>{balance:,.2f}</b> руб.\n"
            except:
                pass
        
        # Время
        if created_str:
            text += f"📅 Создана: {created_str}\n"
        if completed_str:
            text += f"✅ Завершена: {completed_str}\n"
        if duration_str:
            text += f"⏱ Время выполнения: {duration_str}\n"
        
        # Ошибка
        if task.error_message:
            text += f"\n⚠️ <b>Ошибка:</b>\n<code>{task.error_message}</code>\n"
        
        # Кнопка возврата к списку задач
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="◀️ К списку задач",
                        callback_data="menu:my_tasks"
                    )
                ]
            ]
        )
        
        await callback.message.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка при просмотре задачи {task_id} пользователем {user_id}: {e}", exc_info=True)
        await callback.answer("❌ Ошибка при загрузке задачи", show_alert=True)


async def callback_task_download(callback: CallbackQuery, state: FSMContext) -> None:
    """Обработчик скачивания результата задачи."""
    user_id = callback.from_user.id
    
    try:
        # Извлекаем ID задачи из callback_data (формат: "task:download:123")
        task_id_str = callback.data.split(":")[-1]
        task_id = int(task_id_str)
        
        # Получаем задачу
        task = await get_task_by_id(task_id, user_id=user_id)
        
        if not task:
            await callback.answer("❌ Задача не найдена", show_alert=True)
            return
        
        if task.status.value != "completed":
            await callback.answer("❌ Задача ещё не завершена", show_alert=True)
            return
        
        if not task.output_file_path:
            await callback.answer("❌ Файл результата не найден", show_alert=True)
            return
        
        # Проверяем существование файла
        file_path = Path(task.output_file_path)
        if not file_path.exists():
            await callback.answer("❌ Файл был удалён", show_alert=True)
            return
        
        # Отправляем файл
        document = FSInputFile(file_path)
        
        # Формируем подпись
        import json
        cadastral_count = 0
        if task.cadastral_numbers:
            try:
                numbers = json.loads(task.cadastral_numbers)
                cadastral_count = len(numbers) if isinstance(numbers, list) else 0
            except:
                pass
        
        caption = (
            f"✅ <b>Результат задачи #{task.id}</b>\n\n"
            f"📊 Обработано: <b>{task.successful_count}</b> из <b>{task.processed_count}</b>\n"
        )
        
        if task.failed_count > 0:
            caption += f"⚠️ С ошибками: <b>{task.failed_count}</b>\n"
        
        if task.api_balance:
            try:
                balance = float(task.api_balance)
                caption += f"💰 Баланс API: <b>{balance:,.2f}</b> руб.\n"
            except:
                pass
        
        await callback.message.answer_document(
            document=document,
            caption=caption,
            parse_mode="HTML"
        )
        
        await callback.answer("✅ Файл отправлен")
        
    except ValueError:
        await callback.answer("❌ Неверный ID задачи", show_alert=True)
    except Exception as e:
        logger.error(f"Ошибка при скачивании файла задачи {task_id_str if 'task_id_str' in locals() else 'unknown'}: {e}", exc_info=True)
        await callback.answer("❌ Ошибка при отправке файла", show_alert=True)


async def callback_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    """Обработчик отмены операции - возвращает на предыдущий шаг."""
    current_state = await state.get_state()
    
    # Определяем, куда вернуться в зависимости от текущего состояния
    if current_state == MenuStates.rosreestr_text_input:
        # Возвращаемся в меню Росреестра
        await state.set_state(MenuStates.rosreestr_menu)
        text = (
            "◀️ <b>Возврат в меню Росреестра</b>\n\n"
            "📋 <b>Выберите способ ввода:</b>\n\n"
            "🔹 <b>Ввести текст</b>\n"
            "   Отправьте кадастровые номера текстом\n"
            "   (один или несколько через запятую)\n\n"
            "🔹 <b>Загрузить файл</b>\n"
            "   Загрузите Excel файл с кадастровыми номерами\n"
            "   (номера будут найдены автоматически во всех ячейках)"
        )
        await callback.message.edit_text(
            text,
            reply_markup=get_rosreestr_menu_keyboard(),
            parse_mode="HTML"
        )
        await callback.answer("◀️ Возврат в меню")
        
    elif current_state == MenuStates.rosreestr_file_upload:
        # Возвращаемся в меню Росреестра
        await state.set_state(MenuStates.rosreestr_menu)
        text = (
            "◀️ <b>Возврат в меню Росреестра</b>\n\n"
            "📋 <b>Выберите способ ввода:</b>\n\n"
            "🔹 <b>Ввести текст</b>\n"
            "   Отправьте кадастровые номера текстом\n"
            "   (один или несколько через запятую)\n\n"
            "🔹 <b>Загрузить файл</b>\n"
            "   Загрузите Excel файл с кадастровыми номерами\n"
            "   (номера будут найдены автоматически во всех ячейках)"
        )
        await callback.message.edit_text(
            text,
            reply_markup=get_rosreestr_menu_keyboard(),
            parse_mode="HTML"
        )
        await callback.answer("◀️ Возврат в меню")
        
    elif current_state == MenuStates.rosreestr_menu:
        # Возвращаемся в главное меню
        await state.set_state(MenuStates.main_menu)
        text = (
            "🏠 <b>Главное меню</b>\n\n"
            "👇 Выберите нужный раздел:"
        )
        await callback.message.edit_text(
            text,
            reply_markup=get_main_menu_keyboard(),
            parse_mode="HTML"
        )
        await callback.answer("◀️ Возврат в главное меню")
        
    else:
        # Для всех остальных состояний - возврат в главное меню
        await state.set_state(MenuStates.main_menu)
        text = (
            "🏠 <b>Главное меню</b>\n\n"
            "👇 Выберите нужный раздел:"
        )
        await callback.message.edit_text(
            text,
            reply_markup=get_main_menu_keyboard(),
            parse_mode="HTML"
        )
        await callback.answer("◀️ Возврат в главное меню")
    
    logger.info(f"Пользователь {callback.from_user.id} отменил операцию из состояния {current_state}")


def register_menu_handlers(dp: Dispatcher) -> None:
    """Регистрирует обработчики меню."""
    # Команда /menu
    dp.message.register(menu_handler, Command("menu"))
    
    # Callback обработчики
    dp.callback_query.register(callback_main_menu, lambda c: c.data == "menu:back_to_main")
    dp.callback_query.register(callback_rosreestr_menu, lambda c: c.data == "menu:rosreestr")
    dp.callback_query.register(callback_rosreestr_text_input, lambda c: c.data == "rosreestr:text_input")
    dp.callback_query.register(callback_rosreestr_file_upload, lambda c: c.data == "rosreestr:file_upload")
    dp.callback_query.register(callback_company_report_menu, lambda c: c.data == "menu:company_report")
    dp.callback_query.register(callback_pts_menu, lambda c: c.data == "menu:pts")
    dp.callback_query.register(callback_my_tasks, lambda c: c.data == "menu:my_tasks")
    dp.callback_query.register(callback_cancel, lambda c: c.data == "menu:cancel")
    # Обработчики задач
    dp.callback_query.register(callback_task_download, lambda c: c.data and c.data.startswith("task:download:"))
    dp.callback_query.register(callback_task_view, lambda c: c.data and c.data.startswith("task:view:"))
    dp.callback_query.register(callback_tasks_page, lambda c: c.data and c.data.startswith("tasks:page:"))
