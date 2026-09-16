"""Política adaptativa: señales de conducta → parámetros de adaptación.

Ver `docs/adr/ADR-004-adaptacion-por-senales.md` para la tabla de precedencia,
la separación observacional/política y las dos familias de parámetros.

Invariantes que el código de aquí garantiza:

1. Los conflictos entre señales se resuelven por **precedencia declarada**
   (observada > proxy), nunca por orden de evaluación de los `if`.
2. Ninguna señal derivada entra a la política junto con su componente:
   `decide()` filtra la entrada a `POLICY_SIGNALS` antes de evaluar.
3. Todo parámetro pertenece a una de las dos familias: prompt-shaping
   (texto aditivo al system prompt) o control-flow (orquestación).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from src.domain.adaptive_signals import (
    DEFAULT_CUTOFFS,
    DERIVED_FROM,
    OBSERVATIONAL_SIGNALS,
    POLICY_SIGNALS,
    AdaptationCutoffs,
    Signal,
    SignalKind,
)

__all__ = [
    "DEFAULT_ADAPTATION",
    "DEFAULT_CUTOFFS",
    "DERIVED_FROM",
    "OBSERVATIONAL_SIGNALS",
    "POLICY_SIGNALS",
    "AdaptationCutoffs",
    "AdaptationParameters",
    "AdaptivePolicy",
    "ControlFlowParameters",
    "PromptShapingParameters",
    "Signal",
    "SignalKind",
]


@dataclass(frozen=True)
class PromptShapingParameters:
    """Familia prompt-shaping: texto aditivo al system prompt.

    Se inyecta antes de abrir el stream ⇒ idéntico en streaming y no-streaming.
    """

    explanation_length: str = "medium"  # short | medium | long
    examples_per_explanation: int = 1
    socratic_question_rate: str = "low"  # low | medium | high
    prefers_analogy: bool = False

    def to_prompt_fragment(self) -> str:
        """Fragmento aditivo para el system prompt. Único punto de efecto."""
        length = {
            "short": "Responde de forma breve: ve al grano, evita preámbulos.",
            "medium": "Responde con extensión moderada.",
            "long": "Puedes desarrollar la explicación con detalle.",
        }[self.explanation_length]
        socratic = {
            "low": "Haz como mucho una pregunta de verificación al final.",
            "medium": "Intercala alguna pregunta que obligue a razonar.",
            "high": "Guía sobre todo con preguntas; deja que el estudiante concluya.",
        }[self.socratic_question_rate]
        examples = (
            "No uses ejemplos salvo que sean imprescindibles."
            if self.examples_per_explanation <= 0
            else f"Incluye {self.examples_per_explanation} ejemplo(s) concreto(s)."
        )
        analogy = (
            " Apóyate en una analogía cotidiana antes de formalizar."
            if self.prefers_analogy
            else ""
        )
        return f"Adaptación al estudiante: {length} {examples} {socratic}{analogy}"


@dataclass(frozen=True)
class ControlFlowParameters:
    """Familia control-flow: orquestación alrededor de la generación, no prompt."""

    practice_before_advance: bool = False
    chunk_explanation: bool = False


@dataclass(frozen=True)
class AdaptationParameters:
    """Parámetros de adaptación, siempre repartidos en las dos familias.

    No admite campos sueltos: un parámetro nuevo entra en una familia o no entra.
    """

    prompt_shaping: PromptShapingParameters = PromptShapingParameters()
    control_flow: ControlFlowParameters = ControlFlowParameters()


DEFAULT_ADAPTATION = AdaptationParameters()


class AdaptivePolicy:
    """Traduce señales a parámetros de adaptación de forma determinista."""

    def __init__(self, cutoffs: AdaptationCutoffs | None = None) -> None:
        self._cut = cutoffs or DEFAULT_CUTOFFS

    def decide(self, signals: Mapping[SignalKind, Signal]) -> AdaptationParameters:
        """Parámetros para este perfil de señales.

        Las señales observacionales se descartan en la entrada: no existen para
        ninguna rama de la política.
        """
        usable = {
            kind: signal
            for kind, signal in signals.items()
            if kind in POLICY_SIGNALS
            and signal.samples >= self._cut.min_samples_for_adaptation
        }
        return AdaptationParameters(
            prompt_shaping=PromptShapingParameters(
                explanation_length=self._resolve_explanation_length(usable),
                examples_per_explanation=self._resolve_examples(usable),
                socratic_question_rate=self._resolve_socratic_rate(usable),
                prefers_analogy=self._over(usable, SignalKind.ANALOGY_AFFINITY, self._cut.preference),
            ),
            control_flow=ControlFlowParameters(
                practice_before_advance=self._over(
                    usable, SignalKind.PRACTICE_SEEKING, self._cut.preference
                ),
                chunk_explanation=self._over(
                    usable, SignalKind.RESPONSE_LATENCY, self._cut.band_high
                ),
            ),
        )

    # --- Resolución con conflicto -------------------------------------------------

    def _resolve_explanation_length(self, signals: Mapping[SignalKind, Signal]) -> str:
        """Único parámetro con señales en conflicto.

        Precedencia: el abandono es conducta observada y manda sobre
        `attention_span`, que es un proxy (turnos por sesión). Un estudiante que
        abandona explicaciones largas recibe respuestas cortas aunque tenga
        muchos turnos.
        """
        if self._over(signals, SignalKind.LONG_EXPLANATION_ABANDONMENT, self._cut.abandonment):
            return "short"
        if self._over(signals, SignalKind.ATTENTION_SPAN, self._cut.attention_span):
            return "long"
        return "medium"

    # --- Resolución sin conflicto (una sola señal) --------------------------------

    def _resolve_examples(self, signals: Mapping[SignalKind, Signal]) -> int:
        band = self._band(signals, SignalKind.EXAMPLE_REQUEST_RATE)
        return {"high": 3, "medium": 2}.get(band, 1)

    def _resolve_socratic_rate(self, signals: Mapping[SignalKind, Signal]) -> str:
        band = self._band(signals, SignalKind.SELF_CORRECTION)
        return band if band in ("high", "medium") else "low"

    # --- Utilidades ---------------------------------------------------------------

    def _over(
        self, signals: Mapping[SignalKind, Signal], kind: SignalKind, cutoff: float
    ) -> bool:
        signal = signals.get(kind)
        return signal is not None and signal.value > cutoff

    def _band(self, signals: Mapping[SignalKind, Signal], kind: SignalKind) -> str:
        signal = signals.get(kind)
        if signal is None:
            return "unknown"
        if signal.value >= self._cut.band_high:
            return "high"
        if signal.value >= self._cut.band_low:
            return "medium"
        return "low"
