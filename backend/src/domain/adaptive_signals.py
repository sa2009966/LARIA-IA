"""Primitivas de señal del motor adaptativo (ADR-004).

Módulo hoja a propósito: `StudentProfile` necesita `Signal`/`SignalKind` y no
puede depender de `domain.services`, cuyo `__init__` importa `TutorPolicy` y
cerraría un ciclo. Aquí viven los tipos; la política vive en
`domain/services/adaptive_policy.py`.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum


class SignalKind(str, Enum):
    """Señales de conducta observadas en la interacción del estudiante."""

    # Observadas: conducta directa.
    LONG_EXPLANATION_ABANDONMENT = "long_explanation_abandonment"
    CLARIFICATION_RATE = "clarification_rate"
    RESPONSE_LATENCY = "response_latency"
    EXAMPLE_REQUEST_RATE = "example_request_rate"
    PRACTICE_SEEKING = "practice_seeking"
    SELF_CORRECTION = "self_correction"
    ANALOGY_AFFINITY = "analogy_affinity"
    # Proxy: infiere un estado interno por correlación.
    ATTENTION_SPAN = "attention_span"
    # Derivada: solo observacional (dashboard), nunca política.
    CONFIDENCE_EXPRESSION = "confidence_expression"


#: Señales derivadas y el componente del que salen. Una derivada NUNCA puede
#: alimentar `AdaptivePolicy` junto con su componente (Decisión 4 del ADR-004).
DERIVED_FROM: dict[SignalKind, SignalKind] = {
    SignalKind.CONFIDENCE_EXPRESSION: SignalKind.CLARIFICATION_RATE,
}

#: Señales exclusivamente observacionales: dashboard y transparencia.
OBSERVATIONAL_SIGNALS: frozenset[SignalKind] = frozenset(DERIVED_FROM)

#: Únicas señales que pueden alimentar la política.
POLICY_SIGNALS: frozenset[SignalKind] = frozenset(SignalKind) - OBSERVATIONAL_SIGNALS


@dataclass(frozen=True)
class AdaptationCutoffs:
    """Umbrales de la política. Hipótesis nombradas, no constantes físicas.

    Se sobrescriben por entorno (`ADAPT_*`) desde la raíz de composición; el
    dominio no lee configuración.
    """

    band_low: float = 0.34
    band_high: float = 0.67
    abandonment: float = 0.55
    attention_span: float = 0.6
    preference: float = 0.4
    ewma_alpha: float = 0.3
    long_explanation_chars: int = 900
    session_gap_minutes: int = 20
    min_samples_for_adaptation: int = 5


DEFAULT_CUTOFFS = AdaptationCutoffs()


@dataclass(frozen=True)
class Signal:
    """Valor EWMA de una señal más el número de observaciones que la sostienen."""

    kind: SignalKind
    value: float = 0.0
    samples: int = 0

    def observe(self, observation: float, alpha: float) -> "Signal":
        obs = max(0.0, min(1.0, float(observation)))
        if self.samples == 0:
            value = obs
        else:
            a = max(0.01, min(1.0, float(alpha)))
            value = a * obs + (1.0 - a) * self.value
        return replace(self, value=value, samples=self.samples + 1)
