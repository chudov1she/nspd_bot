"""
Сервис для работы с личным кабинетом Росреестра (lk.rosreestr.ru).
"""
import os
from typing import Optional
from loguru import logger

from bot.services.rosreestr_lk.core import RosreestrLKClient
from bot.services.rosreestr_lk.exceptions import RosreestrLKError
from bot.services.rosreestr_lk.captcha_recognizer import CaptchaRecognizer
from bot.services.rosreestr_lk.llm_captcha_recognizer import LLMCaptchaRecognizer

# Глобальный экземпляр клиента
_lk_client: Optional[RosreestrLKClient] = None


def get_lk_client(use_llm_for_captcha: bool = None) -> RosreestrLKClient:
    """
    Получить глобальный экземпляр клиента личного кабинета Росреестра.
    
    Args:
        use_llm_for_captcha: Использовать LLM для распознавания капчи.
                             Если None, используется значение из переменной окружения USE_LLM_CAPTCHA.
    
    Returns:
        Глобальный экземпляр RosreestrLKClient
    """
    global _lk_client
    
    if _lk_client is None:
        # Определяем, использовать ли LLM для капчи
        if use_llm_for_captcha is None:
            use_llm_for_captcha = os.getenv("USE_LLM_CAPTCHA", "false").lower() == "true"
        
        _lk_client = RosreestrLKClient(use_llm_for_captcha=use_llm_for_captcha)
        logger.info(f"Создан глобальный экземпляр RosreestrLKClient (LLM для капчи: {use_llm_for_captcha})")
    
    return _lk_client


async def close_lk_client():
    """Закрыть глобальный клиент личного кабинета Росреестра."""
    global _lk_client
    
    if _lk_client:
        try:
            await _lk_client.close()
            logger.info("Глобальный экземпляр RosreestrLKClient закрыт")
        except Exception as e:
            logger.error(f"Ошибка при закрытии RosreestrLKClient: {e}")
        finally:
            _lk_client = None


__all__ = [
    "RosreestrLKClient",
    "RosreestrLKError",
    "CaptchaRecognizer",
    "LLMCaptchaRecognizer",
    "get_lk_client",
    "close_lk_client",
]
