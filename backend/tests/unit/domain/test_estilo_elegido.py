"""El estudiante elige cómo quiere que le expliquen, y eso gana a lo deducido (ADR-022).

Antes el estilo solo se deducía: de palabras sueltas del mensaje, de señales o de
lo que le funcionó. Nunca se preguntaba, y "ecuación" en el mensaje ya forzaba el
estilo matemático aunque el estudiante aprendiera mejor con analogías.
"""
import pytest

from src.domain.aggregates.student_profile import StudentProfile
from src.domain.services.cognitive_style import (
    CognitiveStyle as C,
    CognitiveStyleSelector,
    style_requested_in,
)
from src.domain.services.learner_context import LearnerContext
from src.domain.services.tutor_policy import TutorPolicy
from uuid import uuid4


def _perfil(eleccion: str = "") -> StudentProfile:
    p = StudentProfile.create(uuid4())
    p.choose_explanation_style(eleccion)
    return p


@pytest.mark.parametrize(
    "frase, estilo",
    [
        ("explícamelo paso a paso", C.STEP_BY_STEP),
        ("hazme un dibujo de la célula", C.VISUAL),
        ("con una analogía por favor", C.ANALOGY),
        ("demuéstralo", C.MATHEMATICAL),
        ("más técnico", C.TECHNICAL),
        ("explícamelo más sencillo", C.SIMPLE),
    ],
)
def test_un_pedido_explicito_de_forma_se_reconoce(frase, estilo):
    assert style_requested_in(frase) == estilo


@pytest.mark.parametrize("frase", ["quiero aprender ecuaciones", "qué es una fórmula química", "el esquema de Ponzi"])
def test_un_tema_no_es_un_pedido_de_forma(frase):
    assert style_requested_in(frase) is None


def test_la_eleccion_gana_a_una_palabra_del_tema():
    sel = CognitiveStyleSelector()

    assert sel.select(_perfil("analogy"), "¿cómo despejo esta ecuación?") == C.ANALOGY


def test_lo_que_pide_en_el_mensaje_gana_a_la_eleccion():
    sel = CognitiveStyleSelector()

    assert sel.select(_perfil("analogy"), "explícamelo paso a paso") == C.STEP_BY_STEP


def test_sin_eleccion_sigue_deduciendo_como_antes():
    sel = CognitiveStyleSelector()

    assert sel.select(_perfil(), "¿cómo despejo esta ecuación?") == C.MATHEMATICAL


def test_elegir_nada_borra_la_eleccion():
    p = _perfil("visual")
    p.choose_explanation_style(None)

    assert p.explanation_style_choice == ""


# --- Modo libre -----------------------------------------------------------------------


def _sistema(learner, tema=None):
    return TutorPolicy().answer_question(
        "", "quiero aprender fracciones", None, learning_topic=tema, learner=learner
    ).system


def test_ya_nivelado_empieza_la_clase_desde_su_nivel_y_no_ofrece_otra():
    s = _sistema(LearnerContext(topic_level=("Fracciones", "intermedio")), tema="fracciones")

    assert "ya hizo la nivelación de ese tema: su nivel es intermedio" in s
    assert "No empieces por la definición" in s
    assert "ofrécele una nivelación" not in s


def test_sin_nivel_en_el_tema_se_sigue_ofreciendo_la_nivelacion():
    s = _sistema(LearnerContext(levels=(("Historia", "basico"),)), tema="fracciones")

    assert "ofrécele una nivelación" in s
    assert "Historia: básico" in s


def test_el_estilo_elegido_llega_al_modo_libre():
    s = _sistema(LearnerContext(style=C.VISUAL))

    assert "Forma de explicar que prefiere el estudiante" in s


def test_sin_contexto_el_prompt_no_cambia():
    assert _sistema(None, tema="fracciones") == _sistema(LearnerContext(), tema="fracciones")
