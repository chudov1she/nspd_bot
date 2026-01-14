"""
Современные клавиатуры меню бота.
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Главное меню бота - компактное и удобное."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🏠 Росреестр выгрузка",
                    callback_data="menu:rosreestr"
                ),
                InlineKeyboardButton(
                    text="📊 Отчетность компании выгрузка",
                    callback_data="menu:company_report"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🚗 ПТС выгрузка",
                    callback_data="menu:pts"
                ),
                InlineKeyboardButton(
                    text="📋 Задачи",
                    callback_data="menu:my_tasks"
                )
            ]
        ]
    )
    return keyboard


def get_rosreestr_menu_keyboard() -> InlineKeyboardMarkup:
    """Меню Росреестр - удобные кнопки."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✍️ Ввести текст",
                    callback_data="rosreestr:text_input"
                ),
                InlineKeyboardButton(
                    text="📎 Загрузить файл",
                    callback_data="rosreestr:file_upload"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🏠 Главное меню",
                    callback_data="menu:back_to_main"
                )
            ]
        ]
    )
    return keyboard


def get_back_to_main_keyboard() -> InlineKeyboardMarkup:
    """Кнопка возврата в главное меню."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🏠 Главное меню",
                    callback_data="menu:back_to_main"
                )
            ]
        ]
    )
    return keyboard


def get_cancel_keyboard() -> InlineKeyboardMarkup:
    """Кнопка отмены операции."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📋 Меню",
                    callback_data="menu:back_to_main"
                )
            ]
        ]
    )
    return keyboard


def get_my_tasks_keyboard(
    tasks,
    page: int = 0,
    total_pages: int = 1
) -> InlineKeyboardMarkup:
    """
    Клавиатура для страницы 'Мои задачи' с кнопками задач и пагинацией.
    
    Args:
        tasks: Список задач для отображения
        page: Текущая страница (0-indexed)
        total_pages: Общее количество страниц
    """
    buttons = []
    
    # Добавляем кнопки для каждой задачи
    for task in tasks:
        task_type_emoji = "📝" if task.task_type.value == "text_input" else "📎"
        # Добавляем эмодзи статуса
        status_emoji = "✅" if task.status.value == "completed" else "❌"
        buttons.append([
            InlineKeyboardButton(
                text=f"{status_emoji} {task_type_emoji} Задача #{task.id}",
                callback_data=f"task:view:{task.id}"
            )
        ])
    
    # Кнопки пагинации
    pagination_buttons = []
    if total_pages > 1:
        if page > 0:
            pagination_buttons.append(
                InlineKeyboardButton(
                    text="◀️ Назад",
                    callback_data=f"tasks:page:{page - 1}"
                )
            )
        if page < total_pages - 1:
            pagination_buttons.append(
                InlineKeyboardButton(
                    text="Вперед ▶️",
                    callback_data=f"tasks:page:{page + 1}"
                )
            )
        if pagination_buttons:
            buttons.append(pagination_buttons)
    
    # Кнопка возврата в главное меню
    buttons.append([
        InlineKeyboardButton(
            text="📋 Меню",
            callback_data="menu:back_to_main"
        )
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    return keyboard
