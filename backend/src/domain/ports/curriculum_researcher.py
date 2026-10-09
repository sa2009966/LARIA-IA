"""Puerto del investigador de temarios (ADR-039): busca en internet qué se enseña en cada nivel."""
from __future__ import annotations

from typing import Protocol

from src.domain.ports.lesson_generator import SyllabusItem


class CurriculumResearcher(Protocol):
    async def research(
        self, topic_label: str, level: str, avoid: tuple[str, ...] = ()
    ) -> list[SyllabusItem]:
        """Temario del nivel con ideas clave y fuentes verificadas. Lanza si no puede."""
        ...


class CurriculumResearchRepository(Protocol):
    """Caché global por (tema canónico, nivel): se investiga una vez para todos."""

    async def find(self, topic: str, level: str) -> list[SyllabusItem] | None: ...

    async def save(self, topic: str, level: str, items: list[SyllabusItem]) -> None: ...
