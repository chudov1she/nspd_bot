"""
Исключения для генератора карт.
"""


class MapGeneratorError(Exception):
    """Исключение при генерации карты."""
    pass


class CadastralPlotNotFoundError(MapGeneratorError):
    """Исключение когда кадастровый участок не найден."""
    pass
