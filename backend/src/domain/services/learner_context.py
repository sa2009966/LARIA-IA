"""Lo que el tutor sabe del estudiante cuando no hay material (ADR-022).

Con material decide el motor pedagógico, con mastery por concepto. Sin material
no hay conceptos medidos del documento, pero sí dos datos que el estudiante dio
él mismo: su nivel en los temas en que se niveló y cómo quiere que le expliquen.
"""
from __future__ import annotations

from dataclasses import dataclass

from src.domain.services.cognitive_style import CognitiveStyle

#: Cuántos niveles guardados se mencionan cuando no hay un tema concreto.
MAX_LEVELS_IN_PROMPT = 5


@dataclass(frozen=True)
class LearnerContext:
    style: CognitiveStyle | None = None
    #: `(etiqueta, nivel)` del tema que pidió aprender, si ya se niveló en él.
    topic_level: tuple[str, str] | None = None
    #: Otros niveles guardados `(etiqueta, nivel)`, solo si no hay `topic_level`.
    levels: tuple[tuple[str, str], ...] = ()

    def __bool__(self) -> bool:
        return bool(self.style or self.topic_level or self.levels)
