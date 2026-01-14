"""
Обработчик создания скриншотов и обработки изображений.
"""
from pathlib import Path
from typing import Optional
from loguru import logger
from PIL import Image, ImageOps

from bot.config.settings import settings


class ScreenshotHandler:
    """Обработчик скриншотов и обработки изображений."""
    
    def __init__(self):
        pass
    
    def prepare_output_dir(self, output_dir: Optional[Path] = None) -> Path:
        """
        Подготавливает директорию для сохранения карт.
        
        Args:
            output_dir: Директория для сохранения (опционально)
            
        Returns:
            Path к директории
        """
        if output_dir is None:
            output_dir = settings.OUTPUT_DIR / "maps"
        else:
            output_dir = Path(output_dir)
        
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir
    
    def get_map_file_path(self, output_dir: Path, cadastral_number: str) -> Path:
        """
        Генерирует путь к файлу карты.
        
        Args:
            output_dir: Директория для сохранения
            cadastral_number: Кадастровый номер
            
        Returns:
            Path к файлу карты
        """
        safe_cadastral = cadastral_number.replace(":", "_")
        return output_dir / f"{safe_cadastral}_map.png"
    
    async def take_screenshot(self, page, map_file: Path):
        """
        Делает скриншот страницы.
        
        Args:
            page: Объект страницы Playwright
            map_file: Путь к файлу для сохранения
        """
        logger.debug(f"Делаем скриншот карты: {map_file}")
        await page.screenshot(path=str(map_file), full_page=False)
    
    def crop_image(self, map_file: Path):
        """
        Обрезает изображение, убирая лишние элементы и создавая прямоугольную форму карты.
        Обрезает больше сверху и снизу для получения прямоугольной формы (ширина > высота).
        
        Args:
            map_file: Путь к файлу изображения
        """
        try:
            img = Image.open(map_file)
            # Обрезаем изображение: убираем верх, низ, лево, право
            # Параметры: (left, top, right, bottom) в пикселях
            # Увеличиваем обрезку сверху и снизу для прямоугольной формы
            border = (550, 120, 150, 180)  # (left, top, right, bottom)
            # top=120 и bottom=180 - больше обрезаем сверху и снизу для прямоугольной формы
            cropped_img = ImageOps.crop(img, border)
            cropped_img.save(map_file)
            logger.debug(f"Изображение обрезано (прямоугольная форма) и сохранено: {map_file}")
        except Exception as e:
            logger.warning(f"Не удалось обрезать изображение: {e}")
            # Оставляем оригинальный скриншот

