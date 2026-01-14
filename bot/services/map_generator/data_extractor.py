"""
Извлечение данных об объекте недвижимости со страницы карты nspd.gov.ru.
"""
import re
from typing import Optional, Dict
from loguru import logger

from bot.models.cadastral import RealEstateObject


class MapDataExtractor:
    """Извлекает данные об объекте недвижимости со страницы карты."""
    
    def __init__(self, page):
        self._page = page
    
    async def extract_object_data(self, cadastral_number: str) -> Optional[RealEstateObject]:
        """
        Извлекает данные об объекте недвижимости со страницы карты.
        
        Args:
            cadastral_number: Кадастровый номер для поиска
            
        Returns:
            RealEstateObject с данными или None если не удалось извлечь
        """
        try:
            # Ждем появления панели с информацией
            await self._page.wait_for_selector(
                "#tabpanel-info, div[role='tabpanel']",
                timeout=10000
            )
            
            # Даем время на загрузку всех данных
            await self._page.wait_for_timeout(2000)
            
            # Извлекаем данные через JavaScript
            data = await self._page.evaluate("""
                () => {
                    // Ищем панель с информацией
                    const infoContainer = document.querySelector('#tabpanel-info, div[role="tabpanel"][aria-labelledby*="tab-info"]');
                    if (!infoContainer) {
                        // Пробуем найти через slot
                        const slot = document.querySelector('slot');
                        if (slot) {
                            const assignedNodes = slot.assignedNodes();
                            for (let node of assignedNodes) {
                                if (node.querySelector && node.querySelector('.info-container')) {
                                    return extractDataFromContainer(node);
                                }
                            }
                        }
                        return null;
                    }
                    
                    function extractDataFromContainer(container) {
                        const result = {};
                        
                        // Ищем все контейнеры с информацией
                        const infoContainers = container.querySelectorAll('.info-container');
                        
                        infoContainers.forEach(container => {
                            // Ищем метку (label)
                            const labelElement = container.querySelector('m-typography[text], m-typography');
                            // Ищем значение
                            const valueElement = container.querySelector('m-string-item[text], m-string-item, m-typography[text]');
                            
                            if (labelElement) {
                                let label = labelElement.getAttribute('text');
                                if (!label) {
                                    label = labelElement.textContent?.trim();
                                }
                                
                                let value = null;
                                if (valueElement) {
                                    value = valueElement.getAttribute('text');
                                    if (!value) {
                                        value = valueElement.textContent?.trim();
                                    }
                                }
                                
                                // Если не нашли значение в valueElement, ищем в следующем элементе
                                if (!value && labelElement.nextElementSibling) {
                                    const nextEl = labelElement.nextElementSibling;
                                    value = nextEl.getAttribute('text') || nextEl.textContent?.trim();
                                }
                                
                                if (label && value && value !== label) {
                                    result[label] = value;
                                }
                            }
                        });
                        
                        return result;
                    }
                    
                    return extractDataFromContainer(infoContainer);
                }
            """)
            
            if not data or len(data) == 0:
                logger.warning("Не удалось извлечь данные со страницы карты")
                return None
            
            logger.info(f"Извлечено {len(data)} полей данных со страницы карты")
            
            # Парсим данные в объект RealEstateObject
            return self._parse_map_data(cadastral_number, data)
            
        except Exception as e:
            logger.error(f"Ошибка при извлечении данных со страницы карты: {e}")
            return None
    
    def _parse_map_data(self, cadastral_number: str, data: Dict[str, str]) -> RealEstateObject:
        """
        Парсит извлеченные данные в объект RealEstateObject.
        
        Args:
            cadastral_number: Кадастровый номер
            data: Словарь с данными из HTML
            
        Returns:
            RealEstateObject
        """
        # Функция для безопасного извлечения значения
        def get_value(key_variants: list) -> Optional[str]:
            for key in key_variants:
                if key in data:
                    value = data[key].strip()
                    return value if value and value != '-' else None
            return None
        
        # Функция для парсинга площади
        def parse_area(area_str: Optional[str]) -> Optional[float]:
            if not area_str:
                return None
            # Убираем "кв. м" и пробелы, заменяем запятую на точку
            cleaned = area_str.replace("кв. м", "").replace("кв.м", "").strip()
            cleaned = cleaned.replace(",", ".").replace(" ", "")
            try:
                return float(cleaned)
            except (ValueError, TypeError):
                return None
        
        # Функция для парсинга кадастровой стоимости
        def parse_cost(cost_str: Optional[str]) -> Optional[float]:
            if not cost_str:
                return None
            # Убираем "руб." и пробелы, заменяем запятую на точку
            cleaned = cost_str.replace("руб.", "").replace("руб", "").strip()
            cleaned = cleaned.replace(",", ".").replace(" ", "")
            try:
                return float(cleaned)
            except (ValueError, TypeError):
                return None
        
        # Функция для парсинга даты
        def parse_date(date_str: Optional[str]) -> Optional[str]:
            if not date_str or date_str == '-':
                return None
            # Формат: DD.MM.YYYY
            return date_str.strip()
        
        # Извлекаем данные
        object_type = get_value([
            "Вид объекта недвижимости",
            "Вид объекта"
        ])
        
        area_str = get_value([
            "Площадь уточненная",
            "Площадь",
            "Площадь декларированная"
        ])
        area = parse_area(area_str)
        
        address = get_value(["Адрес"])
        
        category = get_value([
            "Категория земель",
            "Категория"
        ])
        
        permitted_use = get_value([
            "Вид разрешенного использования",
            "Разрешенное использование"
        ])
        
        cost_str = get_value(["Кадастровая стоимость"])
        cadastral_value = parse_cost(cost_str)
        
        status = get_value(["Статус"])
        
        date_assigned = parse_date(get_value(["Дата присвоения"]))
        
        # Формируем права (форма собственности)
        ownership = get_value(["Форма собственности"])
        rights = ownership if ownership else None
        
        # Создаем объект
        return RealEstateObject(
            cadastral_number=cadastral_number,
            object_type=object_type,
            address=address,
            area=area,
            category=category,
            permitted_use=permitted_use,
            cadastral_value=cadastral_value,
            rights=rights,
            status=status,
            date_assigned=date_assigned
        )
