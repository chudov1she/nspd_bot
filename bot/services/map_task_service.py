"""
Сервис для работы с задачами генерации карт в базе данных.
"""
import json
from typing import List, Optional, Dict
from loguru import logger
from bot.utils.datetime import now_moscow

from bot.database.models import MapGenerationTask, MapGenerationStatus
from bot.database.base import async_session_maker
from sqlalchemy import select, desc, and_


async def create_map_task(
    user_id: int,
    cadastral_number: str,
    coordinates: Optional[Dict[str, float]] = None,
    parent_task_id: Optional[int] = None,
    max_retries: int = 3
) -> Optional[MapGenerationTask]:
    """
    Создает новую задачу генерации карты.
    Проверяет на дубликаты - если уже есть активная задача для этого номера, возвращает None.
    
    Args:
        user_id: Telegram ID пользователя
        cadastral_number: Кадастровый номер участка
        coordinates: Словарь с координатами {'x': float, 'y': float} (опционально, не используется)
        parent_task_id: ID основной задачи (опционально)
        max_retries: Максимум попыток при ошибках
        
    Returns:
        Созданная задача или None, если дубликат
    """
    async with async_session_maker() as session:
        # Проверяем на дубликаты - ищем активные задачи для этого номера
        duplicate_stmt = select(MapGenerationTask).where(
            and_(
                MapGenerationTask.cadastral_number == cadastral_number,
                MapGenerationTask.status.in_([
                    MapGenerationStatus.PENDING,
                    MapGenerationStatus.PROCESSING,
                    MapGenerationStatus.RETRYING
                ])
            )
        )
        duplicate_result = await session.execute(duplicate_stmt)
        existing_task = duplicate_result.scalar_one_or_none()
        
        if existing_task:
            logger.info(
                f"Найдена активная задача генерации карты для {cadastral_number} "
                f"(ID: {existing_task.id}, статус: {existing_task.status})"
            )
            return None  # Дубликат - не создаем новую задачу
        
        # Проверяем, есть ли уже успешно выполненная задача (можно использовать существующую карту)
        completed_stmt = select(MapGenerationTask).where(
            and_(
                MapGenerationTask.cadastral_number == cadastral_number,
                MapGenerationTask.status == MapGenerationStatus.COMPLETED,
                MapGenerationTask.map_file_path.isnot(None)
            )
        ).order_by(desc(MapGenerationTask.completed_at)).limit(1)
        
        completed_result = await session.execute(completed_stmt)
        completed_task = completed_result.scalar_one_or_none()
        
        if completed_task:
            from pathlib import Path
            # Проверяем, существует ли файл карты
            if completed_task.map_file_path and Path(completed_task.map_file_path).exists():
                logger.info(
                    f"Найдена существующая карта для {cadastral_number} "
                    f"(задача ID: {completed_task.id})"
                )
                return None  # Карта уже существует
        
        # Создаем новую задачу (координаты опциональны)
        coordinates = coordinates or {}
        task = MapGenerationTask(
            user_id=user_id,
            cadastral_number=cadastral_number,
            coordinate_x=str(coordinates.get('x', '')) if coordinates.get('x') else None,
            coordinate_y=str(coordinates.get('y', '')) if coordinates.get('y') else None,
            parent_task_id=parent_task_id,
            max_retries=max_retries,
            status=MapGenerationStatus.PENDING
        )
        
        session.add(task)
        await session.commit()
        await session.refresh(task)
        
        logger.info(
            f"Создана задача генерации карты {task.id} для {cadastral_number} "
            f"(пользователь {user_id})"
        )
        return task


async def get_pending_map_tasks(limit: int = 10) -> List[MapGenerationTask]:
    """
    Получает список задач генерации карт в ожидании обработки.
    
    Args:
        limit: Максимальное количество задач
        
    Returns:
        Список задач
    """
    async with async_session_maker() as session:
        stmt = (
            select(MapGenerationTask)
            .where(MapGenerationTask.status == MapGenerationStatus.PENDING)
            .order_by(MapGenerationTask.created_at)
            .limit(limit)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())


async def get_retry_map_tasks(limit: int = 10) -> List[MapGenerationTask]:
    """
    Получает список задач для повторной попытки.
    
    Args:
        limit: Максимальное количество задач
        
    Returns:
        Список задач
    """
    async with async_session_maker() as session:
        stmt = (
            select(MapGenerationTask)
            .where(
                and_(
                    MapGenerationTask.status == MapGenerationStatus.RETRYING,
                    MapGenerationTask.retry_count < MapGenerationTask.max_retries
                )
            )
            .order_by(MapGenerationTask.last_retry_at)
            .limit(limit)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())


async def update_map_task_status(
    task_id: int,
    status: MapGenerationStatus,
    error_message: Optional[str] = None
) -> None:
    """
    Обновляет статус задачи генерации карты.
    
    Args:
        task_id: ID задачи
        status: Новый статус
        error_message: Сообщение об ошибке (если есть)
    """
    async with async_session_maker() as session:
        stmt = select(MapGenerationTask).where(MapGenerationTask.id == task_id)
        result = await session.execute(stmt)
        task = result.scalar_one_or_none()
        
        if task:
            task.status = status
            if error_message:
                task.error_message = error_message
            
            if status == MapGenerationStatus.PROCESSING:
                task.started_at = now_moscow()
            elif status in [MapGenerationStatus.COMPLETED, MapGenerationStatus.FAILED]:
                task.completed_at = now_moscow()
            
            await session.commit()
            logger.debug(f"Обновлен статус задачи генерации карты {task_id}: {status}")


async def update_map_task_result(
    task_id: int,
    map_file_path: Optional[str] = None,
    error_message: Optional[str] = None
) -> None:
    """
    Обновляет результат выполнения задачи генерации карты.
    
    Args:
        task_id: ID задачи
        map_file_path: Путь к сгенерированной карте
        error_message: Сообщение об ошибке (если есть)
    """
    async with async_session_maker() as session:
        stmt = select(MapGenerationTask).where(MapGenerationTask.id == task_id)
        result = await session.execute(stmt)
        task = result.scalar_one_or_none()
        
        if task:
            if map_file_path:
                task.map_file_path = map_file_path
                task.status = MapGenerationStatus.COMPLETED
                task.completed_at = now_moscow()
                logger.info(f"Задача генерации карты {task_id} завершена успешно: {map_file_path}")
            elif error_message:
                # При ошибке сразу помечаем как FAILED, без повторных попыток
                task.error_message = error_message
                task.status = MapGenerationStatus.FAILED
                task.completed_at = now_moscow()
                logger.error(
                    f"Задача генерации карты {task_id} завершена с ошибкой: {error_message}"
                )
            
            await session.commit()


async def get_map_task_by_id(task_id: int) -> Optional[MapGenerationTask]:
    """
    Получает задачу генерации карты по ID.
    
    Args:
        task_id: ID задачи
        
    Returns:
        Задача или None
    """
    async with async_session_maker() as session:
        stmt = select(MapGenerationTask).where(MapGenerationTask.id == task_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()


async def get_map_task_by_cadastral(
    cadastral_number: str,
    status: Optional[MapGenerationStatus] = None
) -> Optional[MapGenerationTask]:
    """
    Получает задачу генерации карты по кадастровому номеру.
    
    Args:
        cadastral_number: Кадастровый номер
        status: Фильтр по статусу (опционально)
        
    Returns:
        Задача или None
    """
    async with async_session_maker() as session:
        stmt = select(MapGenerationTask).where(
            MapGenerationTask.cadastral_number == cadastral_number
        )
        
        if status:
            stmt = stmt.where(MapGenerationTask.status == status)
        
        stmt = stmt.order_by(desc(MapGenerationTask.created_at)).limit(1)
        
        result = await session.execute(stmt)
        return result.scalar_one_or_none()


async def get_user_map_tasks(
    user_id: int,
    limit: int = 10
) -> List[MapGenerationTask]:
    """
    Получает задачи генерации карт пользователя.
    
    Args:
        user_id: Telegram ID пользователя
        limit: Количество задач
        
    Returns:
        Список задач
    """
    async with async_session_maker() as session:
        stmt = (
            select(MapGenerationTask)
            .where(MapGenerationTask.user_id == user_id)
            .order_by(desc(MapGenerationTask.created_at))
            .limit(limit)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

