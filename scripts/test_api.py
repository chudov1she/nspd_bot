"""
Скрипт для проверки работы API Росреестра.
Проверяет подключение, баланс и получение данных по тестовому кадастровому номеру.
"""
import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from bot.config.settings import settings
from bot.services.api_client import get_api_client, close_api_client
from loguru import logger


async def test_api():
    """Тестирует работу API Росреестра."""
    print("=" * 60)
    print("🔍 Проверка настроек API Росреестра")
    print("=" * 60)
    
    # Проверяем настройки
    print(f"\n📋 Настройки:")
    print(f"   API ключ: {'✅ Установлен' if settings.API_ROSREESTR_KEY else '❌ Не установлен'}")
    print(f"   Режим симуляции: {'⚠️ ВКЛЮЧЕН (тестовый режим)' if settings.API_SIMULATION_MODE else '✅ ВЫКЛЮЧЕН (реальный API)'}")
    print(f"   Timeout: {settings.API_ROSREESTR_TIMEOUT} сек")
    
    if settings.API_SIMULATION_MODE:
        print("\n⚠️  ВНИМАНИЕ: Режим симуляции включен!")
        print("   Для проверки реального API установите в .env:")
        print("   API_SIMULATION_MODE=false")
        return
    
    if not settings.API_ROSREESTR_KEY:
        print("\n❌ ОШИБКА: API ключ не установлен!")
        print("   Установите в .env файле:")
        print("   API_ROSREESTR_KEY=ваш_ключ_здесь")
        return
    
    print("\n" + "=" * 60)
    print("🔌 Проверка подключения к API")
    print("=" * 60)
    
    try:
        api_client = get_api_client()
        
        # 1. Проверка доступности API
        print("\n1️⃣ Проверка доступности API...")
        is_available = await api_client.check_availability()
        if is_available:
            print("   ✅ API доступен")
        else:
            print("   ❌ API недоступен")
            return
        
        # 2. Проверка баланса
        print("\n2️⃣ Проверка баланса...")
        balance = await api_client.get_balance()
        if balance is not None:
            print(f"   ✅ Баланс: {balance:,.2f} руб.")
        else:
            print("   ⚠️  Не удалось получить баланс")
        
        # 3. Тестовый запрос данных
        print("\n3️⃣ Тестовый запрос данных...")
        test_cadastral = "78:38:0022629:1115"  # Тестовый номер из логов
        print(f"   Кадастровый номер: {test_cadastral}")
        
        try:
            result = await api_client.get_cadastral_data(test_cadastral)
            
            if result.has_error():
                print(f"   ⚠️  Ошибка: {result.error}")
                if result.error_code:
                    print(f"   Код ошибки: {result.error_code}")
            else:
                print("   ✅ Данные получены успешно!")
                print(f"   Тип объекта: {result.object_type}")
                print(f"   Адрес: {result.address}")
                if result.area:
                    print(f"   Площадь: {result.area} кв.м")
                if result.cadastral_value:
                    print(f"   Кадастровая стоимость: {result.cadastral_value:,.2f} руб.")
                if result.api_balance is not None:
                    print(f"   Баланс после запроса: {result.api_balance:,.2f} руб.")
        
        except Exception as e:
            print(f"   ❌ Ошибка при запросе данных: {e}")
            logger.exception("Детали ошибки:")
        
        # Закрываем соединение
        await close_api_client()
        
        print("\n" + "=" * 60)
        print("✅ Проверка завершена")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        logger.exception("Детали ошибки:")
        await close_api_client()


if __name__ == "__main__":
    # Настройка логирования
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO"
    )
    
    try:
        asyncio.run(test_api())
    except KeyboardInterrupt:
        print("\n\n⏹ Прервано пользователем")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        sys.exit(1)
