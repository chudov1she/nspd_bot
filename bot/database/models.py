"""
Модели базы данных.
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, Enum as SQLEnum
from sqlalchemy.sql import func
from enum import Enum
from bot.database.base import Base


class TaskStatus(str, Enum):
    """Статусы задач."""
    PENDING = "pending"  # В ожидании
    PROCESSING = "processing"  # Обрабатывается
    COMPLETED = "completed"  # Завершена успешно
    FAILED = "failed"  # Завершена с ошибкой
    CANCELLED = "cancelled"  # Отменена


class TaskType(str, Enum):
    """Типы задач."""
    TEXT_INPUT = "text_input"  # Ввод текста
    FILE_UPLOAD = "file_upload"  # Загрузка файла


class MapGenerationStatus(str, Enum):
    """Статусы задач генерации карт."""
    PENDING = "pending"  # В ожидании
    PROCESSING = "processing"  # Обрабатывается
    COMPLETED = "completed"  # Завершена успешно
    FAILED = "failed"  # Завершена с ошибкой
    RETRYING = "retrying"  # Повторная попытка


class User(Base):
    """Модель пользователя Telegram."""
    
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(Integer, unique=True, nullable=False, index=True)
    username = Column(String, nullable=True, index=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    is_admin = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def __repr__(self) -> str:
        return f"<User(telegram_id={self.telegram_id}, username={self.username}, is_admin={self.is_admin})>"


class Task(Base):
    """Модель задачи/запроса пользователя."""
    
    __tablename__ = "tasks"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)  # Telegram ID пользователя
    task_type = Column(SQLEnum(TaskType), nullable=False)  # Тип задачи
    status = Column(SQLEnum(TaskStatus), default=TaskStatus.PENDING, nullable=False, index=True)
    
    # Входные данные
    input_data = Column(Text, nullable=True)  # Текст или имя файла
    cadastral_numbers = Column(Text, nullable=True)  # JSON список кадастровых номеров
    
    # Результаты
    processed_count = Column(Integer, default=0)  # Количество обработанных номеров
    successful_count = Column(Integer, default=0)  # Успешно обработано
    failed_count = Column(Integer, default=0)  # С ошибками
    
    # Файлы
    input_file_path = Column(String, nullable=True)  # Путь к входному файлу
    output_file_path = Column(String, nullable=True)  # Путь к выходному файлу
    
    # Ошибки и информация
    error_message = Column(Text, nullable=True)  # Сообщение об ошибке
    api_balance = Column(String, nullable=True)  # Баланс API после выполнения
    
    # Временные метки
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    def __repr__(self) -> str:
        return f"<Task(id={self.id}, user_id={self.user_id}, type={self.task_type}, status={self.status})>"


class MapGenerationTask(Base):
    """Модель задачи генерации карты для земельного участка."""
    
    __tablename__ = "map_generation_tasks"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    parent_task_id = Column(Integer, nullable=True, index=True)  # ID основной задачи (опционально)
    user_id = Column(Integer, nullable=False, index=True)  # Telegram ID пользователя
    cadastral_number = Column(String, nullable=False, index=True)  # Кадастровый номер участка
    
    # Координаты для генерации карты
    coordinate_x = Column(String, nullable=True)  # Координата X
    coordinate_y = Column(String, nullable=True)  # Координата Y
    
    # Статус и повторные попытки
    status = Column(SQLEnum(MapGenerationStatus), default=MapGenerationStatus.PENDING, nullable=False, index=True)
    retry_count = Column(Integer, default=0, nullable=False)  # Количество попыток
    max_retries = Column(Integer, default=3, nullable=False)  # Максимум попыток
    
    # Результаты
    map_file_path = Column(String, nullable=True)  # Путь к сгенерированной карте
    error_message = Column(Text, nullable=True)  # Сообщение об ошибке
    
    # Временные метки
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    last_retry_at = Column(DateTime(timezone=True), nullable=True)  # Время последней попытки
    
    def __repr__(self) -> str:
        return f"<MapGenerationTask(id={self.id}, cadastral={self.cadastral_number}, status={self.status}, retries={self.retry_count})>"

