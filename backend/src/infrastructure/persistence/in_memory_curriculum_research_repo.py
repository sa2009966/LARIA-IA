from src.domain.ports.lesson_generator import SyllabusItem


class InMemoryCurriculumResearchRepository:
    """Caché de temarios investigados (ADR-039) para desarrollo y tests."""

    def __init__(self) -> None:
        self._data: dict[tuple[str, str], list[SyllabusItem]] = {}

    async def find(self, topic: str, level: str) -> list[SyllabusItem] | None:
        items = self._data.get((topic, level))
        return list(items) if items is not None else None

    async def save(self, topic: str, level: str, items: list[SyllabusItem]) -> None:
        self._data[(topic, level)] = list(items)
