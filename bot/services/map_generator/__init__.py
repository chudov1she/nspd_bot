"""
Модуль генерации карт земельных участков через парсинг nspd.gov.ru.
"""
from bot.services.map_generator.core import MapGenerator
from bot.services.map_generator.exceptions import MapGeneratorError
from bot.services.map_generator.generator import MapGeneratorService

# Глобальный экземпляр генератора
_map_generator: MapGenerator | None = None
_map_service: MapGeneratorService | None = None


def get_map_generator() -> MapGenerator:
    """Получить глобальный экземпляр генератора карт."""
    global _map_generator
    if _map_generator is None:
        _map_generator = MapGenerator()
    return _map_generator


def get_map_service() -> MapGeneratorService:
    """Получить глобальный экземпляр сервиса генерации карт."""
    global _map_service, _map_generator
    if _map_service is None:
        if _map_generator is None:
            _map_generator = MapGenerator()
        _map_service = MapGeneratorService(_map_generator)
    return _map_service


async def close_map_generator():
    """Закрыть глобальный генератор карт."""
    global _map_generator, _map_service
    if _map_generator:
        await _map_generator.close()
        _map_generator = None
        _map_service = None


__all__ = [
    'MapGenerator',
    'MapGeneratorService',
    'MapGeneratorError',
    'get_map_generator',
    'get_map_service',
    'close_map_generator',
]

