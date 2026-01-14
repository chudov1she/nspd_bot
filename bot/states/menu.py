"""
Состояния меню бота.
"""
from aiogram.fsm.state import State, StatesGroup


class MenuStates(StatesGroup):
    """Состояния главного меню."""
    
    # Главное меню
    main_menu = State()
    
    # Росреестр выгрузка
    rosreestr_menu = State()
    rosreestr_text_input = State()  # Ожидание текста с кадастровыми номерами
    rosreestr_file_upload = State()  # Ожидание загрузки XLS файла
    
    # Отчетность компании (на будущее)
    company_report_menu = State()
    
    # ПТС выгрузка (на будущее)
    pts_menu = State()

