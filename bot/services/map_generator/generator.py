"""
Основная логика генерации карт.
"""
import asyncio
from pathlib import Path
from typing import Optional
from loguru import logger

from bot.services.map_generator.core import MapGenerator
from bot.services.map_generator.exceptions import MapGeneratorError, CadastralPlotNotFoundError


class MapGeneratorService:
    """Сервис генерации карт, объединяющий все компоненты."""
    
    def __init__(self, generator: MapGenerator):
        self._generator = generator
    
    async def generate_map(
        self,
        cadastral_number: str,
        coordinates: Optional[dict] = None,
        output_dir: Optional[Path] = None
    ) -> Optional[Path]:
        """
        Генерирует карту земельного участка.
        Поиск выполняется по кадастровому номеру, координаты не требуются.
        
        Args:
            cadastral_number: Кадастровый номер участка
            coordinates: Словарь с координатами {'x': float, 'y': float} (опционально, не используется)
            output_dir: Директория для сохранения карты (опционально)
            
        Returns:
            Path к сохраненному файлу карты или None при ошибке
            
        Raises:
            MapGeneratorError: При ошибках генерации
        """
        
        try:
            # Инициализируем браузер если нужно
            if self._generator._browser is None:
                await self._generator._init_browser()
            
            # Подготавливаем директорию и путь к файлу
            output_dir = self._generator.screenshot_handler.prepare_output_dir(output_dir)
            map_file = self._generator.screenshot_handler.get_map_file_path(
                output_dir, cadastral_number
            )
            safe_cadastral = cadastral_number.replace(":", "_")
            
            logger.info(f"Генерация карты для {cadastral_number}")
            
            # Открываем страницу карты
            await self._generator.navigation.open_map_page()
            
            # Ищем кадастровый номер
            await self._generator.navigation.search_cadastral_number(cadastral_number)
            
            # Ждем результатов поиска
            await self._generator.navigation.wait_for_search_results()
            
            # Сохраняем HTML для отладки
            await self._generator.navigation.save_debug_html(output_dir, safe_cadastral)
            
            # Кликаем на кнопку с кадастровым номером
            button_clicked = await self._generator.click_handler.click_cadastral_button(cadastral_number)
            
            # Если кнопка не найдена, значит участок не существует
            if not button_clicked:
                error_msg = f"Кадастровый участок {cadastral_number} не найден"
                logger.warning(error_msg)
                raise CadastralPlotNotFoundError(error_msg)
            
            # Ждем загрузки карты
            await self._generator.navigation.wait_for_map_load()
            
            # Уменьшаем масштаб карты для более широкого обзора (zoom out)
            # Ищем кнопку уменьшения масштаба в zoom-control
            try:
                # Ищем zoom-control и кнопку уменьшения масштаба внутри него
                # Структура: <zoom-control> <m-tooltip content="Уменьшить масштаб карты"> <m-button>
                zoom_out_button = self._generator.page.locator(
                    'zoom-control m-tooltip[content*="Уменьшить"] m-button'
                ).first
                
                # Ждем появления кнопки и кликаем 2 раза
                await zoom_out_button.wait_for(state='visible', timeout=3000)
                await zoom_out_button.click()
                await asyncio.sleep(0.5)
                await zoom_out_button.click()
                await asyncio.sleep(0.5)
                logger.debug("Масштаб карты уменьшен (2 клика)")
            except Exception as e:
                logger.debug(f"Не удалось изменить масштаб через основной селектор: {e}")
                # Пробуем альтернативный способ - просто первую кнопку в zoom-control
                try:
                    zoom_out_alt = self._generator.page.locator('zoom-control m-button').first
                    await zoom_out_alt.wait_for(state='visible', timeout=3000)
                    await zoom_out_alt.click()
                    await asyncio.sleep(0.5)
                    await zoom_out_alt.click()
                    await asyncio.sleep(0.5)
                    logger.debug("Масштаб карты уменьшен (альтернативный способ, 2 клика)")
                except Exception as e2:
                    logger.warning(f"Не удалось изменить масштаб карты: {e2}")
            
            # Делаем скриншот
            await self._generator.screenshot_handler.take_screenshot(
                self._generator.page, map_file
            )
            
            # Обрезаем изображение
            self._generator.screenshot_handler.crop_image(map_file)
            
            logger.info(f"✅ Карта успешно сгенерирована: {map_file}")
            return map_file
        
        except Exception as e:
            logger.error(f"Ошибка при генерации карты для {cadastral_number}: {e}")
            raise MapGeneratorError(f"Не удалось сгенерировать карту: {str(e)}")
    
    async def generate_map_batch(
        self,
        land_plots: list,
        output_dir: Optional[Path] = None
    ) -> dict:
        """
        Генерирует карты для нескольких земельных участков.
        
        Args:
            land_plots: Список словарей с данными участков:
                [{'cadastral_number': str, 'coordinates': {'x': float, 'y': float}}, ...]
            output_dir: Директория для сохранения карт
            
        Returns:
            Словарь {cadastral_number: Path или None}
        """
        import asyncio
        
        results = {}
        
        # Инициализируем браузер один раз для всех участков
        if self._generator._browser is None:
            await self._generator._init_browser()
        
        for plot in land_plots:
            cadastral_number = plot.get('cadastral_number')
            coordinates = plot.get('coordinates')  # Опционально - поиск по номеру
            
            if not cadastral_number:
                results[cadastral_number] = None
                continue
            
            try:
                map_path = await self.generate_map(
                    cadastral_number=cadastral_number,
                    coordinates=coordinates,
                    output_dir=output_dir
                )
                results[cadastral_number] = map_path
                
                # Небольшая задержка между запросами
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Ошибка при генерации карты для {cadastral_number}: {e}")
                results[cadastral_number] = None
        
        return results

