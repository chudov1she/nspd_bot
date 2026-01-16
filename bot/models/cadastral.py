"""
Модели данных для объектов недвижимости.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class RealEstateObject:
    """Модель объекта недвижимости из Росреестра."""
    
    cadastral_number: str
    object_type: Optional[str] = None  # Земельный участок, Здание, Помещение, Сооружение
    address: Optional[str] = None
    area: Optional[float] = None  # кв. м
    category: Optional[str] = None
    permitted_use: Optional[str] = None
    cadastral_value: Optional[float] = None
    rights: Optional[str] = None
    owner: Optional[str] = None
    encumbrances: Optional[str] = None
    status: Optional[str] = None
    date_assigned: Optional[str] = None
    engineering_communications: Optional[str] = None
    form: Optional[str] = None  # Только для земельных участков
    coordinates: Optional[dict] = None  # {x, y} для карты (только для земельных участков)
    map_image_path: Optional[str] = None  # Путь к файлу карты (только для земельных участков)
    # Дополнительные поля
    level: Optional[str] = None  # Этаж
    purpose: Optional[str] = None  # Назначение
    reg_date: Optional[str] = None  # Дата регистрации права
    info_update_date: Optional[str] = None  # Дата обновления информации
    old_cadastral_number: Optional[str] = None  # Старый кадастровый номер
    cadastral_cost_date: Optional[str] = None  # Дата кадастровой стоимости
    
    # Флаги ошибок
    error: Optional[str] = None
    error_code: Optional[str] = None
    api_balance: Optional[float] = None  # Баланс API после запроса
    
    def is_land_plot(self) -> bool:
        """Проверяет, является ли объект земельным участком."""
        return self.object_type and "земельный участок" in self.object_type.lower()
    
    def has_error(self) -> bool:
        """Проверяет, есть ли ошибка при получении данных."""
        return self.error is not None
    
    def to_dict(self) -> dict:
        """
        Преобразует объект в словарь для Excel.
        Возвращает только поля, указанные в требованиях к отчёту.
        """
        # Форматируем площадь (без разделителя тысяч, запятая для десятичных)
        area_str = ""
        if self.area is not None:
            if self.area == int(self.area):
                # Целое число: 2956
                area_str = str(int(self.area))
            else:
                # С десятичными: 2956,50
                area_str = f"{self.area:.2f}".replace(".", ",")
        
        # Форматируем кадастровую стоимость (без разделителя тысяч, запятая для десятичных)
        cost_str = ""
        if self.cadastral_value is not None:
            # Формат: 24224607,11 (без точек для тысяч)
            cost_str = f"{self.cadastral_value:.2f}".replace(".", ",")
        
        return {
            "№": "",  # Будет заполнено при создании таблицы
            "Наименование": self.object_type or "",
            "Кадастровый номер": self.cadastral_number,
            "Адрес (местоположение)": self.address or "",
            "Общая площадь, кв. м": area_str,
            "Категория": self.category or "",
            "Разрешенное использование": self.permitted_use or "",
            "Кадастровая стоимость": cost_str,
            "Передаваемые права": self.rights or "",
            "Правообладатель (собственник)": self.owner or "",
            "Обременения (ограничения)": self.encumbrances or "Отсутствуют",
            "Этаж": self.level or "",
            "Статус объекта": self.status or "",
            "Назначение": self.purpose or "",
            "Дата регистрации права": self.reg_date or "",
            "Дата обновления информации": self.info_update_date or "",
            "Старый кадастровый номер": self.old_cadastral_number or "",
            "Дата кадастровой стоимости": self.cadastral_cost_date or "",
        }
    
    def get_cadastral_number_for_matching(self) -> str:
        """Возвращает кадастровый номер для сопоставления (нормализованный)."""
        return self.cadastral_number.strip()

