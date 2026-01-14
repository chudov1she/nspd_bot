"""
Тест всех возможных форматов кадастровых номеров.
"""
import sys
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from bot.utils.validators import (
    is_valid_cadastral_number,
    normalize_cadastral_number,
    CADASTRAL_PATTERN
)
from bot.services.parser import extract_cadastral_numbers_from_text


def test_all_formats():
    """Тестирует все возможные форматы кадастровых номеров."""
    print("=" * 80)
    print("Тестирование всех форматов кадастровых номеров")
    print("=" * 80)
    
    test_cases = [
        # Стандартный формат (двоеточия)
        ("78:38:0022629:1115", True, "Стандартный формат"),
        ("29:22:000000:2425", True, "С 6 цифрами в третьей части"),
        
        # С пробелами вокруг разделителей
        ("78 : 38 : 0022629 : 1115", False, "С пробелами (прямая валидация не пройдет)"),
        ("78:38:0022629:1115 ", True, "С пробелом в конце"),
        (" 78:38:0022629:1115", True, "С пробелом в начале"),
        ("  78:38:0022629:1115  ", True, "С пробелами с обеих сторон"),
        
        # Старый формат (дефисы вместо двоеточий)
        ("78-38-0022629-1115", False, "Старый формат с дефисами"),
        ("29-22-000000-2425", False, "Старый формат с дефисами (6 цифр)"),
        
        # В тексте
        ("Кадастровый номер 78:38:0022629:1115", False, "В тексте (прямая валидация)"),
        ("Участок №78:38:0022629:1115", False, "В тексте с символом №"),
        ("78:38:0022629:1115 - это номер", False, "В тексте с дефисом"),
        
        # Разные разделители
        ("78/38/0022629/1115", False, "Слеши вместо двоеточий"),
        ("78.38.0022629.1115", False, "Точки вместо двоеточий"),
        
        # Неполные
        ("78:38:0022629", False, "Неполный номер"),
        ("78:38:0022629:11", False, "Короткая четвертая часть"),
        ("78:38:00262:1115", False, "Короткая третья часть (5 цифр)"),
    ]
    
    print("\n1. Прямая валидация (is_valid_cadastral_number):")
    print("-" * 80)
    for number, expected, description in test_cases:
        result = is_valid_cadastral_number(number)
        status = "OK" if result == expected else "FAIL"
        print(f"[{status:4}] {description:40} | {number:40} | Валиден: {result}")
    
    print("\n" + "=" * 80)
    print("2. Извлечение из текста (extract_cadastral_numbers_from_text):")
    print("-" * 80)
    
    text_cases = [
        "Номер 78:38:0022629:1115 в тексте",
        "Участок 29:22:000000:2425 находится здесь",
        "Список: 78:38:0022629:1115, 78:38:0022629:1006",
        "Кадастровый номер участка: 78:38:0022629:1115",
        "Номера 78:38:0022629:1115 и 29:22:000000:2425",
        "78:38:0022629:1115 - это кадастровый номер",
        "Номер №78:38:0022629:1115",
        "С пробелами: 78 : 38 : 0022629 : 1115",  # С пробелами вокруг разделителей
        "Старый формат: 78-38-0022629-1115",  # Дефисы
    ]
    
    for text in text_cases:
        extracted = extract_cadastral_numbers_from_text(text)
        print(f"\nТекст: {text}")
        print(f"Извлечено: {extracted} ({len(extracted)} номеров)")
    
    print("\n" + "=" * 80)
    print("3. Проверка нормализации:")
    print("-" * 80)
    
    normalize_tests = [
        "78:38:0022629:1115",
        " 78:38:0022629:1115 ",
        "78:38:0022629:1115  ",
        "  78:38:0022629:1115",
    ]
    
    for number in normalize_tests:
        normalized = normalize_cadastral_number(number)
        print(f"'{number}' -> '{normalized}'")
    
    print("\n" + "=" * 80)
    print("4. Проверка паттерна поиска (CADASTRAL_PATTERN):")
    print("-" * 80)
    
    pattern_tests = [
        "78:38:0022629:1115",
        "29:22:000000:2425",
        "Кадастровый номер: 78:38:0022629:1115",
        "Участок 29:22:000000:2425 находится",
        "78 : 38 : 0022629 : 1115",  # С пробелами
        "78-38-0022629-1115",  # Дефисы
    ]
    
    for text in pattern_tests:
        matches = CADASTRAL_PATTERN.findall(text)
        print(f"Текст: {text}")
        print(f"Найдено паттерном: {matches}")
        print()


if __name__ == "__main__":
    try:
        test_all_formats()
    except Exception as e:
        print(f"\nОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
