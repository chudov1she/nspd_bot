"""
Сервис для работы с задачами в базе данных.
"""
import json
from typing import List, Optional
from loguru import logger
from bot.utils.datetime import now_moscow

from bot.database.models import Task, TaskStatus, TaskType
from bot.database.base import async_session_maker
from sqlalchemy import select, desc


async def create_task(
    user_id: int,
    task_type: TaskType,
    input_data: Optional[str] = None,
    cadastral_numbers: Optional[List[str]] = None
) -> Task:
    """
    Создает новую задачу в базе данных.
    
    Args:
        user_id: Telegram ID пользователя
        task_type: Тип задачи
        input_data: Входные данные (текст или имя файла)
        cadastral_numbers: Список кадастровых номеров
        
    Returns:
        Созданная задача
    """
    async with async_session_maker() as session:
        task = Task(
            user_id=user_id,
            task_type=task_type,
            status=TaskStatus.PENDING,
            input_data=input_data,
            cadastral_numbers=json.dumps(cadastral_numbers) if cadastral_numbers else None,
            # started_at будет установлен воркером при начале обработки
        )
        session.add(task)
        await session.commit()
        await session.refresh(task)
        logger.info(f"Создана задача {task.id} для пользователя {user_id}, тип: {task_type}")
        return task


async def update_task_status(
    task_id: int,
    status: TaskStatus,
    error_message: Optional[str] = None
) -> None:
    """
    Обновляет статус задачи.
    
    Args:
        task_id: ID задачи
        status: Новый статус
        error_message: Сообщение об ошибке (если есть)
    """
    async with async_session_maker() as session:
        stmt = select(Task).where(Task.id == task_id)
        result = await session.execute(stmt)
        task = result.scalar_one_or_none()
        
        if task:
            task.status = status
            if error_message:
                task.error_message = error_message
            if status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                task.completed_at = now_moscow()
            await session.commit()
            logger.debug(f"Обновлен статус задачи {task_id}: {status}")


async def update_task_file_path(
    task_id: int,
    input_file_path: Optional[str] = None
) -> None:
    """
    Обновляет путь к входному файлу задачи.
    
    Args:
        task_id: ID задачи
        input_file_path: Путь к входному файлу
    """
    async with async_session_maker() as session:
        stmt = select(Task).where(Task.id == task_id)
        result = await session.execute(stmt)
        task = result.scalar_one_or_none()
        
        if task:
            if input_file_path:
                task.input_file_path = input_file_path
            await session.commit()
            logger.debug(f"Обновлен путь к файлу задачи {task_id}")


async def update_task_cadastral_numbers(
    task_id: int,
    cadastral_numbers: List[str]
) -> None:
    """
    Обновляет список кадастровых номеров задачи.
    
    Args:
        task_id: ID задачи
        cadastral_numbers: Список кадастровых номеров
    """
    async with async_session_maker() as session:
        stmt = select(Task).where(Task.id == task_id)
        result = await session.execute(stmt)
        task = result.scalar_one_or_none()
        
        if task:
            task.cadastral_numbers = json.dumps(cadastral_numbers)
            await session.commit()
            logger.debug(f"Обновлены кадастровые номера задачи {task_id}")


async def update_task_results(
    task_id: int,
    processed_count: int,
    successful_count: int,
    failed_count: int,
    output_file_path: Optional[str] = None,
    api_balance: Optional[float] = None
) -> None:
    """
    Обновляет результаты выполнения задачи.
    
    Args:
        task_id: ID задачи
        processed_count: Количество обработанных номеров
        successful_count: Успешно обработано
        failed_count: С ошибками
        output_file_path: Путь к выходному файлу
        api_balance: Баланс API
    """
    async with async_session_maker() as session:
        stmt = select(Task).where(Task.id == task_id)
        result = await session.execute(stmt)
        task = result.scalar_one_or_none()
        
        if task:
            task.processed_count = processed_count
            task.successful_count = successful_count
            task.failed_count = failed_count
            task.output_file_path = output_file_path
            if api_balance is not None:
                task.api_balance = str(api_balance)
            task.status = TaskStatus.COMPLETED
            task.completed_at = now_moscow()
            await session.commit()
            logger.debug(f"Обновлены результаты задачи {task_id}")


async def get_user_tasks(
    user_id: int,
    limit: int = 10
) -> List[Task]:
    """
    Получает последние задачи пользователя.
    
    Args:
        user_id: Telegram ID пользователя
        limit: Количество задач
        
    Returns:
        Список задач
    """
    async with async_session_maker() as session:
        stmt = (
            select(Task)
            .where(Task.user_id == user_id)
            .order_by(desc(Task.created_at))
            .limit(limit)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())


async def get_user_completed_tasks(
    user_id: int,
    offset: int = 0,
    limit: int = 5
) -> tuple[List[Task], int]:
    """
    Получает завершенные задачи пользователя с пагинацией.
    
    Args:
        user_id: Telegram ID пользователя
        offset: Смещение для пагинации
        limit: Количество задач на странице
        
    Returns:
        Кортеж (список задач, общее количество)
    """
    async with async_session_maker() as session:
        # Получаем общее количество завершенных задач
        count_stmt = (
            select(Task)
            .where(
                Task.user_id == user_id,
                Task.status == TaskStatus.COMPLETED
            )
        )
        count_result = await session.execute(count_stmt)
        total_count = len(list(count_result.scalars().all()))
        
        # Получаем задачи с пагинацией
        stmt = (
            select(Task)
            .where(
                Task.user_id == user_id,
                Task.status == TaskStatus.COMPLETED
            )
            .order_by(desc(Task.completed_at))
            .offset(offset)
            .limit(limit)
        )
        result = await session.execute(stmt)
        tasks = list(result.scalars().all())
        
        return tasks, total_count


async def get_all_completed_tasks(
    offset: int = 0,
    limit: int = 5
) -> tuple[List[Task], int]:
    """
    Получает все завершенные задачи (успешные и с ошибками) с пагинацией (без фильтрации по пользователю).
    
    Args:
        offset: Смещение для пагинации
        limit: Количество задач на странице
        
    Returns:
        Кортеж (список задач, общее количество)
    """
    async with async_session_maker() as session:
        # Получаем общее количество завершенных задач (COMPLETED и FAILED)
        count_stmt = (
            select(Task)
            .where(
                Task.status.in_([TaskStatus.COMPLETED, TaskStatus.FAILED])
            )
        )
        count_result = await session.execute(count_stmt)
        total_count = len(list(count_result.scalars().all()))
        
        # Получаем задачи с пагинацией (COMPLETED и FAILED)
        stmt = (
            select(Task)
            .where(
                Task.status.in_([TaskStatus.COMPLETED, TaskStatus.FAILED])
            )
            .order_by(desc(Task.completed_at))
            .offset(offset)
            .limit(limit)
        )
        result = await session.execute(stmt)
        tasks = list(result.scalars().all())
        
        return tasks, total_count


async def get_task_by_id(task_id: int, user_id: Optional[int] = None) -> Optional[Task]:
    """
    Получает задачу по ID.
    
    Args:
        task_id: ID задачи
        user_id: Telegram ID пользователя (опционально, для проверки владельца)
        
    Returns:
        Задача или None
    """
    async with async_session_maker() as session:
        stmt = select(Task).where(Task.id == task_id)
        if user_id:
            stmt = stmt.where(Task.user_id == user_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()


async def get_all_tasks(
    limit: int = 50,
    status: Optional[TaskStatus] = None
) -> List[Task]:
    """
    Получает все задачи (для администраторов).
    
    Args:
        limit: Количество задач
        status: Фильтр по статусу
        
    Returns:
        Список задач
    """
    async with async_session_maker() as session:
        stmt = select(Task).order_by(desc(Task.created_at))
        
        if status:
            stmt = stmt.where(Task.status == status)
        
        stmt = stmt.limit(limit)
        
        result = await session.execute(stmt)
        return list(result.scalars().all())


async def get_task_statistics() -> dict:
    """
    Получает статистику по задачам.
    
    Returns:
        Словарь со статистикой
    """
    async with async_session_maker() as session:
        # Общее количество задач
        total_stmt = select(Task)
        total_result = await session.execute(total_stmt)
        total_tasks = len(list(total_result.scalars().all()))
        
        # По статусам
        completed_stmt = select(Task).where(Task.status == TaskStatus.COMPLETED)
        completed_result = await session.execute(completed_stmt)
        completed_count = len(list(completed_result.scalars().all()))
        
        failed_stmt = select(Task).where(Task.status == TaskStatus.FAILED)
        failed_result = await session.execute(failed_stmt)
        failed_count = len(list(failed_result.scalars().all()))
        
        return {
            "total": total_tasks,
            "completed": completed_count,
            "failed": failed_count,
            "success_rate": (completed_count / total_tasks * 100) if total_tasks > 0 else 0
        }

