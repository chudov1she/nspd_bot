"""
Скрипт для проверки распознавания кадастровых номеров.
Тестирует валидацию и парсинг различных форматов кадастровых номеров.
"""
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from bot.utils.validators import (
    is_valid_cadastral_number,
    normalize_cadastral_number,
    CADASTRAL_PATTERN
)
from bot.services.parser import extract_cadastral_numbers_from_text


def test_cadastral_numbers():
    """Тестирует распознавание кадастровых номеров."""
    print("=" * 70)
    print("Тестирование распознавания кадастровых номеров")
    print("=" * 70)
    
    # Тестовые номера
    test_numbers = [
        # Стандартные номера
        "78:38:0022629:1115",
        "78:38:0022629:1006",
        "78:31:0001521:3148",
        
        # Проблемный номер (6 цифр в третьей части)
        "29:22:000000:2425",
        # Номера с 7 цифрами в третьей части
        "78:38:00226297:1006",
        "78:31:00015217:3148",
        "29:22:0000007:2425",
        # Номера с пробелами
        "78:38:0022629:1115 ",
        " 78:38:0022629:1115",
        "78:38:0022629:1115 ",
        
        # Номера в тексте
        "Кадастровый номер: 78:38:0022629:1115",
        "Участок 29:22:000000:2425 находится в районе",
        "Номера: 78:38:0022629:1115, 78:38:0022629:1006, 29:22:000000:2425",
        
        # Невалидные номера
        "78:38:0022629",  # Неполный
        "78:38:0022629:11",  # Слишком короткая четвертая часть
        "invalid",
        "78:38:00262:1115",  # Слишком короткая третья часть (5 цифр)
    ]
    
    print("\n1. Проверка валидации отдельных номеров:")
    print("-" * 70)
    
    valid_count = 0
    invalid_count = 0
    
    for number in test_numbers:
        is_valid = is_valid_cadastral_number(number)
        normalized = normalize_cadastral_number(number)
        status = "[OK] ВАЛИДЕН" if is_valid else "[X] НЕВАЛИДЕН"
        
        print(f"{status:15} | {number:40} | Нормализован: {normalized or 'N/A'}")
        
        if is_valid:
            valid_count += 1
        else:
            invalid_count += 1
    
    print(f"\nИтого: {valid_count} валидных, {invalid_count} невалидных")
    
    print("\n" + "=" * 70)
    print("2. Проверка извлечения номеров из текста:")
    print("-" * 70)
    
    test_texts = [
        "Кадастровый номер участка: 78:38:0022629:1115",
        "Участки: 78:38:0022629:1115, 78:38:0022629:1006",
        "Номер 29:22:000000:2425 и еще 78:31:0001521:3148",
        "Список: 78:38:0022629:1115; 29:22:000000:2425; 78:38:0022629:1006",
        "Один номер 78:38:0022629:1115 в тексте",
    ]
    
    for text in test_texts:
        extracted = extract_cadastral_numbers_from_text(text)
        print(f"\nТекст: {text}")
        print(f"Извлечено: {extracted}")
        print(f"Количество: {len(extracted)}")
    
    print("\n" + "=" * 70)
    print("3. Проверка проблемного номера 29:22:000000:2425:")
    print("-" * 70)
    
    problem_number = "29:22:000000:2425"
    is_valid_problem = is_valid_cadastral_number(problem_number)
    normalized_problem = normalize_cadastral_number(problem_number)
    
    print(f"Номер: {problem_number}")
    print(f"Валиден: {'ДА' if is_valid_problem else 'НЕТ'}")
    print(f"Нормализован: {normalized_problem}")
    
    # Проверка паттерна напрямую
    import re
    pattern = re.compile(r'\d{2}:\d{2}:\d{6,}:\d{4,}')
    match = pattern.search(problem_number)
    print(f"Паттерн поиска: {'Найден' if match else 'Не найден'}")
    
    print("\n" + "=" * 70)
    print("Тестирование завершено")
    print("=" * 70)


if __name__ == "__main__":
    try:
        test_cadastral_numbers()
    except Exception as e:
        print(f"\nОШИБКА при тестировании: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
