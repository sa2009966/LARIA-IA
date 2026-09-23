"""Señales de aprendizaje en el lenguaje del estudiante (ask).

No sustituyen un quiz: son evidencia débil (auto-reporte / confusión) que
debe ajustar el perfil antes de decidir la estrategia.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from src.domain.concept_identity import canonicalize_concept
from src.domain.subject_areas import EXACTAS, SOCIALES, area_of_subject, matches_area


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


# Los patrones se evalúan sobre el texto **normalizado** (sin acentos, en
# minúsculas), así que se escriben sin tildes: una sola forma por expresión en
# vez de una alternativa por acento. Antes, "no logro captarlo" o "no me entra"
# no disparaban nada y el turno se atendía como si el alumno no hubiera pedido
# ayuda (W7 de la auditoría).
_CONFUSION = re.compile(
    r"\b(no\s+(lo\s+)?entiendo|no\s+(lo\s+)?comprendo|no\s+(me\s+)?queda\s+claro|"
    r"no\s+(lo\s+)?(logro|consigo)\s+\w+|no\s+me\s+entra|no\s+lo\s+(pillo|capto|agarro)|"
    r"estoy\s+confundid[oa]|me\s+confund[eo]|me\s+(perdi|pierdo)|estoy\s+perdid[oa]|"
    r"perdid[oa]|no\s+tengo\s+idea|ni\s+idea|me\s+cuesta(\s+mucho)?|"
    r"sigo\s+sin\s+entender|no\s+se\s+por\s+que)\b",
    re.IGNORECASE,
)
_NOVICE = re.compile(
    r"\b(no\s+se\s+nada|nunca\s+(lo\s+)?(he\s+)?(visto|di|estudiado)|primera\s+vez|"
    r"soy\s+(principiante|nuevo|nueva)|desde\s+cero|no\s+conozco|no\s+tengo\s+base|"
    r"recien\s+(empiezo|estoy\s+empezando)|arranco\s+de\s+cero)\b",
    re.IGNORECASE,
)
_HELP = re.compile(
    r"\b(ayuda|ayudame|dame\s+una\s+pista|solo\s+una\s+pista|una\s+pista|"
    r"expl[ií]ca(me|melo)?\s+(facil|mas\s+facil|mas\s+simple|otra\s+vez|de\s+nuevo)|"
    r"como\s+si\s+fuera|paso\s+a\s+paso|me\s+(puedes|podes)\s+ayudar|"
    r"me\s+(lo\s+)?explicas)\b",
    re.IGNORECASE,
)

# Conceptos frecuentes en preguntas (heurística ligera), con su área: la misma
# palabra significa cosas distintas según la materia del material (ADR-011).
_CONCEPT_PATTERNS: list[tuple[re.Pattern[str], str, str | None]] = [
    (re.compile(r"\bvariables?\b", re.I), "variable", EXACTAS),
    (re.compile(r"\becuaci[oó]n(es)?\b", re.I), "ecuación", EXACTAS),
    (re.compile(r"\bdistributiv[ao]\b", re.I), "propiedad distributiva", EXACTAS),
    (re.compile(r"\bdespejar\b|\bresolver\b", re.I), "resolver ecuación", EXACTAS),
    (re.compile(r"\bexpresi[oó]n(es)?\b", re.I), "expresión algebraica", EXACTAS),
    (re.compile(r"\bdesigualdad(es)?\b", re.I), "desigualdad", EXACTAS),
    (re.compile(r"\bdesigualdad(es)?\b", re.I), "desigualdad social", SOCIALES),
    (re.compile(r"\bpobreza\b", re.I), "pobreza", SOCIALES),
    (re.compile(r"\bgini\b", re.I), "indice de gini", SOCIALES),
    (re.compile(r"\bmovilidad\s+social\b", re.I), "movilidad social", SOCIALES),
    (re.compile(r"\binformalidad\b", re.I), "informalidad laboral", SOCIALES),
]


class LearningSignalDetector:
    """Detecta señales de lucha/novato en el texto de la pregunta del estudiante."""

    def detect(self, question: str, subject: str | None = None) -> LearningSignal:
        """Señal y conceptos de la pregunta, acotados a la materia del material.

        Sin `subject` no se filtra nada: es la opción segura para llamadas que
        no conocen el documento.
        """
        text = (question or "").strip()
        if not text:
            return LearningSignal(LearningSignalKind.NONE, 0.0, ())

        # Una sola normalización para todo: acentos, mayúsculas y espacios.
        normalizado = canonicalize_concept(text)
        area = area_of_subject(subject)
        concepts = tuple(
            canonicalize_concept(label)
            for pattern, label, pattern_area in _CONCEPT_PATTERNS
            if matches_area(pattern_area, area) and pattern.search(normalizado)
        )

        if _NOVICE.search(normalizado):
            return LearningSignal(LearningSignalKind.NOVICE, 0.9, concepts)
        if _CONFUSION.search(normalizado):
            return LearningSignal(LearningSignalKind.CONFUSION, 0.75, concepts)
        if _HELP.search(normalizado):
            return LearningSignal(LearningSignalKind.HELP, 0.45, concepts)
        return LearningSignal(LearningSignalKind.NONE, 0.0, concepts)
