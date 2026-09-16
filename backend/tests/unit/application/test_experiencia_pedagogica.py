"""Invariantes de experiencia pedagógica (ADR-006, fases 1 y 2).

Estos tests existen para que no se pueda volver al comportamiento anterior:
tratar la ausencia de evidencia como ignorancia, y un chat que solo podía
empeorar el perfil del estudiante.
"""
from uuid import uuid4

import pytest

from src.application.services.learning_evidence_projector import (
    _apply_conversational_evidence,
)
from src.domain.adaptive_signals import SignalKind
from src.domain.aggregates.student_profile import StudentProfile
from src.domain.catalog.prerequisite_seeds import build_seeded_graph
from src.domain.events.domain_events import TutorQuestionAskedEvent
from src.domain.services.cognitive_style import CognitiveStyle, CognitiveStyleSelector
from src.domain.services.pedagogical_engine import (
    PedagogicalEngine,
    PedagogicalMode,
    TutorIntent,
)
from src.domain.services.prerequisite_graph import GateAction, PrerequisiteGate
from src.domain.services.tutor_policy import TutorPolicy
from src.domain.value_objects.question import Difficulty


def engine() -> PedagogicalEngine:
    return PedagogicalEngine(gate=PrerequisiteGate(build_seeded_graph()))


# --- Fase 1: el alumno nuevo no es un alumno deficiente -----------------------------


@pytest.mark.parametrize(
    "profile", [None, StudentProfile.create(uuid4())], ids=["sin_perfil", "perfil_nuevo"]
)
def test_alumno_nuevo_recibe_respuesta_a_su_pregunta(profile):
    """Antes: bloqueado, desviado a `variable`, dificultad easy."""
    decision = engine().select(
        profile, uuid4(), TutorIntent.ASK, ("matrices",), question="¿qué son las matrices?"
    )

    assert decision.blocked_by_prereq is False
    assert decision.focus_concepts[0] == "matrices"
    assert decision.target_difficulty == Difficulty.MEDIUM
    assert decision.mode == PedagogicalMode.EXPLAIN


@pytest.mark.parametrize(
    "profile", [None, StudentProfile.create(uuid4())], ids=["sin_perfil", "perfil_nuevo"]
)
def test_el_prompt_del_alumno_nuevo_no_habla_de_carencias(profile):
    decision = engine().select(
        profile, uuid4(), TutorIntent.ASK, ("matrices",), question="¿qué son las matrices?"
    )
    system = TutorPolicy().answer_question("ctx", "¿qué son las matrices?", decision).system

    assert "no domina" not in system
    assert "No expliques el tema avanzado" not in system
    assert "no de sus carencias" in system


def test_el_expediente_de_metricas_no_viaja_en_el_prompt():
    """El modelo recibe la decisión, no el historial clínico del estudiante."""
    profile = StudentProfile.create(uuid4())
    for _ in range(2):
        profile.record_concept_result("variable", 0.1)
    decision = engine().select(profile, uuid4(), TutorIntent.ASK, ("matrices",))
    system = TutorPolicy().answer_question("ctx", "q", decision).system

    assert "doc_mastery=" not in system
    assert "struggle_signals=" not in system
    assert decision.evidence_summary  # sigue disponible para logs y observabilidad


def test_alumno_medido_y_debil_si_recibe_andamiaje():
    """La fase 1 no desactiva el andamiaje: lo condiciona a haber medido."""
    doc = uuid4()
    profile = StudentProfile.create(uuid4())
    profile.record_quiz_result(doc, 0.2)

    decision = engine().select(profile, doc, TutorIntent.ASK)

    assert decision.mode == PedagogicalMode.SCAFFOLD
    assert decision.target_difficulty == Difficulty.EASY


def test_el_gate_no_desvia_el_foco_con_evidencia_fina():
    """Invariante del ADR-006: solo SEQUENCE reordena el foco.

    Ojo: el foco puede reordenarse por OTRO mecanismo (misconception medida),
    que es previo a este ADR y no se toca aquí.
    """
    profile = StudentProfile.create(uuid4())
    profile.record_concept_result("variable", 0.1)  # una sola señal: no alcanza

    decision = engine().select(profile, uuid4(), TutorIntent.ASK, ("matrices",))

    assert decision.gate_action != GateAction.SEQUENCE
    assert decision.blocked_by_prereq is False


def test_anti_spoiler_solo_en_quiz():
    doc = uuid4()
    profile = StudentProfile.create(uuid4())
    ask = engine().select(profile, doc, TutorIntent.ASK, ("matrices",))
    quiz = engine().select(profile, doc, TutorIntent.QUIZ, ("matrices",))

    assert ask.anti_spoiler is False
    assert quiz.anti_spoiler is True
    assert "Nunca reveles" not in TutorPolicy().answer_question("c", "q", ask).system


# --- Fase 2: la conversación puede subir el mastery ---------------------------------


def evento_con_autocorreccion(student_id, document_id, concepts=("variable",)):
    return TutorQuestionAskedEvent(
        aggregate_id=document_id,
        student_id=student_id,
        document_id=document_id,
        question="ah claro, ya entendí",
        answer="Bien visto.",
        signal_observations=((SignalKind.SELF_CORRECTION.value, 1.0),),
        focus_concepts=concepts,
        cognitive_style=CognitiveStyle.ANALOGY.value,
        pedagogical_mode=PedagogicalMode.EXPLAIN.value,
        answer_length=40,
    )


def test_conversar_puede_subir_el_mastery():
    """El hallazgo de fase 2: antes el chat solo podía empeorar el perfil."""
    profile = StudentProfile.create(uuid4())
    doc = uuid4()
    antes = profile.effective_concept_mastery("variable")

    for _ in range(3):
        _apply_conversational_evidence(
            profile, evento_con_autocorreccion(profile.student_id, doc)
        )

    assert profile.effective_concept_mastery("variable") > antes
    assert profile.effective_concept_mastery("variable") > 0.4


def test_la_autocorreccion_descuenta_la_racha_pero_no_la_borra():
    """Una frase no puede anular varios fallos calificados.

    Si la borrara, un "ah claro" desarmaría `SEQUENCE` y el gate oscilaría
    entre liderar con la base y abandonarla en turnos consecutivos.
    """
    profile = StudentProfile.create(uuid4())
    doc = uuid4()
    for _ in range(4):
        profile.record_concept_result("variable", 0.1)
    assert profile.mastery_by_concept["variable"].error_streak == 4

    _apply_conversational_evidence(
        profile, evento_con_autocorreccion(profile.student_id, doc)
    )

    assert profile.mastery_by_concept["variable"].error_streak == 3


def test_un_solo_mensaje_no_certifica_un_concepto():
    """Evidencia débil siempre pasa por la EWMA, incluso siendo la primera."""
    profile = StudentProfile.create(uuid4())
    doc = uuid4()

    profile.record_conversational_success(doc, ("funciones",))

    assert profile.effective_concept_mastery("funciones") < 0.45


def test_la_lucha_conversacional_repetida_alcanza_sequence():
    """SEQUENCE era inalcanzable sin quizzes: `error_streak` solo crecía ahí."""
    doc = uuid4()
    gate = PrerequisiteGate(build_seeded_graph())
    profile = StudentProfile.create(uuid4())

    for _ in range(5):
        profile.record_ask_struggle(doc, strength=0.9, concepts=("funciones",))

    assert gate.evaluate("derivadas", profile).action == GateAction.SEQUENCE


def test_sin_autocorreccion_no_hay_evidencia_positiva():
    profile = StudentProfile.create(uuid4())
    doc = uuid4()
    evento = TutorQuestionAskedEvent(
        aggregate_id=doc,
        student_id=profile.student_id,
        document_id=doc,
        question="¿qué es una variable?",
        answer="Una variable es...",
        signal_observations=((SignalKind.SELF_CORRECTION.value, 0.0),),
        focus_concepts=("variable",),
    )

    assert _apply_conversational_evidence(profile, evento) is False
    assert "variable" not in profile.mastery_by_concept


def test_el_chat_desbloquea_lo_que_el_chat_bloqueo():
    """Un hueco medido se puede cerrar conversando, sin pasar por un quiz."""
    doc = uuid4()
    gate = PrerequisiteGate(build_seeded_graph())
    profile = StudentProfile.create(uuid4())
    for _ in range(2):
        profile.record_concept_result("variable", 0.1)
    assert gate.evaluate("expresión algebraica", profile).action == GateAction.SEQUENCE

    for _ in range(6):
        _apply_conversational_evidence(
            profile, evento_con_autocorreccion(profile.student_id, doc)
        )

    assert gate.evaluate("expresión algebraica", profile).action == GateAction.PROCEED


# --- Fase 2: la memoria pedagógica significa lo que dice ---------------------------


def test_la_memoria_solo_guarda_lo_que_funciono():
    profile = StudentProfile.create(uuid4())
    doc = uuid4()

    sin_exito = TutorQuestionAskedEvent(
        aggregate_id=doc,
        student_id=profile.student_id,
        document_id=doc,
        question="no entiendo",
        answer="...",
        focus_concepts=("variable",),
        cognitive_style=CognitiveStyle.ANALOGY.value,
        pedagogical_mode=PedagogicalMode.SCAFFOLD.value,
    )
    assert _apply_conversational_evidence(profile, sin_exito) is False
    assert profile.pedagogical_memory.last_effective_strategies == []

    assert _apply_conversational_evidence(
        profile, evento_con_autocorreccion(profile.student_id, doc)
    ) is True


def test_el_estilo_cognitivo_no_esta_congelado_en_simple():
    """Un default "simple" cortocircuitaba las heurísticas para todo alumno."""
    selector = CognitiveStyleSelector()
    lento = StudentProfile.create(uuid4())
    lento.pace = "slow"
    lento.total_struggle_signals = 9
    rapido = StudentProfile.create(uuid4())
    rapido.pace = "fast"
    rapido.total_attempts = 20

    assert selector.select(lento, question="explicame") == CognitiveStyle.STEP_BY_STEP
    assert selector.select(rapido, question="explicame") == CognitiveStyle.TECHNICAL


def test_un_estilo_efectivo_se_respeta_cuando_existe():
    selector = CognitiveStyleSelector()
    profile = StudentProfile.create(uuid4())
    profile.pace = "slow"
    profile.pedagogical_memory.set_preferred_style(CognitiveStyle.ANALOGY.value)

    assert selector.select(profile, question="explicame") == CognitiveStyle.ANALOGY
