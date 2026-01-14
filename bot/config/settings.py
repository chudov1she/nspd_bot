"""
Настройки и конфигурация бота.
"""
import os
from pathlib import Path
from dotenv import load_dotenv
from loguru import logger

# Загрузка переменных окружения
load_dotenv()

# Базовые пути
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"

# Создание директорий если их нет
LOGS_DIR.mkdir(exist_ok=True)
(DATA_DIR / "input").mkdir(parents=True, exist_ok=True)
(DATA_DIR / "output").mkdir(parents=True, exist_ok=True)


class Settings:
    """Класс для хранения настроек бота."""
    
    # Telegram Bot
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    
    # API Росреестра
    # URL API жестко задан в api_client.py согласно документации
    # API_ROSREESTR_BASE_URL больше не используется
    API_ROSREESTR_KEY: str = os.getenv("API_ROSREESTR_KEY", "")
    # TIMEOUT минимум 120 секунд согласно документации api-cloud.ru
    API_ROSREESTR_TIMEOUT: int = int(os.getenv("API_ROSREESTR_TIMEOUT", "120"))
    # Режим симуляции API (для тестирования без реального ключа)
    API_SIMULATION_MODE: bool = os.getenv("API_SIMULATION_MODE", "false").lower() in ("true", "1", "yes")
    
    # Пути
    BASE_DIR: Path = BASE_DIR
    DATA_DIR: Path = DATA_DIR
    LOGS_DIR: Path = LOGS_DIR
    INPUT_DIR: Path = DATA_DIR / "input"
    OUTPUT_DIR: Path = DATA_DIR / "output"
    
    # Логирование
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: Path = LOGS_DIR / "bot.log"
    LOG_ROTATION: str = "10 MB"
    LOG_RETENTION: str = "7 days"
    
    # База данных
    DATABASE_FILE: Path = BASE_DIR / "bot.db"
    
    # Администраторы (из .env)
    ADMIN_IDS: str = os.getenv("ADMIN_IDS", "")
    
    @classmethod
    def validate(cls) -> None:
        """Проверяет корректность настроек."""
        if not cls.TELEGRAM_BOT_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN не найден в переменных окружения!")
    
    @classmethod
    def is_api_configured(cls) -> bool:
        """Проверяет, настроен ли API ключ."""
        # В режиме симуляции считаем что API настроен
        if cls.API_SIMULATION_MODE:
            return True
        return bool(cls.API_ROSREESTR_KEY)
    
    @classmethod
    def get_admin_ids(cls) -> list[int]:
        """
        Получает список ID администраторов из переменной окружения ADMIN_IDS.
        
        Формат в .env: ADMIN_IDS=123456789,987654321,111222333
        Или через пробел: ADMIN_IDS=123456789 987654321 111222333
        
        Returns:
            Список ID администраторов
        """
        admin_ids = []
        if not cls.ADMIN_IDS:
            return admin_ids
        
        # Поддерживаем оба формата: через запятую и через пробел
        ids_str = cls.ADMIN_IDS.replace(",", " ").strip()
        for id_str in ids_str.split():
            id_str = id_str.strip()
            if id_str:
                try:
                    admin_ids.append(int(id_str))
                except ValueError:
                    logger.warning(f"Некорректный ID администратора в ADMIN_IDS: {id_str}")
        
        return admin_ids


# Экземпляр настроек
settings = Settings()

