"""La evidencia se pesa por su calidad (ADR-007).

Estos tests existen para que no se pueda volver al comportamiento anterior:
que preguntar contara como fallar. Tres errores compartían esa raíz —
auto-reporte tratado como medición, ascendido a diagnóstico, y un diagnóstico
apagando el gate — y los tres se blindan aquí.
"""
from uuid import uuid4

from src.domain.aggregates.student_profile import (
    EvidenceKind,
    EvidenceSample,
    StudentProfile,
)
from src.domain.catalog.prerequisite_seeds import build_seeded_graph
from src.domain.services.cognitive_style import CognitiveStyle
from src.domain.services.learning_signal_detector import LearningSignalDetector
from src.domain.services.pedagogical_engine import (
    PedagogicalEngine,
    PedagogicalMode,
    TutorIntent,
)
from src.domain.services.prerequisite_graph import GateAction, PrerequisiteGate
from src.domain.value_objects.question import Difficulty


def engine() -> PedagogicalEngine:
    return PedagogicalEngine(gate=PrerequisiteGate(build_seeded_graph()))


def perfil_que_pregunta(veces: int, concepto: str = "ecuación") -> StudentProfile:
    """Perfil con `veces` auto-reportes de confusión, como los aplica el servicio."""
    doc = uuid4()
    profile = StudentProfile.create(uuid4())
    for _ in range(veces):
        profile.record_ask_struggle(doc, strength=0.9, concepts=(concepto,))
    return profile


# --- El peso de cada clase de evidencia --------------------------------------------


def test_un_item_calificado_pesa_el_doble_que_un_auto_reporte():
    profile = perfil_que_pregunta(1, "variable")
    debil = profile.mastery_by_concept["variable"]
    assert (debil.weak_evidence_count, debil.measured_evidence_count) == (1, 0)
    assert debil.weighted_evidence == 0.5
    assert debil.informs_decision is False

    profile.record_concept_result("variable", 0.0)
    medido = profile.mastery_by_concept["variable"]
    assert (medido.weak_evidence_count, medido.measured_evidence_count) == (1, 1)
    assert medido.weighted_evidence == 1.5
    assert medido.informs_decision is True


def test_la_autocorreccion_del_chat_tambien_es_evidencia_debil():
    """Fase 2 del ADR-006: sube el mastery, pero sin autoridad de medición."""
    profile = StudentProfile.create(uuid4())
    profile.record_conversational_success(uuid4(), ("funciones",))

    cm = profile.mastery_by_concept["funciones"]
    assert cm.measured_evidence_count == 0
    assert profile.has_decision_evidence("funciones") is False


# --- E2: preguntar no baja el nivel del turno --------------------------------------


def test_decir_que_eres_novato_no_convierte_el_turno_en_andamiaje():
    """El alumno que avisa que no sabe recibe el MISMO nivel, no menos.

    Reproduce el turno real: el servicio aplica la señal al perfil en memoria
    antes de decidir, así que el auto-reporte de ESTA pregunta llegaba a la
    decisión de ESTA pregunta y la hundía a scaffold/easy.
    """
    doc = uuid4()
    pregunta = "no sé nada de ecuaciones, ¿qué son las matrices?"
    signal = LearningSignalDetector().detect(pregunta)

    neutral = engine().select(
        StudentProfile.create(uuid4()), doc, TutorIntent.ASK, ("matrices",),
        question="¿qué son las matrices?",
    )
    autoreporte = StudentProfile.create(uuid4())
    autoreporte.record_ask_struggle(
        doc, strength=signal.strength, concepts=signal.concepts_hint
    )
    declarado = engine().select(
        autoreporte, doc, TutorIntent.ASK, ("matrices",), question=pregunta
    )

    assert (declarado.mode, declarado.target_difficulty) == (
        neutral.mode,
        neutral.target_difficulty,
    )
    assert declarado.mode == PedagogicalMode.EXPLAIN
    assert declarado.target_difficulty == Difficulty.MEDIUM


def test_el_auto_reporte_si_cambia_el_registro():
    """Lo que el auto-reporte mueve es el estilo, no el nivel."""
    doc = uuid4()
    decision = engine().select(
        StudentProfile.create(uuid4()),
        doc,
        TutorIntent.ASK,
        ("matrices",),
        question="no entiendo, explicamelo paso a paso",
    )

    assert decision.cognitive_style == CognitiveStyle.STEP_BY_STEP
    assert decision.target_difficulty == Difficulty.MEDIUM
    assert decision.mode == PedagogicalMode.EXPLAIN


def test_una_senal_de_struggle_no_vuelve_medido_el_documento():
    """`struggle_signals` es auto-reporte: bastaba uno para la rama de déficit."""
    doc = uuid4()
    profile = perfil_que_pregunta(1, "variable")
    doc_id = next(iter(profile.mastery_by_document))
    assert profile.mastery_by_document[doc_id].struggle_signals == 1

    decision = engine().select(profile, doc_id, TutorIntent.ASK, ("matrices",))

    assert decision.mode == PedagogicalMode.EXPLAIN
    assert decision.target_difficulty == Difficulty.MEDIUM


# --- E2 en el gate: dos preguntas no son un hueco medido ---------------------------


def test_dos_preguntas_no_alcanzan_para_liderar_con_la_base():
    gate = PrerequisiteGate(build_seeded_graph())
    profile = perfil_que_pregunta(2, "funciones")

    result = gate.evaluate("derivadas", profile)

    assert result.action == GateAction.INTEGRATE
    assert result.blocked is False


def test_la_lucha_repetida_si_alcanza(  ):
    """El ADR-006 quiso que conversar pudiera llegar a SEQUENCE: sigue pudiendo."""
    gate = PrerequisiteGate(build_seeded_graph())

    assert gate.evaluate("derivadas", perfil_que_pregunta(4, "funciones")).action == (
        GateAction.SEQUENCE
    )


def test_un_fallo_calificado_repetido_sigue_bastando():
    """La evidencia medida no perdió fuerza: dos ítems fallados siguen siendo hueco."""
    gate = PrerequisiteGate(build_seeded_graph())
    profile = StudentProfile.create(uuid4())
    for _ in range(2):
        profile.record_concept_result("variable", 0.1)

    assert gate.evaluate("matrices", profile).action == GateAction.SEQUENCE


# --- E3: un concepto que cuesta no es un malentendido concreto ---------------------


def test_preguntar_no_inventa_un_diagnostico():
    profile = perfil_que_pregunta(3, "ecuación")

    assert profile.pedagogical_memory.frequent_misconceptions == []
    assert profile.frequent_errors == []

    decision = engine().select(
        profile,
        next(iter(profile.mastery_by_document)),
        TutorIntent.ASK,
        ("matrices",),
        question="¿qué son las matrices?",
    )
    assert "misconception" not in decision.objective
    assert "mapped_misconception" not in decision.evidence_summary


def test_un_fallo_calificado_si_alimenta_la_memoria():
    """El canal legítimo sigue abierto: lo que se falla medido sí se recuerda."""
    profile = StudentProfile.create(uuid4())
    profile.record_concept_evidence(
        "variable",
        EvidenceSample(kind=EvidenceKind.QUIZ_ITEM, score_ratio=0.0),
    )

    assert "variable" in profile.frequent_errors
    assert "variable" in profile.pedagogical_memory.frequent_misconceptions


# --- E4: un malentendido en memoria no puede apagar el gate -----------------------


def test_una_misconception_en_memoria_no_apaga_el_gate():
    """El gate evalúa un concepto del currículo, no una etiqueta de diagnóstico.

    Antes se evaluaba `focus[0]`, que con un malentendido mapeado es un id del
    catálogo: sin prerrequisitos en el grafo ⇒ PROCEED siempre. El gate quedaba
    apagado justo para quien más evidencia de hueco tenía.
    """
    doc = uuid4()
    profile = StudentProfile.create(uuid4())
    profile.pedagogical_memory.remember_misconception("el igual es hacer la operacion")
    for _ in range(2):
        profile.record_concept_result("variable", 0.1)

    decision = engine().select(profile, doc, TutorIntent.ASK, ("ecuación",))

    assert decision.gate_action == GateAction.SEQUENCE
    assert decision.remediation_concepts == ("variable",)
    assert "variable" in decision.focus_concepts
