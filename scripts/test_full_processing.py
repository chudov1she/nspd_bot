"""
Тест полного цикла обработки кадастрового номера:
1. Распознавание из текста
2. Получение данных через API
3. Проверка типа объекта
4. Создание задачи на генерацию карты (если земельный участок)
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from bot.services.parser import extract_cadastral_numbers_from_text
from bot.services.api_client import get_api_client, APINotConfiguredError, APIConnectionError
from bot.services.map_task_service import create_map_task, get_map_task_by_cadastral
from bot.database.models import MapGenerationStatus, MapGenerationTask, Task, User  # Импорт моделей для создания таблиц
from bot.database.base import init_db
from bot.models.cadastral import RealEstateObject
from bot.config.settings import settings
from loguru import logger


async def test_full_processing():
    """Тестирует полный цикл обработки кадастрового номера."""
    print("=" * 80)
    print("Тест полного цикла обработки кадастрового номера")
    print("=" * 80)
    
    # Инициализация базы данных (создание таблиц если их нет)
    print("\n0. Инициализация базы данных:")
    print("-" * 80)
    try:
        await init_db()
        print("OK: База данных инициализирована")
    except Exception as e:
        print(f"ОШИБКА при инициализации БД: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Тестовый кадастровый номер
    test_cadastral = "78:38:0022629:1115"
    test_text = f"Кадастровый номер участка: {test_cadastral}"
    
    print(f"\n1. Распознавание кадастрового номера из текста:")
    print("-" * 80)
    print(f"Текст: {test_text}")
    
    # Шаг 1: Распознавание
    numbers = extract_cadastral_numbers_from_text(test_text)
    print(f"Извлечено номеров: {len(numbers)}")
    print(f"Номера: {numbers}")
    
    if not numbers:
        print("ОШИБКА: Кадастровый номер не распознан!")
        return
    
    if test_cadastral not in numbers:
        print(f"ОШИБКА: Ожидался номер {test_cadastral}, но получен {numbers}")
        return
    
    print("OK: Кадастровый номер распознан корректно")
    
    # Шаг 2: Получение данных через API
    print(f"\n2. Получение данных через API для {test_cadastral}:")
    print("-" * 80)
    
    if settings.API_SIMULATION_MODE:
        print("ВНИМАНИЕ: Режим симуляции API включен. Используются тестовые данные.")
        # Создаем тестовый объект
        result = RealEstateObject(
            cadastral_number=test_cadastral,
            object_type="Земельный участок",
            address="Тестовый адрес",
            area=1000.0,
            cadastral_value=1000000.0
        )
        print("Создан тестовый объект (симуляция)")
    else:
        if not settings.API_ROSREESTR_KEY:
            print("ОШИБКА: API ключ не установлен")
            return
        
        api_client = get_api_client()
        try:
            print("Запрос данных через API...")
            result = await api_client.get_cadastral_data(test_cadastral)
            
            if not result:
                print("ОШИБКА: Не получены данные от API")
                return
            
            if result.has_error():
                print(f"ОШИБКА API: {result.error} (код: {result.error_code})")
                return
            
            print("OK: Данные получены через API")
        except APINotConfiguredError as e:
            print(f"ОШИБКА конфигурации API: {e}")
            return
        except APIConnectionError as e:
            print(f"ОШИБКА подключения к API: {e}")
            return
        except Exception as e:
            print(f"ОШИБКА при запросе API: {e}")
            import traceback
            traceback.print_exc()
            return
        finally:
            await api_client.close()
    
    # Выводим информацию об объекте
    print(f"\nИнформация об объекте:")
    print(f"  Кадастровый номер: {result.cadastral_number}")
    print(f"  Тип объекта: {result.object_type}")
    print(f"  Адрес: {result.address}")
    print(f"  Площадь: {result.area} кв.м" if result.area else "  Площадь: не указана")
    print(f"  Кадастровая стоимость: {result.cadastral_value} руб." if result.cadastral_value else "  Кадастровая стоимость: не указана")
    if result.coordinates:
        print(f"  Координаты: X={result.coordinates.get('x')}, Y={result.coordinates.get('y')}")
    else:
        print(f"  Координаты: не указаны (будет поиск по кадастровому номеру)")
    
    # Шаг 3: Проверка типа объекта
    print(f"\n3. Проверка типа объекта:")
    print("-" * 80)
    is_land_plot = result.is_land_plot()
    print(f"Является земельным участком: {'ДА' if is_land_plot else 'НЕТ'}")
    
    if not is_land_plot:
        print("INFO: Объект не является земельным участком. Задача на карту не создается.")
        print("Тест завершен успешно (объект не требует карты).")
        return
    
    print("OK: Объект является земельным участком")
    
    # Шаг 4: Создание задачи на генерацию карты
    print(f"\n4. Создание задачи на генерацию карты:")
    print("-" * 80)
    
    # Используем тестовый user_id (можно изменить)
    test_user_id = 123456789  # Тестовый ID пользователя
    
    try:
        # Проверяем, нет ли уже задачи для этого номера
        existing_task = await get_map_task_by_cadastral(
            test_cadastral,
            status=MapGenerationStatus.PENDING
        )
        
        if existing_task:
            print(f"INFO: Уже существует задача {existing_task.id} для этого номера (статус: {existing_task.status})")
            map_task = existing_task
        else:
            # Создаем новую задачу
            coordinates = result.coordinates or {}  # Может быть пустым - поиск по номеру
            print(f"Создание задачи с координатами: {coordinates}")
            
            map_task = await create_map_task(
                user_id=test_user_id,
                cadastral_number=result.cadastral_number,
                coordinates=coordinates,
                parent_task_id=None,  # Тестовая задача без родителя
                max_retries=1  # Без повторных попыток
            )
            
            if map_task:
                print(f"OK: Задача на генерацию карты создана (ID: {map_task.id})")
                print(f"  Статус: {map_task.status}")
                print(f"  Кадастровый номер: {map_task.cadastral_number}")
                print(f"  Координаты X: {map_task.coordinate_x or 'не указаны'}")
                print(f"  Координаты Y: {map_task.coordinate_y or 'не указаны'}")
                print(f"  Макс. попыток: {map_task.max_retries}")
            else:
                print("INFO: Задача не создана (возможно, уже существует завершенная задача с картой)")
                # Проверяем завершенную задачу
                completed_task = await get_map_task_by_cadastral(
                    test_cadastral,
                    status=MapGenerationStatus.COMPLETED
                )
                if completed_task:
                    print(f"Найдена завершенная задача {completed_task.id}")
                    if completed_task.map_file_path:
                        from pathlib import Path as PathLib
                        if PathLib(completed_task.map_file_path).exists():
                            print(f"Карта уже существует: {completed_task.map_file_path}")
                        else:
                            print(f"Файл карты указан, но не найден: {completed_task.map_file_path}")
                return
        
    except Exception as e:
        print(f"ОШИБКА при создании задачи: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Итоги
    print(f"\n" + "=" * 80)
    print("ИТОГИ ТЕСТА:")
    print("=" * 80)
    print("1. Распознавание кадастрового номера: OK")
    print("2. Получение данных через API: OK")
    print("3. Проверка типа объекта: OK (земельный участок)")
    print("4. Создание задачи на генерацию карты: OK")
    print(f"\nЗадача на генерацию карты создана: ID {map_task.id}")
    print(f"Кадастровый номер: {map_task.cadastral_number}")
    print(f"Статус: {map_task.status}")
    print("\nТест завершен успешно!")
    print("=" * 80)


if __name__ == "__main__":
    try:
        asyncio.run(test_full_processing())
    except KeyboardInterrupt:
        print("\n\nТест прерван пользователем")
    except Exception as e:
        print(f"\n\nКРИТИЧЕСКАЯ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
