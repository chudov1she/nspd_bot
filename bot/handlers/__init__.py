"""
Обработчики команд и сообщений бота.
"""
from aiogram import Dispatcher

from .start import register_start_handler
from .router import register_router
from .admin import register_admin_handlers
from .menu import register_menu_handlers


def register_handlers(dp: Dispatcher) -> None:
    """Регистрирует все обработчики."""
    register_start_handler(dp)
    register_menu_handlers(dp)
    register_router(dp)
    register_admin_handlers(dp)

