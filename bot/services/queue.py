"""
Сервис управления очередью задач.
"""
import asyncio
from typing import Optional
from loguru import logger
from bot.utils.datetime import now_moscow

from bot.database.models import Task, TaskStatus
from bot.database.base import async_session_maker
from bot.services.task_service import update_task_status
from sqlalchemy import select, func


class TaskQueue:
    """Очередь задач для обработки."""
    
    def __init__(self):
        self._lock = asyncio.Lock()
        self._processing = False
    
    async def add_task(self, task_id: int) -> int:
        """
        Добавляет задачу в очередь.
        
        Args:
            task_id: ID задачи
            
        Returns:
            Позиция в очереди (1-based)
        """
        async with self._lock:
            async with async_session_maker() as session:
                # Подсчитываем количество задач в очереди (pending или processing)
                stmt = select(func.count(Task.id)).where(
                    Task.status.in_([TaskStatus.PENDING, TaskStatus.PROCESSING])
                )
                result = await session.execute(stmt)
                queue_position = result.scalar() + 1
                
                # Обновляем задачу
                stmt = select(Task).where(Task.id == task_id)
                task_result = await session.execute(stmt)
                task = task_result.scalar_one_or_none()
                
                if task:
                    task.status = TaskStatus.PENDING
                    await session.commit()
                    logger.info(
                        f"Задача {task_id} добавлена в очередь, позиция: {queue_position}"
                    )
                    return queue_position
                else:
                    logger.error(f"Задача {task_id} не найдена")
                    return 0
    
    async def get_next_task(self) -> Optional[Task]:
        """
        Получает следующую задачу из очереди (FIFO).
        
        Returns:
            Следующая задача или None если очередь пуста
        """
        async with self._lock:
            async with async_session_maker() as session:
                # Получаем самую старую задачу со статусом PENDING
                stmt = (
                    select(Task)
                    .where(Task.status == TaskStatus.PENDING)
                    .order_by(Task.created_at.asc())
                    .limit(1)
                )
                result = await session.execute(stmt)
                task = result.scalar_one_or_none()
                
                if task:
                    # Меняем статус на PROCESSING
                    task.status = TaskStatus.PROCESSING
                    task.started_at = now_moscow()
                    await session.commit()
                    await session.refresh(task)
                    logger.info(f"Задача {task.id} взята в обработку из очереди")
                    return task
                
                return None
    
    async def get_queue_size(self) -> int:
        """
        Возвращает размер очереди (количество задач в статусе PENDING).
        
        Returns:
            Количество задач в очереди
        """
        async with self._lock:
            async with async_session_maker() as session:
                stmt = select(func.count(Task.id)).where(Task.status == TaskStatus.PENDING)
                result = await session.execute(stmt)
                return result.scalar() or 0
    
    async def get_queue_position(self, task_id: int) -> int:
        """
        Возвращает позицию задачи в очереди.
        
        Args:
            task_id: ID задачи
            
        Returns:
            Позиция в очереди (1-based) или 0 если задача не в очереди
        """
        async with self._lock:
            async with async_session_maker() as session:
                # Получаем задачу
                stmt = select(Task).where(Task.id == task_id)
                result = await session.execute(stmt)
                task = result.scalar_one_or_none()
                
                if not task or task.status != TaskStatus.PENDING:
                    return 0
                
                # Подсчитываем количество задач, созданных раньше этой
                stmt = select(func.count(Task.id)).where(
                    Task.status == TaskStatus.PENDING,
                    Task.created_at < task.created_at
                )
                result = await session.execute(stmt)
                position = result.scalar() or 0
                return position + 1


# Глобальный экземпляр очереди
_task_queue: Optional[TaskQueue] = None


def get_task_queue() -> TaskQueue:
    """Получить глобальный экземпляр очереди."""
    global _task_queue
    if _task_queue is None:
        _task_queue = TaskQueue()
    return _task_queue

