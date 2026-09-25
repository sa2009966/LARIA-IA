"""Arbitraje entre la decisión pedagógica y los parámetros de adaptación.

La pedagogía decide el **fondo** (qué modo, qué dificultad, qué foco) a partir
de la evidencia del estudiante sobre ese concepto. La adaptación decide la
**forma** (largo, ejemplos, cuánto preguntar) a partir de señales de
comportamiento agregadas. Cuando la forma contradice al fondo, **gana el fondo**:
ante conflicto manda lo específico.

Sin este arbitraje, `TutorPolicy` concatenaba ambas cosas y un turno de
andamiaje podía pedir a la vez "pista → ejemplo parcial → invitación a
completar" y "ve al grano, evita preámbulos. Guía sobre todo con preguntas".
Eso no es adaptación: es ruido con dos autores.

Tabla de precedencia y razones: ADR-004, Decisión 5. Este módulo es su
transcripción; si cambia una regla, cambia primero la tabla.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

from src.domain.services.adaptive_policy import (
    AdaptationParameters,
    ControlFlowParameters,
    PromptShapingParameters,
)
from src.domain.services.cognitive_style import CognitiveStyle
from src.domain.services.pedagogical_engine import PedagogicalDecision, PedagogicalMode
from src.domain.services.prerequisite_graph import GateAction


@dataclass(frozen=True)
class Override:
    """Un veto aplicado: qué parámetro, de qué a qué, y por qué.

    Se devuelve —en vez de aplicarse en silencio— porque es el insumo de la
    explicabilidad: "no acorté la explicación porque estábamos construyendo la
    base" es exactamente lo que hace legible la adaptación.
    """

    parameter: str
    from_value: str
    to_value: str
    reason: str


@dataclass(frozen=True)
class ComposedPlan:
    """Parámetros efectivos tras el arbitraje, con el rastro de lo vetado."""

    prompt_shaping: PromptShapingParameters
    control_flow: ControlFlowParameters
    overrides: tuple[Override, ...] = ()

    @property
    def adaptation(self) -> AdaptationParameters:
        """Misma forma que produce `AdaptivePolicy`, ya arbitrada."""
        return AdaptationParameters(
            prompt_shaping=self.prompt_shaping, control_flow=self.control_flow
        )


#: Razones, en el lenguaje del dominio. Se usan tal cual en la explicación.
_R_ANDAMIAJE_LARGO = "el andamiaje necesita espacio: pista, ejemplo parcial e invitación"
_R_ANDAMIAJE_SOCRATICO = "andamiar es sostener, no interrogar a quien ya está atascado"
_R_ANDAMIAJE_EJEMPLO = "el ejemplo parcial es el andamiaje: sin ejemplo no hay tal"
_R_PASO_A_PASO = "'paso a paso' y 've al grano' se contradicen"
_R_ANALOGIA_DUPLICADA = "el estilo cognitivo ya pide analogía; repetirlo no es énfasis"
_R_NADA_QUE_TROCEAR = "no se trocea una explicación que ya es breve"
_R_YA_ES_PRACTICA = "el turno ya es práctica: ofrecerla otra vez no añade nada"


def _es_andamiaje(decision: PedagogicalDecision) -> bool:
    """`SEQUENCE` es empezar por la base: pedagógicamente, andamiaje."""
    return (
        decision.mode == PedagogicalMode.SCAFFOLD
        or decision.gate_action == GateAction.SEQUENCE
    )


def compose_plan(
    decision: PedagogicalDecision | None,
    adaptation: AdaptationParameters | None,
) -> ComposedPlan:
    """Parámetros efectivos del turno. Función pura: mismos datos, mismo plan."""
    adaptation = adaptation or AdaptationParameters()
    shaping = adaptation.prompt_shaping
    flow = adaptation.control_flow
    if decision is None:
        # Sin decisión pedagógica no hay fondo que proteger (chat libre).
        return ComposedPlan(prompt_shaping=shaping, control_flow=flow)

    vetos: list[Override] = []

    if _es_andamiaje(decision):
        if shaping.explanation_length == "short":
            vetos.append(
                Override("explanation_length", "short", "medium", _R_ANDAMIAJE_LARGO)
            )
            shaping = replace(shaping, explanation_length="medium")
        if shaping.socratic_question_rate in ("medium", "high"):
            vetos.append(
                Override(
                    "socratic_question_rate",
                    shaping.socratic_question_rate,
                    "low",
                    _R_ANDAMIAJE_SOCRATICO,
                )
            )
            shaping = replace(shaping, socratic_question_rate="low")
        if shaping.examples_per_explanation <= 0:
            vetos.append(
                Override(
                    "examples_per_explanation",
                    str(shaping.examples_per_explanation),
                    "1",
                    _R_ANDAMIAJE_EJEMPLO,
                )
            )
            shaping = replace(shaping, examples_per_explanation=1)

    if (
        decision.cognitive_style == CognitiveStyle.STEP_BY_STEP
        and shaping.explanation_length == "short"
    ):
        vetos.append(Override("explanation_length", "short", "medium", _R_PASO_A_PASO))
        shaping = replace(shaping, explanation_length="medium")

    if decision.mode == PedagogicalMode.PRACTICE and shaping.practice_before_advance:
        vetos.append(
            Override("practice_before_advance", "True", "False", _R_YA_ES_PRACTICA)
        )
        shaping = replace(shaping, practice_before_advance=False)

    if decision.cognitive_style == CognitiveStyle.ANALOGY and shaping.prefers_analogy:
        vetos.append(
            Override("prefers_analogy", "True", "False", _R_ANALOGIA_DUPLICADA)
        )
        shaping = replace(shaping, prefers_analogy=False)

    # Depende del largo YA arbitrado, no del que pidió la política.
    if shaping.explanation_length == "short" and flow.chunk_explanation:
        vetos.append(
            Override("chunk_explanation", "True", "False", _R_NADA_QUE_TROCEAR)
        )
        flow = replace(flow, chunk_explanation=False)

    return ComposedPlan(
        prompt_shaping=shaping, control_flow=flow, overrides=tuple(vetos)
    )
