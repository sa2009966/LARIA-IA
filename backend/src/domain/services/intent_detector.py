"""Detector de intención del estudiante para el tutor.

Clasifica el mensaje de entrada en una intención de alto nivel que React
usará para seleccionar el componente de UI correcto (respuesta, quiz, hint,
celebración o aprendizaje). Determinista (regex/palabras clave) — no usa LLM.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from src.domain.services.learning_signal_detector import LearningSignalDetector


class TutorIntent(str, Enum):
    LEARN = "learn"  # quiere aprender/explicar un tema
    QUIZ = "quiz"  # pide un cuestionario/examen/práctica
    HINT = "hint"  # pide ayuda/pista/está confundido
    CELEBRATE = "celebrate"  # respuesta afirmativa a un logro
    GENERAL = "general"  # conversación general sin intención pedagógica
    NONE = "none"


@dataclass(frozen=True)
class Intention:
    intent: TutorIntent
    confidence: float  # 0..1
    topic_hint: str | None = None  # concepto detectado en la pregunta


_LEARN = re.compile(
    r"\b(?:qu[eé]\s+es|qu[eé]\s+son|qu[eé]\s+significa|expl[ií]ca(?:r|rme|me)?|"
    r"ense[ñn]a(?:r)?|d[eé]fin(?:e|ici[oó]n)?|concepto de|qu[ií]ero\s+aprender|"
    r"introdu[cç](?:e|ir)?|empecemos|por\s+d[oó]nde|ay[úu]dame\s+a\s+entender|"
    r"quiero\s+entender|vamos\s+a\s+ver)\b",
    re.IGNORECASE,
)
_QUIZ = re.compile(
    r"\b(quiz|examen|preg[úu]ntame|prueba|test|practica|ejercicios|"
    r"ponme|evalu[aá]|reto|checkpoint|retroalimentaci[oó]n)\b",
    re.IGNORECASE,
)
_CELEBRATE = re.compile(
    r"\b(entend[ií]|me\s+queda\s+claro|genial|excelente|s[ií]\s+s[eé]\b|"
    r"lo\s+logre|perfecto|bien|listo|continuemos|d[aá]le)\b",
    re.IGNORECASE,
)

# Conceptos frecuentes al pedir aprender (heurística ligera, reuso del detector)
_TOPIC_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bgrafos?\b", re.I), "grafos"),
    (re.compile(r"\bdfs\b|\bbfs\b", re.I), "recorrido de grafos"),
    (re.compile(r"\bdijkstra\b", re.I), "dijkstra"),
    (re.compile(r"\b[áa]lgebra\b", re.I), "álgebra"),
    (re.compile(r"\becuaci[oó]n(es)?\b", re.I), "ecuaciones"),
    (re.compile(r"\bpolinomios?\b", re.I), "polinomios"),
    (re.compile(r"\bmatrices?\b|\bmatriz\b", re.I), "matrices"),
    (re.compile(r"\bderivadas?\b", re.I), "derivadas"),
    (re.compile(r"\bintegrales?\b", re.I), "integrales"),
    (re.compile(r"\bl[ií]mites?\b", re.I), "límites"),
    (re.compile(r"\bprobabilidad", re.I), "probabilidad"),
    (re.compile(r"\bestad[ií]stica", re.I), "estadística"),
]


class IntentDetector:
    """Detecta intención pedagógica en el mensaje del estudiante."""

    def __init__(self) -> None:
        self._signal = LearningSignalDetector()

    def detect(self, message: str) -> Intention:
        text = (message or "").strip()
        if not text:
            return Intention(TutorIntent.NONE, 0.0, None)

        topic = next(
            (label for pattern, label in _TOPIC_PATTERNS if pattern.search(text)),
            None,
        )

        # Señal de ayuda/confusión tiene prioridad: pedir ayuda ≠ aprender.
        signal = self._signal.detect(text)
        if signal.kind.value in ("confusion", "help", "novice"):
            return Intention(TutorIntent.HINT, signal.strength, topic)

        if _QUIZ.search(text):
            return Intention(TutorIntent.QUIZ, 0.9, topic)
        if _LEARN.search(text):
            return Intention(TutorIntent.LEARN, 0.8, topic)
        if _CELEBRATE.search(text):
            return Intention(TutorIntent.CELEBRATE, 0.6, topic)
        return Intention(TutorIntent.GENERAL, 0.4, topic)
