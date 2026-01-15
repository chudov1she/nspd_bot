"""
Модуль для распознавания капчи через LLM (OpenRouter API).
Использует vision модели для распознавания текста с изображений.
"""
from pathlib import Path
from typing import Optional
from loguru import logger
import base64
import aiohttp

from bot.services.rosreestr_lk.exceptions import RosreestrLKError


class LLMCaptchaRecognizer:
    """Распознавание капчи через LLM с vision capabilities."""
    
    # OpenRouter API endpoint
    OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
    
    # Бесплатные модели с vision
    FREE_VISION_MODELS = [
        "allenai/molmo-2-8b:free",  # Бесплатная модель AllenAI (по умолчанию)
        "google/gemini-flash-1.5",  # Бесплатная модель Google
        "google/gemini-pro-vision",  # Альтернатива
        "qwen/qwen-vl-max",  # Бесплатная модель Qwen
    ]
    
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """
        Инициализация распознавателя.
        
        Args:
            api_key: API ключ OpenRouter (опционально, можно через env)
            model: Модель для использования (по умолчанию allenai/molmo-2-8b:free)
        """
        import os
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY", "")
        self.model = model or self.FREE_VISION_MODELS[0]
        self._session = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Получает или создает HTTP сессию."""
        if self._session is None:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def close(self):
        """Закрывает HTTP сессию."""
        if self._session:
            await self._session.close()
            self._session = None
    
    def _image_to_base64(self, image_path: Path) -> str:
        """Конвертирует изображение в base64 строку."""
        with open(image_path, "rb") as img_file:
            img_data = img_file.read()
            base64_str = base64.b64encode(img_data).decode('utf-8')
            # Определяем MIME тип по расширению
            mime_type = "image/png" if image_path.suffix.lower() == ".png" else "image/jpeg"
            return f"data:{mime_type};base64,{base64_str}"
    
    async def recognize(self, image_path: Path) -> Optional[str]:
        """
        Распознает текст с изображения капчи через LLM.
        
        Args:
            image_path: Путь к изображению капчи
            
        Returns:
            Распознанный текст или None при ошибке
        """
        if not self.api_key:
            raise RosreestrLKError(
                "OpenRouter API ключ не указан. "
                "Установите OPENROUTER_API_KEY в .env или передайте при инициализации."
            )
        
        if not image_path.exists():
            raise RosreestrLKError(f"Файл изображения не найден: {image_path}")
        
        try:
            # Конвертируем изображение в base64
            image_base64 = self._image_to_base64(image_path)
            
            # Подготавливаем запрос
            session = await self._get_session()
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/your-repo",  # Опционально
                "X-Title": "Rosreestr Bot",  # Опционально
            }
            
            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Распознай текст на этом изображении капчи. В капче могут быть только буквы (латиница, a-z, A-Z) и цифры (0-9). Спецсимволов, пробелов и других символов нет. Верни ТОЛЬКО распознанный текст без дополнительных объяснений, кавычек, точек и других символов. Если не можешь распознать, верни пустую строку."
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": image_base64
                                }
                            }
                        ]
                    }
                ],
                "max_tokens": 50,
                "temperature": 0.1,  # Низкая температура для более точного результата
            }
            
            logger.info(f"Отправка запроса к LLM ({self.model}) для распознавания капчи...")
            
            async with session.post(
                self.OPENROUTER_API_URL,
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Ошибка API OpenRouter: {response.status} - {error_text}")
                    raise RosreestrLKError(f"Ошибка API: {response.status}")
                
                data = await response.json()
                
                # Извлекаем текст из ответа
                if "choices" in data and len(data["choices"]) > 0:
                    text = data["choices"][0]["message"]["content"].strip()
                    
                    # Очищаем результат (убираем кавычки, пробелы, точки и другие спецсимволы)
                    # Оставляем только буквы и цифры
                    import re
                    text = text.strip('"\'`.,;:!?()[]{}').strip()
                    # Убираем все пробелы, переносы строк
                    text = text.replace(' ', '').replace('\n', '').replace('\r', '').replace('\t', '')
                    # Оставляем только буквы и цифры
                    text = re.sub(r'[^a-zA-Z0-9]', '', text)
                    # Приводим все буквы к нижнему регистру (капча всегда в нижнем регистре)
                    text = text.lower()
                    
                    if text:
                        logger.info(f"Распознанный текст капчи (LLM {self.model}): {text}")
                        return text
                    else:
                        logger.warning("LLM вернул пустой текст")
                        return None
                else:
                    logger.warning("Неожиданный формат ответа от LLM")
                    return None
                    
        except aiohttp.ClientError as e:
            logger.error(f"Ошибка HTTP при запросе к LLM: {e}")
            raise RosreestrLKError(f"Ошибка сети: {str(e)}")
        except Exception as e:
            logger.error(f"Ошибка при распознавании капчи через LLM: {e}")
            raise RosreestrLKError(f"Не удалось распознать капчу: {str(e)}")
    
    async def __aenter__(self):
        """Поддержка async context manager."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Поддержка async context manager."""
        await self.close()
