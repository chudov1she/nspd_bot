"""
Утилиты для работы с датой и временем в московском часовом поясе.
"""
from datetime import datetime, timezone, timedelta

# Пытаемся использовать zoneinfo, если не работает - используем pytz
try:
    from zoneinfo import ZoneInfo
    try:
        MOSCOW_TZ = ZoneInfo("Europe/Moscow")
    except Exception:
        # Если zoneinfo не может загрузить timezone (например, на Windows без tzdata)
        import pytz
        MOSCOW_TZ = pytz.timezone("Europe/Moscow")
except ImportError:
    # zoneinfo недоступен (Python < 3.9)
    import pytz
    MOSCOW_TZ = pytz.timezone("Europe/Moscow")


def now_moscow() -> datetime:
    """
    Возвращает текущее время в московском часовом поясе.
    
    Returns:
        datetime объект с московским временем
    """
    return datetime.now(MOSCOW_TZ)


def strftime_moscow(format_str: str) -> str:
    """
    Форматирует текущее московское время по заданному формату.
    
    Args:
        format_str: Строка формата для strftime
        
    Returns:
        Отформатированная строка с московским временем
    """
    return now_moscow().strftime(format_str)

