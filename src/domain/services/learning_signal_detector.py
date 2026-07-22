"""Señales de aprendizaje en el lenguaje del estudiante (ask).

No sustituyen un quiz: son evidencia débil (auto-reporte / confusión) que
debe ajustar el perfil antes de decidir la estrategia.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class LearningSignalKind(str, Enum):
    CONFUSION = "confusion"  # no entiende / perdido
    NOVICE = "novice"  # primera vez / no sé nada
    HELP = "help"  # pide pista / ayuda
    NONE = "none"


@dataclass(frozen=True)
class LearningSignal:
    kind: LearningSignalKind
    strength: float  # 0..1
    concepts_hint: tuple[str, ...]


_CONFUSION = re.compile(
    r"\b(no\s+entiendo|no\s+comprendo|estoy\s+confundid[oa]|me\s+confund[eé]|"
    r"no\s+me\s+queda\s+claro|perdid[oa]|no\s+tengo\s+idea)\b",
    re.IGNORECASE,
)
_NOVICE = re.compile(
    r"\b(no\s+s[eé]\s+nada|nunca\s+he\s+visto|primera\s+vez|soy\s+principiante|"
    r"desde\s+cero|no\s+conozco|no\s+tengo\s+base)\b",
    re.IGNORECASE,
)
_HELP = re.compile(
    r"\b(ayuda|ayudame|ayúdame|dame\s+una\s+pista|solo\s+una\s+pista|"
    r"expl[ií]came\s+f[aá]cil|como\s+si\s+fuera)\b",
    re.IGNORECASE,
)

# Conceptos frecuentes en preguntas de álgebra / genéricas (heurística ligera)
_CONCEPT_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bvariables?\b", re.I), "variable"),
    (re.compile(r"\becuaci[oó]n(es)?\b", re.I), "ecuación"),
    (re.compile(r"\bdistributiv[ao]\b", re.I), "propiedad distributiva"),
    (re.compile(r"\bdespejar\b|\bresolver\b", re.I), "resolver ecuación"),
    (re.compile(r"\bexpresi[oó]n(es)?\b", re.I), "expresión algebraica"),
]


class LearningSignalDetector:
    """Detecta señales de lucha/novato en el texto de la pregunta del estudiante."""

    def detect(self, question: str) -> LearningSignal:
        text = (question or "").strip()
        if not text:
            return LearningSignal(LearningSignalKind.NONE, 0.0, ())

        concepts = tuple(
            label for pattern, label in _CONCEPT_PATTERNS if pattern.search(text)
        )

        if _NOVICE.search(text):
            return LearningSignal(LearningSignalKind.NOVICE, 0.9, concepts)
        if _CONFUSION.search(text):
            return LearningSignal(LearningSignalKind.CONFUSION, 0.75, concepts)
        if _HELP.search(text):
            return LearningSignal(LearningSignalKind.HELP, 0.45, concepts)
        return LearningSignal(LearningSignalKind.NONE, 0.0, concepts)
