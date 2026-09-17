"""Traduce los hechos de un turno en observaciones de señales (ADR-004).

El `gap_ms` **llega calculado desde el borde** (el servicio que recibe la
pregunta, con wall-clock real). Este observador no lee relojes: si lo hiciera,
duplicaría la fuente de verdad que el ADR-004 fija en `StudentProfile`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from src.domain.services.adaptive_policy import (
    DEFAULT_CUTOFFS,
    AdaptationCutoffs,
    SignalKind,
)

_CLARIFICATION = re.compile(
    r"\b(no\s+entiendo|no\s+comprendo|puedes\s+aclarar|qu[eé]\s+significa|"
    r"a\s+qu[eé]\s+te\s+refieres|no\s+me\s+queda\s+claro|otra\s+vez)\b",
    re.IGNORECASE,
)
_EXAMPLE_REQUEST = re.compile(
    r"\b(un\s+ejemplo|d[ae]me\s+un\s+ejemplo|por\s+ejemplo|ejemplific)\w*\b",
    re.IGNORECASE,
)
_PRACTICE_SEEKING = re.compile(
    r"\b(ejercicios?|practicar|pr[aá]ctica|ponme\s+un\s+problema|qu[ií]zz?|"
    r"examen\s+de\s+prueba)\b",
    re.IGNORECASE,
)
_SELF_CORRECTION = re.compile(
    r"\b(ya\s+entend[ií]|creo\s+que\s+me\s+equivoqu[eé]|entonces\s+ser[ií]a|"
    r"ah\s+claro|me\s+equivoqu[eé]|ya\s+lo\s+veo)\b",
    re.IGNORECASE,
)
_ANALOGY_AFFINITY = re.compile(
    r"\b(como\s+si\s+fuera|una\s+analog[ií]a|es\s+como|comp[aá]ralo\s+con)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class TurnFacts:
    """Hechos observables de un turno, medidos en el borde."""

    question: str
    gap_ms: float | None
    previous_answer_length: int


class AdaptiveSignalObserver:
    """Produce observaciones 0..1 por señal a partir de un turno."""

    def __init__(self, cutoffs: AdaptationCutoffs | None = None) -> None:
        self._cut = cutoffs or DEFAULT_CUTOFFS

    def observe(self, facts: TurnFacts) -> dict[SignalKind, float]:
        """Observaciones de este turno. Una señal ausente no se observa.

        Distinguir "no observado" de "observado en 0" es lo que permite que el
        gate de muestras de la política signifique algo.
        """
        text = facts.question or ""
        out: dict[SignalKind, float] = {
            SignalKind.CLARIFICATION_RATE: self._matches(_CLARIFICATION, text),
            SignalKind.EXAMPLE_REQUEST_RATE: self._matches(_EXAMPLE_REQUEST, text),
            SignalKind.PRACTICE_SEEKING: self._matches(_PRACTICE_SEEKING, text),
            SignalKind.SELF_CORRECTION: self._matches(_SELF_CORRECTION, text),
            SignalKind.ANALOGY_AFFINITY: self._matches(_ANALOGY_AFFINITY, text),
        }

        session_gap_ms = self._cut.session_gap_minutes * 60_000.0
        if facts.gap_ms is not None:
            out[SignalKind.RESPONSE_LATENCY] = min(1.0, facts.gap_ms / session_gap_ms)
            # Proxy: seguir en la misma sesión cuenta como turno sostenido.
            out[SignalKind.ATTENTION_SPAN] = 1.0 if facts.gap_ms < session_gap_ms else 0.0
            # Solo es abandono si la respuesta anterior fue efectivamente larga:
            # sin explicación larga previa no hay nada que abandonar.
            if facts.previous_answer_length >= self._cut.long_explanation_chars:
                out[SignalKind.LONG_EXPLANATION_ABANDONMENT] = (
                    1.0 if facts.gap_ms >= session_gap_ms else 0.0
                )
        return out

    def observe_confidence_expression(self, clarification_rate: float) -> float:
        """Señal derivada, **solo** para dashboard/transparencia.

        Vive fuera de `observe()` a propósito: no debe entrar al mismo flujo que
        alimenta la política, porque se derivaría de `clarification_rate` y se
        contaría la misma evidencia dos veces (ADR-004, Decisión 4).
        """
        return max(0.0, min(1.0, 1.0 - float(clarification_rate)))

    @staticmethod
    def _matches(pattern: re.Pattern[str], text: str) -> float:
        return 1.0 if pattern.search(text) else 0.0
