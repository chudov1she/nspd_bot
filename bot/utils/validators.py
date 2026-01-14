"""
Валидаторы для кадастровых номеров и других данных.
"""
import re
from typing import Optional

# Паттерн для поиска кадастрового номера в тексте (без якорей начала/конца строки)
# Формат: XX:XX:XXXXXXX:XX-XXXXXXX (третья часть минимум 6 цифр, четвертая от 1 до 7 цифр)
CADASTRAL_PATTERN = re.compile(r'\d{2}:\d{2}:\d{6,}:\d{1,7}')

# Паттерн для валидации полного кадастрового номера (с якорями)
# Формат: XX:XX:XXXXXXX:XX-XXXXXXX (третья часть минимум 6 цифр, четвертая от 1 до 7 цифр)
CADASTRAL_VALIDATION_PATTERN = re.compile(r'^\d{2}:\d{2}:\d{6,}:\d{1,7}$')


def is_valid_cadastral_number(number: str) -> bool:
    """
    Проверяет, является ли строка валидным кадастровым номером.
    
    Args:
        number: Строка для проверки
        
    Returns:
        True если номер валиден, False иначе
        
    Examples:
        >>> is_valid_cadastral_number("78:38:0022629:1115")
        True
        >>> is_valid_cadastral_number("22:61:020713:45")
        True
        >>> is_valid_cadastral_number("22:61:020713:455")
        True
        >>> is_valid_cadastral_number("invalid")
        False
    """
    if not number or not isinstance(number, str):
        return False
    
    # Убираем пробелы
    number = number.strip()
    
    return bool(CADASTRAL_VALIDATION_PATTERN.match(number))


def normalize_cadastral_number(number: str) -> Optional[str]:
    """
    Нормализует кадастровый номер (убирает пробелы, приводит к стандартному виду).
    
    Args:
        number: Кадастровый номер для нормализации
        
    Returns:
        Нормализованный номер или None если невалиден
    """
    if not number:
        return None
    
    # Убираем все пробелы
    normalized = str(number).strip().replace(" ", "")
    
    if is_valid_cadastral_number(normalized):
        return normalized
    
    return None

