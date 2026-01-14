"""
Общие функции для обработки запросов к Росреестру.
"""
from typing import List, Optional
from pathlib import Path
from aiogram.types import Message, FSInputFile
from loguru import logger

from bot.models.cadastral import RealEstateObject
from bot.services.api_client import get_api_client, APINotConfiguredError, APIConnectionError
from bot.services.excel_handler import create_output_excel, ExcelHandlerError
from bot.services.task_service import update_task_status, update_task_results
from bot.database.models import Task, TaskStatus
from bot.keyboards.menu import get_cancel_keyboard


async def check_api_availability(
    message: Message,
    task: Task,
    numbers: List[str],
    user_id: int
) -> bool:
    """
    Проверяет доступность API и отправляет сообщения об ошибках.
    
    Returns:
        True если API доступен, False иначе
    """
    from bot.config.settings import settings
    
    api_client = get_api_client()
    
    # Проверка наличия API ключа
    if not settings.is_api_configured():
        numbers_text = "\n".join([f"• <code>{num}</code>" for num in numbers[:10]])
        if len(numbers) > 10:
            numbers_text += f"\n... и еще {len(numbers) - 10} номеров"
        
        await update_task_status(task.id, TaskStatus.FAILED, "API ключ не задан")
        await message.answer(
            f"⚠️ <b>API ключ не задан</b>\n\n"
            f"📊 Найдено кадастровых номеров: <b>{len(numbers)}</b>\n\n"
            f"<b>Найденные номера:</b>\n{numbers_text}\n\n"
            "Для получения данных необходимо настроить API ключ.\n\n"
            "Установите переменную окружения <code>API_ROSREESTR_KEY</code> в файле <code>.env</code>.",
            reply_markup=get_cancel_keyboard(),
            parse_mode="HTML"
        )
        logger.warning(f"API ключ не задан, пользователь {user_id} не может получить данные")
        return False
    
    # Проверка доступности API
    is_available = await api_client.check_availability()
    if not is_available:
        numbers_text = "\n".join([f"• <code>{num}</code>" for num in numbers[:10]])
        if len(numbers) > 10:
            numbers_text += f"\n... и еще {len(numbers) - 10} номеров"
        
        await update_task_status(task.id, TaskStatus.FAILED, "API недоступен")
        await message.answer(
            f"⚠️ <b>API недоступен</b>\n\n"
            f"📊 Найдено кадастровых номеров: <b>{len(numbers)}</b>\n\n"
            f"<b>Найденные номера:</b>\n{numbers_text}\n\n"
            "Не удалось подключиться к API Росреестра.\n"
            "Проверьте настройки API ключа и доступность сервиса.",
            reply_markup=get_cancel_keyboard(),
            parse_mode="HTML"
        )
        logger.warning(f"API недоступен для пользователя {user_id}")
        return False
    
    return True


async def get_api_balance(results: List[RealEstateObject]) -> Optional[float]:
    """
    Получает баланс API из последнего ответа или отдельным запросом.
    
    Args:
        results: Список результатов обработки
        
    Returns:
        Баланс API или None
    """
    # Ищем баланс в последнем ответе API
    balance = None
    for result in reversed(results):
        if result.api_balance is not None:
            balance = result.api_balance
            break
    
    # Если баланс не найден, делаем отдельный запрос
    if balance is None:
        api_client = get_api_client()
        balance = await api_client.get_balance()
    
    return balance


def format_response_text(
    successful: List[RealEstateObject],
    failed: List[RealEstateObject],
    balance: Optional[float] = None
) -> str:
    """
    Формирует текст ответа со статистикой обработки.
    
    Args:
        successful: Список успешно обработанных результатов
        failed: Список результатов с ошибками
        balance: Баланс API
        
    Returns:
        Форматированный текст ответа
    """
    response_text = (
        f"✅ <b>Обработка завершена</b>\n\n"
        f"📊 <b>Статистика:</b>\n"
        f"• Успешно обработано: <b>{len(successful)}</b>\n"
        f"• С ошибками: <b>{len(failed)}</b>\n\n"
    )
    
    if balance is not None:
        response_text += f"💰 <b>Текущий баланс API:</b> {balance:.2f} руб.\n\n"
    
    if failed:
        response_text += "⚠️ <b>Ошибки:</b>\n"
        for result in failed[:5]:  # Показываем первые 5 ошибок
            response_text += f"• <code>{result.cadastral_number}</code>: {result.error}\n"
        if len(failed) > 5:
            response_text += f"... и еще {len(failed) - 5} ошибок\n"
        response_text += "\n"
    
    return response_text


async def process_api_results(
    message: Message,
    task: Task,
    numbers: List[str],
    results: List[RealEstateObject],
    source_file_path: Optional[Path] = None
) -> None:
    """
    Обрабатывает результаты API: формирует ответ, создает Excel, отправляет файл.
    
    Args:
        message: Сообщение от пользователя
        task: Задача в БД
        numbers: Список кадастровых номеров
        results: Результаты обработки API
        source_file_path: Путь к исходному файлу (для файлового ввода)
    """
    user_id = message.from_user.id
    
    # Подсчитываем успешные и неуспешные запросы
    successful = [r for r in results if not r.has_error()]
    failed = [r for r in results if r.has_error()]
    
    # Получаем баланс
    balance = await get_api_balance(results)
    
    # Формируем ответ
    response_text = format_response_text(successful, failed, balance)
    
    # Формируем Excel файл
    try:
        await message.answer(
            response_text + "\n📄 <i>Формирование Excel файла...</i>",
            reply_markup=get_cancel_keyboard(),
            parse_mode="HTML"
        )
        
        # Создаем выходной файл
        if source_file_path:
            output_file = create_output_excel(results, source_file_path=source_file_path)
        else:
            output_file = create_output_excel(results)
        
        # Обновляем задачу с результатами
        try:
            await update_task_results(
                task_id=task.id,
                processed_count=len(numbers),
                successful_count=len(successful),
                failed_count=len(failed),
                output_file_path=str(output_file),
                api_balance=balance
            )
        except Exception as e:
            logger.warning(f"Не удалось обновить задачу {task.id}: {e}")
        
        # Отправляем файл пользователю
        document = FSInputFile(output_file)
        await message.answer_document(
            document=document,
            caption=f"✅ <b>Файл готов!</b>\n\n"
                    f"Обработано записей: <b>{len(results)}</b>\n"
                    f"Успешно: <b>{len(successful)}</b>\n"
                    f"С ошибками: <b>{len(failed)}</b>",
            parse_mode="HTML"
        )
        
        logger.info(f"Файл отправлен пользователю {user_id}: {output_file.name}")
        
        # Удаляем временный файл после отправки
        try:
            output_file.unlink()
        except Exception as e:
            logger.warning(f"Не удалось удалить временный файл {output_file}: {e}")
            
    except ExcelHandlerError as e:
        logger.error(f"Ошибка при создании Excel файла: {e}")
        await update_task_status(task.id, TaskStatus.FAILED, f"Ошибка создания файла: {str(e)}")
        await message.answer(
            response_text + f"\n\n❌ <b>Ошибка при создании файла:</b>\n<code>{str(e)}</code>",
            reply_markup=get_cancel_keyboard(),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Неожиданная ошибка при создании файла: {e}", exc_info=True)
        await update_task_status(task.id, TaskStatus.FAILED, f"Ошибка: {str(e)}")
        await message.answer(
            response_text + f"\n\n❌ <b>Ошибка при создании файла:</b>\n<code>{str(e)}</code>",
            reply_markup=get_cancel_keyboard(),
            parse_mode="HTML"
        )
    
    logger.info(
        f"Обработано {len(successful)}/{len(numbers)} номеров для пользователя {user_id}"
    )


async def handle_api_errors(
    message: Message,
    task: Task,
    error: Exception
) -> None:
    """
    Обрабатывает ошибки API и отправляет сообщения пользователю.
    
    Args:
        message: Сообщение от пользователя
        task: Задача в БД
        error: Исключение
    """
    if isinstance(error, APINotConfiguredError):
        await update_task_status(task.id, TaskStatus.FAILED, "API ключ не задан")
        await message.answer(
            "❌ <b>API ключ не задан</b>\n\n"
            "Для получения данных необходимо настроить API ключ.\n\n"
            "Установите переменную окружения <code>API_ROSREESTR_KEY</code> в файле <code>.env</code>.",
            reply_markup=get_cancel_keyboard(),
            parse_mode="HTML"
        )
    elif isinstance(error, APIConnectionError):
        await update_task_status(task.id, TaskStatus.FAILED, f"Ошибка подключения: {str(error)}")
        await message.answer(
            f"❌ <b>Ошибка подключения к API</b>\n\n"
            f"{str(error)}\n\n"
            "Проверьте доступность сервиса.",
            reply_markup=get_cancel_keyboard(),
            parse_mode="HTML"
        )
    else:
        logger.error(f"Ошибка при получении данных через API: {error}", exc_info=True)
        try:
            await update_task_status(task.id, TaskStatus.FAILED, str(error))
        except Exception:
            pass
        await message.answer(
            f"❌ <b>Ошибка при обработке данных</b>\n\n"
            f"<code>{str(error)}</code>",
            reply_markup=get_cancel_keyboard(),
            parse_mode="HTML"
        )

