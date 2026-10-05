"""Temario investigado en internet para los tramos intermedio y avanzado (ADR-039).

Se investiga UNA vez por (tema canónico, nivel) y se guarda para todos: la búsqueda
cuesta ~18 000 tokens y ~15 s. Si falla, devuelve None y quien llama usa el temario
del modelo, como antes: la búsqueda mejora la ruta, no la condiciona.
"""
from __future__ import annotations

import logging

from src.domain.ports.curriculum_researcher import (
    CurriculumResearcher,
    CurriculumResearchRepository,
)
from src.domain.ports.lesson_generator import SyllabusItem

logger = logging.getLogger("laria.research")

#: El básico lo cubre bien el modelo; lo que no se cumplía era intermedio y avanzado.
RESEARCHED_LEVELS = frozenset({"intermedio", "avanzado"})


class CurriculumResearchService:
    def __init__(
        self,
        researcher: CurriculumResearcher | None,
        repository: CurriculumResearchRepository,
    ) -> None:
        self._researcher = researcher
        self._repo = repository

    async def syllabus(
        self, topic: str, label: str, level: str | None, avoid: tuple[str, ...] = ()
    ) -> list[SyllabusItem] | None:
        if level not in RESEARCHED_LEVELS or not topic:
            return None
        guardado = await self._repo.find(topic, level)
        if guardado:
            return guardado
        if self._researcher is None:
            return None
        try:
            items = await self._researcher.research(label, level, avoid)
        except Exception as exc:  # noqa: BLE001 — sin investigación, temario del modelo
            logger.warning("investigacion_fallo tema=%s nivel=%s (%s)", topic, level, exc)
            return None
        if items:
            await self._repo.save(topic, level, items)
        return items or None
