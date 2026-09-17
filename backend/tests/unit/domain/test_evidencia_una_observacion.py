"""Un turno es una observación, y la dificultad mira el material del turno.

Dos errores de contabilidad que se compensaban mal: el mismo turno se contaba
dos veces cuando era lento, y la velocidad corría una EWMA por concepto
etiquetado, así que dependía del largo del quiz. Más la dificultad, que sin
foco conceptual tomaba el peor documento del estudiante, sin importar de qué
material fuera el turno.
"""
from uuid import uuid4

from src.domain.aggregates.student_profile import (
    HIGH_LATENCY_THRESHOLD_MS,
    StudentProfile,
)
from src.domain.services.difficulty_calculator import DifficultyCalculator
from src.domain.value_objects.question import Difficulty


# --- Una muestra por turno --------------------------------------------------------


def test_un_turno_lento_es_un_turno_no_dos():
    doc = uuid4()
    profile = StudentProfile.create(uuid4())

    profile.record_ask_struggle(
        doc,
        strength=0.7,
        concepts=("variable",),
        latency_ms=HIGH_LATENCY_THRESHOLD_MS + 5000.0,
    )

    cm = profile.mastery_by_concept["variable"]
    assert cm.attempts == 1
    assert cm.evidence_count == 1
    # La penalización de latencia sigue ahí, aplicada a esa única muestra.
    assert cm.latency_ms_ema >= HIGH_LATENCY_THRESHOLD_MS


def test_la_latencia_alta_sigue_pesando_mas_que_un_turno_rapido():
    doc = uuid4()
    rapido = StudentProfile.create(uuid4())
    lento = StudentProfile.create(uuid4())

    rapido.record_ask_struggle(doc, strength=0.5, concepts=("variable",), latency_ms=300.0)
    lento.record_ask_struggle(
        doc, strength=0.5, concepts=("variable",), latency_ms=HIGH_LATENCY_THRESHOLD_MS + 1
    )

    assert lento.concept_mastery_for("variable") < rapido.concept_mastery_for("variable")


def test_la_senal_de_latencia_suelta_sigue_existiendo():
    """La usa el projector cuando el turno fue lento sin señal en el texto."""
    doc = uuid4()
    profile = StudentProfile.create(uuid4())

    profile.record_high_latency(doc, ("variable",), HIGH_LATENCY_THRESHOLD_MS + 1)

    assert profile.mastery_by_concept["variable"].evidence_count == 1


# --- Una observación de velocidad por evento --------------------------------------


def test_la_velocidad_no_depende_del_largo_del_quiz():
    doc = uuid4()
    corto = StudentProfile.create(uuid4())
    largo = StudentProfile.create(uuid4())

    corto.record_quiz_result(doc, 1.0, concept_results=(("variable", 1.0),))
    largo.record_quiz_result(
        doc,
        1.0,
        concept_results=tuple((f"concepto {i}", 1.0) for i in range(10)),
    )

    # Mismo resultado, mismo aprendizaje: la velocidad no puede diferir por el
    # número de ítems etiquetados. Antes la EWMA corría 10 veces en el largo.
    assert largo.learning_velocity == corto.learning_velocity


def test_un_intento_sin_conceptos_sigue_moviendo_la_velocidad():
    doc = uuid4()
    profile = StudentProfile.create(uuid4())

    profile.record_quiz_result(doc, 1.0)

    assert profile.learning_velocity > 0.0


# --- La dificultad mira el material del turno -------------------------------------


def test_un_documento_flojo_no_contamina_otro_tema():
    flojo, nuevo = uuid4(), uuid4()
    profile = StudentProfile.create(uuid4())
    for _ in range(3):
        profile.record_quiz_result(flojo, 0.1)

    calc = DifficultyCalculator()

    # El documento flojo sigue decidiendo SU propia dificultad...
    assert calc.from_profile(profile, (), document_id=flojo) == Difficulty.EASY
    # ...pero no la de un material sin evidencia: eso es no medido ⇒ MEDIUM.
    assert calc.from_profile(profile, (), document_id=nuevo) == Difficulty.MEDIUM


def test_sin_foco_y_sin_documento_no_se_castiga_la_falta_de_datos():
    profile = StudentProfile.create(uuid4())

    assert DifficultyCalculator().from_profile(profile, ()) == Difficulty.MEDIUM


def test_el_documento_dominado_sigue_dando_dificultad_alta():
    doc = uuid4()
    profile = StudentProfile.create(uuid4())
    for _ in range(3):
        profile.record_quiz_result(doc, 0.95)

    assert DifficultyCalculator().from_profile(profile, (), document_id=doc) == (
        Difficulty.HARD
    )
