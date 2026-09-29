"""La forma no puede contradecir al fondo (ADR-004, Decisión 5).

Un turno de andamiaje que además pide brevedad e interrogatorio no es
adaptación: es ruido con dos autores. Cada test es una fila de la tabla de
precedencia; si alguien cambia el arbitraje sin cambiar la tabla, esto rompe.
"""
import pytest

from src.domain.services.adaptive_policy import (
    AdaptationParameters,
    ControlFlowParameters,
    PromptShapingParameters,
)
from src.domain.services.cognitive_style import CognitiveStyle
from src.domain.services.pedagogical_engine import PedagogicalDecision, PedagogicalMode
from src.domain.services.plan_composer import compose_plan
from src.domain.services.prerequisite_graph import GateAction
from src.domain.services.tutor_policy import TutorPolicy
from src.domain.value_objects.question import Difficulty


def decision(
    mode: PedagogicalMode = PedagogicalMode.EXPLAIN,
    *,
    style: CognitiveStyle = CognitiveStyle.SIMPLE,
    gate: GateAction = GateAction.PROCEED,
) -> PedagogicalDecision:
    return PedagogicalDecision(
        mode=mode,
        target_difficulty=Difficulty.MEDIUM,
        focus_concepts=("variable",),
        anti_spoiler=False,
        objective="objetivo",
        evidence_summary="",
        cognitive_style=style,
        gate_action=gate,
        blocked_by_prereq=gate == GateAction.SEQUENCE,
    )


def adaptacion(**kwargs) -> AdaptationParameters:
    flow_kwargs = {
        k: kwargs.pop(k) for k in ("practice_before_advance", "chunk_explanation") if k in kwargs
    }
    return AdaptationParameters(
        prompt_shaping=PromptShapingParameters(**kwargs),
        control_flow=ControlFlowParameters(**flow_kwargs),
    )


# --- Filas 1 a 3: andamiaje ---------------------------------------------------------


def test_el_andamiaje_veta_la_respuesta_breve():
    """El test que pedía el plan: SCAFFOLD no puede aceptar `short`."""
    plan = compose_plan(
        decision(PedagogicalMode.SCAFFOLD), adaptacion(explanation_length="short")
    )

    assert plan.prompt_shaping.explanation_length == "medium"
    assert any(o.parameter == "explanation_length" for o in plan.overrides)


@pytest.mark.parametrize("tasa", ["medium", "high"])
def test_el_andamiaje_baja_el_socratico(tasa):
    plan = compose_plan(
        decision(PedagogicalMode.SCAFFOLD), adaptacion(socratic_question_rate=tasa)
    )

    assert plan.prompt_shaping.socratic_question_rate == "low"


def test_el_andamiaje_garantiza_un_ejemplo():
    plan = compose_plan(
        decision(PedagogicalMode.SCAFFOLD), adaptacion(examples_per_explanation=0)
    )

    assert plan.prompt_shaping.examples_per_explanation == 1


def test_secuenciar_por_prerrequisito_cuenta_como_andamiaje():
    """`SEQUENCE` es empezar por la base: pedagógicamente es andamiaje."""
    plan = compose_plan(
        decision(PedagogicalMode.EXPLAIN, gate=GateAction.SEQUENCE),
        adaptacion(explanation_length="short", socratic_question_rate="high"),
    )

    assert plan.prompt_shaping.explanation_length == "medium"
    assert plan.prompt_shaping.socratic_question_rate == "low"


# --- Filas 4 a 6: estilo y control-flow --------------------------------------------


def test_paso_a_paso_no_admite_ve_al_grano():
    plan = compose_plan(
        decision(style=CognitiveStyle.STEP_BY_STEP), adaptacion(explanation_length="short")
    )

    assert plan.prompt_shaping.explanation_length == "medium"


def test_la_analogia_no_se_pide_dos_veces():
    plan = compose_plan(
        decision(style=CognitiveStyle.ANALOGY), adaptacion(prefers_analogy=True)
    )

    assert plan.prompt_shaping.prefers_analogy is False


def test_no_se_trocea_lo_que_ya_es_breve():
    """Se evalúa con el largo YA arbitrado, no con el que pidió la política."""
    plan = compose_plan(
        decision(PedagogicalMode.SOCRATIC),
        adaptacion(explanation_length="short", chunk_explanation=True),
    )

    assert plan.prompt_shaping.explanation_length == "short"  # socrático sí admite breve
    assert plan.control_flow.chunk_explanation is False


def test_el_andamiaje_rescata_el_troceado():
    """Si el veto sube el largo a medium, trocear vuelve a tener sentido."""
    plan = compose_plan(
        decision(PedagogicalMode.SCAFFOLD),
        adaptacion(explanation_length="short", chunk_explanation=True),
    )

    assert plan.prompt_shaping.explanation_length == "medium"
    assert plan.control_flow.chunk_explanation is True


# --- Lo que NO se toca --------------------------------------------------------------


def test_el_socratico_admite_preguntar_mucho():
    plan = compose_plan(
        decision(PedagogicalMode.SOCRATIC),
        adaptacion(socratic_question_rate="high", explanation_length="short"),
    )

    assert plan.prompt_shaping.socratic_question_rate == "high"
    assert plan.overrides == ()


def test_sin_conflicto_no_hay_vetos():
    original = adaptacion(explanation_length="long", examples_per_explanation=2)

    plan = compose_plan(decision(PedagogicalMode.EXPLAIN), original)

    assert plan.prompt_shaping == original.prompt_shaping
    assert plan.overrides == ()


def test_sin_decision_no_hay_fondo_que_proteger():
    """Chat libre: no hay pedagogía que contradecir."""
    original = adaptacion(explanation_length="short", socratic_question_rate="high")

    plan = compose_plan(None, original)

    assert plan.prompt_shaping == original.prompt_shaping
    assert plan.overrides == ()


def test_el_arbitraje_nunca_toca_la_decision_pedagogica():
    """Solo puede recortar la forma. El fondo es soberano."""
    d = decision(PedagogicalMode.SCAFFOLD)

    plan = compose_plan(d, adaptacion(explanation_length="short"))

    assert d.mode == PedagogicalMode.SCAFFOLD
    assert d.target_difficulty == Difficulty.MEDIUM
    assert d.focus_concepts == ("variable",)
    assert not hasattr(plan, "mode")


# --- El efecto de verdad: el prompt ------------------------------------------------


def test_el_prompt_de_andamiaje_deja_de_contradecirse():
    """La prueba que importa: qué llega al modelo.

    Antes salía "pista → ejemplo parcial → invitación a completar" seguido de
    "ve al grano, evita preámbulos. Guía sobre todo con preguntas".
    """
    d = decision(PedagogicalMode.SCAFFOLD)
    cruda = adaptacion(explanation_length="short", socratic_question_rate="high")

    sin_arbitraje = TutorPolicy().answer_question("ctx", "q", d, cruda.prompt_shaping).system
    con_arbitraje = (
        TutorPolicy()
        .answer_question("ctx", "q", d, compose_plan(d, cruda).prompt_shaping)
        .system
    )

    assert "ve al grano" in sin_arbitraje
    assert "Guía sobre todo con preguntas" in sin_arbitraje
    assert "ve al grano" not in con_arbitraje
    assert "Guía sobre todo con preguntas" not in con_arbitraje
    # El andamiaje sigue ahí: se recortó la forma, no el fondo.
    assert "andamiaje" in con_arbitraje


# --- El arbitraje está cableado, no es código de estantería -------------------------


@pytest.mark.asyncio
async def test_el_turno_real_llega_al_prompt_ya_arbitrado(monkeypatch):
    """Si el arbitraje no se cablea en `prepare_pedagogy`, esto se pone rojo."""
    from uuid import uuid4
    from unittest.mock import AsyncMock

    from src.application.services.analyze_document_service import AnalyzeDocumentService
    from src.domain.adaptive_signals import Signal, SignalKind
    from src.domain.aggregates.document_aggregate import DocumentAggregate
    from src.domain.aggregates.student_profile import StudentProfile
    from src.domain.value_objects.analysis_result import AnalysisResult
    from src.infrastructure.persistence.in_memory_document_repo import (
        InMemoryDocumentRepository,
    )
    from src.infrastructure.persistence.in_memory_event_bus import InMemoryEventBus
    from src.infrastructure.persistence.in_memory_student_profile_repo import (
        InMemoryStudentProfileRepository,
    )
    from src.infrastructure.persistence.in_memory_tutor_interaction_repo import (
        InMemoryTutorInteractionRepository,
    )

    estudiante = uuid4()
    docs = InMemoryDocumentRepository()
    doc = DocumentAggregate.upload(
        estudiante, "algebra.txt", content="Una variable es un valor desconocido.",
        subject="Matemática",
    )
    doc.complete_analysis(
        AnalysisResult(summary="s", key_concepts=["variable"], suggested_questions=[])
    )
    await docs.save(doc)

    # Perfil con evidencia medida (⇒ andamiaje) y señales que piden brevedad
    # y socrático alto (⇒ la política pedirá lo contrario del fondo).
    perfil = StudentProfile.create(estudiante)
    for _ in range(2):
        perfil.record_quiz_result(doc.id, 0.1, concept_results=(("variable", 0.0),))
    for kind in (SignalKind.LONG_EXPLANATION_ABANDONMENT, SignalKind.SELF_CORRECTION):
        perfil.adaptive_signals[kind.value] = Signal(kind=kind, value=0.95, samples=10)
    perfiles = InMemoryStudentProfileRepository()
    await perfiles.save(perfil)

    servicio = AnalyzeDocumentService(
        document_repository=docs,
        ia_analyst=AsyncMock(),
        event_bus=InMemoryEventBus(),
        interaction_repository=InMemoryTutorInteractionRepository(),
        profile_repository=perfiles,
    )

    plan = await servicio.prepare_pedagogy(doc.id, "no entiendo nada", estudiante)

    assert plan.decision.mode == PedagogicalMode.SCAFFOLD
    assert plan.prompt_shaping.explanation_length != "short"
    assert plan.prompt_shaping.socratic_question_rate == "low"
    assert {o.parameter for o in plan.overrides} >= {
        "explanation_length",
        "socratic_question_rate",
    }
