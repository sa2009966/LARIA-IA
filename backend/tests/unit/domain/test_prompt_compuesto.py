"""El prompt que de verdad se le manda al modelo (fase D).

Criterio de cierre de la fase: hasta ahora **ningún test miraba el prompt
compuesto**. Se probaba la política —qué parámetros salen de qué señales— y se
daba por hecho que llegaban al modelo. El criterio viejo ("los tests pasan con
`ADAPT_SHADOW_MODE=False`") ya se cumplía sin haber tocado nada, porque nada
cubría esta capa.

Aquí se afirma sobre la cadena que viaja a OpenAI.
"""
from uuid import uuid4

import pytest

from src.domain.aggregates.student_profile import StudentProfile
from src.domain.services.adaptive_policy import (
    AdaptivePolicy,
    PromptShapingParameters,
)
from src.domain.adaptive_signals import Signal, SignalKind
from src.domain.services.cognitive_style import CognitiveStyle
from src.domain.services.pedagogical_engine import (
    PedagogicalDecision,
    PedagogicalMode,
)
from src.domain.services.plan_composer import compose_plan
from src.domain.services.tutor_policy import TutorPolicy
from src.domain.value_objects.question import Difficulty


def decision(
    mode: PedagogicalMode = PedagogicalMode.EXPLAIN,
    estilo: CognitiveStyle = CognitiveStyle.SIMPLE,
) -> PedagogicalDecision:
    return PedagogicalDecision(
        mode=mode,
        target_difficulty=Difficulty.MEDIUM,
        focus_concepts=("ecuacion",),
        anti_spoiler=False,
        objective="Explicar el concepto.",
        evidence_summary="",
        cognitive_style=estilo,
    )


def sistema(dec, shaping: PromptShapingParameters | None) -> str:
    return TutorPolicy().answer_question("ctx", "¿qué es una ecuación?", dec, shaping).system


def perfil_con(**senales: float) -> StudentProfile:
    profile = StudentProfile.create(uuid4())
    for nombre, valor in senales.items():
        kind = SignalKind(nombre)
        profile.adaptive_signals[kind.value] = Signal(kind=kind, value=valor, samples=10)
    return profile


# --- El interruptor ------------------------------------------------------------------


def test_con_la_adaptacion_encendida_el_fragmento_llega_al_modelo():
    prompt = sistema(decision(), PromptShapingParameters(explanation_length="short"))

    assert "Adaptación al estudiante" in prompt
    assert "ve al grano" in prompt


def test_en_modo_sombra_el_prompt_queda_intacto():
    """`None` es lo que `prompt_shaping_for()` devuelve en modo sombra.

    Es el interruptor de emergencia: si la adaptación sale mal en producción se
    apaga por variable de entorno, sin desplegar. Este test falla si alguien la
    cablea de forma que ya no se pueda apagar.
    """
    prompt = sistema(decision(), None)

    assert "Adaptación al estudiante" not in prompt
    assert "ve al grano" not in prompt


# --- El prompt no se contradice consigo mismo ------------------------------------------


def test_un_turno_de_andamiaje_no_pide_a_la_vez_ir_al_grano():
    """El bug que motivó el arbitraje, comprobado sobre el prompt final.

    Con señales reales, un turno SCAFFOLD generaba "usa andamiaje gradual",
    "ve al grano" y "guía sobre todo con preguntas" en la misma cadena.
    """
    dec = decision(mode=PedagogicalMode.SCAFFOLD)
    propuesta = AdaptivePolicy().decide(
        perfil_con(long_explanation_abandonment=0.9, self_correction=0.9).signals_for_policy()
    )
    plan = compose_plan(dec, propuesta)

    prompt = sistema(dec, plan.prompt_shaping)

    assert "andamiaje" in prompt
    assert "ve al grano" not in prompt
    assert "Guía sobre todo con preguntas" not in prompt


def test_paso_a_paso_y_brevedad_no_conviven_en_el_prompt():
    dec = decision(estilo=CognitiveStyle.STEP_BY_STEP)
    propuesta = AdaptivePolicy().decide(
        perfil_con(long_explanation_abandonment=0.9).signals_for_policy()
    )
    plan = compose_plan(dec, propuesta)

    prompt = sistema(dec, plan.prompt_shaping)

    assert "ve al grano" not in prompt


# --- Ofrecer práctica (ADR-015) --------------------------------------------------------


def test_quien_pide_ejercicios_recibe_la_oferta_en_el_prompt():
    propuesta = AdaptivePolicy().decide(perfil_con(practice_seeking=0.9).signals_for_policy())
    plan = compose_plan(decision(), propuesta)

    prompt = sistema(decision(), plan.prompt_shaping)

    assert "ofreciendo un ejercicio breve" in prompt


def test_un_turno_que_ya_es_practica_no_ofrece_practica_otra_vez():
    dec = decision(mode=PedagogicalMode.PRACTICE)
    propuesta = AdaptivePolicy().decide(perfil_con(practice_seeking=0.9).signals_for_policy())
    plan = compose_plan(dec, propuesta)

    prompt = sistema(dec, plan.prompt_shaping)

    assert "ofreciendo un ejercicio breve" not in prompt
    assert any(o.parameter == "practice_before_advance" for o in plan.overrides)


def test_ofrecer_no_es_bloquear():
    """El ADR-006 decidió que el sistema ofrece; el prompt debe ofrecer.

    Si esta palabra se convierte en "exige" o "no avances hasta", la adaptación
    habría empezado a bloquear por la puerta de atrás.
    """
    prompt = sistema(decision(), PromptShapingParameters(practice_before_advance=True))

    assert "ofreciendo" in prompt
    assert "no avances" not in prompt.lower()


# --- Streaming y no-streaming no pueden divergir ---------------------------------------


@pytest.mark.asyncio
async def test_el_mismo_plan_alimenta_streaming_y_no_streaming():
    """Ambos caminos pasan por `prompt_shaping_for`, que es el único punto."""
    from unittest.mock import AsyncMock
    from src.application.services.analyze_document_service import AnalyzeDocumentService

    servicio = AnalyzeDocumentService(
        document_repository=AsyncMock(),
        ia_analyst=AsyncMock(),
        adaptation_enabled=True,
    )
    plan = type("P", (), {"prompt_shaping": PromptShapingParameters(explanation_length="short")})()

    assert servicio.prompt_shaping_for(plan) is plan.prompt_shaping

    en_sombra = AnalyzeDocumentService(
        document_repository=AsyncMock(),
        ia_analyst=AsyncMock(),
        adaptation_enabled=False,
    )
    assert en_sombra.prompt_shaping_for(plan) is None
