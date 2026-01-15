"""
Модуль для распознавания капчи с изображения.
Использует pytesseract (Tesseract OCR) с предобработкой изображения.
"""
from pathlib import Path
from typing import Optional
from loguru import logger
from PIL import Image, ImageEnhance, ImageFilter
import numpy as np

from bot.services.rosreestr_lk.exceptions import RosreestrLKError


class CaptchaRecognizer:
    """Распознавание текста с изображения капчи."""
    
    def __init__(self):
        self._tesseract_path = None
        self._tesseract_available = self._check_tesseract()
    
    def _check_tesseract(self) -> bool:
        """Проверяет доступность Tesseract OCR."""
        try:
            import pytesseract
            import platform
            
            # Пробуем выполнить простую команду
            pytesseract.get_tesseract_version()
            return True
        except ImportError:
            logger.warning("pytesseract не установлен. Установите: pip install pytesseract")
            return False
        except Exception as e:
            # На Windows пытаемся найти Tesseract в стандартных местах
            if platform.system() == "Windows":
                common_paths = [
                    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
                    r"C:\Tesseract-OCR\tesseract.exe",
                ]
                
                for path in common_paths:
                    if Path(path).exists():
                        try:
                            import pytesseract
                            pytesseract.pytesseract.tesseract_cmd = path
                            pytesseract.get_tesseract_version()
                            self._tesseract_path = path  # Сохраняем путь
                            logger.info(f"✅ Tesseract найден: {path}")
                            return True
                        except Exception:
                            continue
            
            logger.warning(f"Tesseract OCR недоступен: {e}")
            logger.warning("Установите Tesseract OCR:")
            logger.warning("  Windows: https://github.com/UB-Mannheim/tesseract/wiki")
            logger.warning("  Linux: sudo apt-get install tesseract-ocr tesseract-ocr-rus")
            logger.warning("  Mac: brew install tesseract")
            return False
    
    def preprocess_image(self, image_path: Path) -> Image.Image:
        """
        Предобрабатывает изображение капчи для лучшего распознавания.
        
        Args:
            image_path: Путь к изображению капчи
            
        Returns:
            Обработанное изображение PIL
        """
        try:
            # Открываем изображение
            img = Image.open(image_path)
            
            # Конвертируем в RGB если нужно
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Увеличиваем размер для лучшего распознавания (в 3 раза)
            width, height = img.size
            img = img.resize((width * 3, height * 3), Image.Resampling.LANCZOS)
            
            # Конвертируем в numpy array для обработки
            img_array = np.array(img)
            
            # Конвертируем в grayscale если еще не
            if len(img_array.shape) == 3:
                # Используем формулу для конвертации RGB в grayscale
                gray = np.dot(img_array[...,:3], [0.2989, 0.5870, 0.1140])
            else:
                gray = img_array
            
            # Нормализуем значения в диапазон 0-255
            gray = np.clip(gray, 0, 255).astype(np.uint8)
            
            # Применяем фильтр для удаления шума
            img_pil = Image.fromarray(gray)
            img_pil = img_pil.filter(ImageFilter.MedianFilter(size=3))
            
            # Улучшаем контраст
            enhancer = ImageEnhance.Contrast(img_pil)
            img_pil = enhancer.enhance(2.0)
            
            # Улучшаем резкость
            enhancer = ImageEnhance.Sharpness(img_pil)
            img_pil = enhancer.enhance(2.0)
            
            # Бинаризация (пороговая обработка)
            # Используем адаптивный порог для работы с градиентом
            # Пробуем несколько порогов и выбираем лучший
            threshold = np.mean(gray)
            
            # Пробуем разные пороги
            thresholds = [threshold * 0.8, threshold, threshold * 1.2, 128]
            best_binary = None
            best_contrast = 0
            
            for thresh in thresholds:
                binary = np.where(gray > thresh, 255, 0).astype(np.uint8)
                # Вычисляем контраст (разница между светлыми и темными областями)
                contrast = np.std(binary)
                if contrast > best_contrast:
                    best_contrast = contrast
                    best_binary = binary
            
            img_pil = Image.fromarray(best_binary)
            
            # Морфологические операции для удаления тонких линий (черная линия на капче)
            # Применяем фильтр для удаления тонких горизонтальных линий
            img_pil = img_pil.filter(ImageFilter.MaxFilter(size=3))
            
            # Дополнительная обработка: удаление мелких шумов (размер должен быть нечетным)
            img_pil = img_pil.filter(ImageFilter.MinFilter(size=3))
            
            return img_pil
            
        except Exception as e:
            logger.error(f"Ошибка при предобработке изображения: {e}")
            raise RosreestrLKError(f"Не удалось обработать изображение: {str(e)}")
    
    def recognize(self, image_path: Path, preprocess: bool = True) -> Optional[str]:
        """
        Распознает текст с изображения капчи.
        
        Args:
            image_path: Путь к изображению капчи
            preprocess: Применять ли предобработку изображения
            
        Returns:
            Распознанный текст или None при ошибке
        """
        if not self._tesseract_available:
            raise RosreestrLKError(
                "Tesseract OCR недоступен. Установите Tesseract и pytesseract."
            )
        
        try:
            import pytesseract
            
            # Устанавливаем путь к Tesseract если он был найден
            if self._tesseract_path:
                pytesseract.pytesseract.tesseract_cmd = self._tesseract_path
            
            # Предобрабатываем изображение если нужно
            if preprocess:
                processed_img = self.preprocess_image(image_path)
            else:
                processed_img = Image.open(image_path)
            
            # Настройки для распознавания
            # Используем только цифры и буквы (без спецсимволов)
            custom_config = r'--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
            
            # Сохраняем обработанное изображение для отладки
            debug_path = image_path.parent / f"{image_path.stem}_processed{image_path.suffix}"
            processed_img.save(debug_path)
            logger.debug(f"Обработанное изображение сохранено: {debug_path}")
            
            # Пробуем разные настройки PSM для лучшего распознавания
            psm_modes = [7, 8, 13]  # 7 - одна строка, 8 - одно слово, 13 - сырой текст
            
            for psm in psm_modes:
                try:
                    custom_config = f'--oem 3 --psm {psm} -c tessedit_char_whitelist=0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
                    text = pytesseract.image_to_string(processed_img, config=custom_config)
                    
                    # Очищаем результат (убираем пробелы, переносы строк)
                    text = text.strip().replace(' ', '').replace('\n', '').replace('\r', '')
                    # Приводим к нижнему регистру (капча всегда в нижнем регистре)
                    text = text.lower()
                    
                    if text:
                        logger.info(f"Распознанный текст капчи (PSM {psm}): {text}")
                        return text
                except Exception as e:
                    logger.debug(f"Ошибка при PSM {psm}: {e}")
                    continue
            
            # Если ничего не сработало, пробуем без whitelist
            try:
                custom_config = r'--oem 3 --psm 7'
                text = pytesseract.image_to_string(processed_img, config=custom_config)
                text = text.strip().replace(' ', '').replace('\n', '').replace('\r', '')
                # Приводим к нижнему регистру (капча всегда в нижнем регистре)
                text = text.lower()
                if text:
                    logger.info(f"Распознанный текст капчи (без whitelist): {text}")
                    return text
            except Exception as e:
                logger.debug(f"Ошибка при распознавании без whitelist: {e}")
            
            logger.warning("Не удалось распознать текст с капчи")
            logger.warning(f"Проверьте обработанное изображение: {debug_path}")
            return None
                
        except ImportError:
            raise RosreestrLKError("pytesseract не установлен. Установите: pip install pytesseract")
        except Exception as e:
            logger.error(f"Ошибка при распознавании капчи: {e}")
            raise RosreestrLKError(f"Не удалось распознать капчу: {str(e)}")
    
    def recognize_with_confidence(self, image_path: Path, preprocess: bool = True) -> tuple[Optional[str], float]:
        """
        Распознает текст с изображения капчи и возвращает уверенность.
        
        Args:
            image_path: Путь к изображению капчи
            preprocess: Применять ли предобработку изображения
            
        Returns:
            Кортеж (распознанный текст, уверенность в процентах) или (None, 0.0) при ошибке
        """
        if not self._tesseract_available:
            raise RosreestrLKError(
                "Tesseract OCR недоступен. Установите Tesseract и pytesseract."
            )
        
        try:
            import pytesseract
            
            # Устанавливаем путь к Tesseract если он был найден
            if self._tesseract_path:
                pytesseract.pytesseract.tesseract_cmd = self._tesseract_path
            
            # Предобрабатываем изображение если нужно
            if preprocess:
                processed_img = self.preprocess_image(image_path)
            else:
                processed_img = Image.open(image_path)
            
            # Настройки для распознавания
            custom_config = r'--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
            
            # Получаем данные с уверенностью
            data = pytesseract.image_to_data(processed_img, config=custom_config, output_type=pytesseract.Output.DICT)
            
            # Извлекаем текст и уверенность
            text_parts = []
            confidences = []
            
            for i in range(len(data['text'])):
                if int(data['conf'][i]) > 0:
                    text_parts.append(data['text'][i])
                    confidences.append(float(data['conf'][i]))
            
            text = ''.join(text_parts).strip().replace(' ', '').replace('\n', '').replace('\r', '')
            # Приводим к нижнему регистру (капча всегда в нижнем регистре)
            text = text.lower()
            
            if text and confidences:
                avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
                logger.info(f"Распознанный текст капчи: {text} (уверенность: {avg_confidence:.1f}%)")
                return text, avg_confidence
            else:
                logger.warning("Не удалось распознать текст с капчи")
                return None, 0.0
                
        except ImportError:
            raise RosreestrLKError("pytesseract не установлен. Установите: pip install pytesseract")
        except Exception as e:
            logger.error(f"Ошибка при распознавании капчи: {e}")
            raise RosreestrLKError(f"Не удалось распознать капчу: {str(e)}")
