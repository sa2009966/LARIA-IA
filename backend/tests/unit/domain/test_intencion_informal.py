"""Entender cómo escriben de verdad los estudiantes, y preguntas sobre el tutor.

Tres fallos reproducidos contra producción:

1. Sin libro, "qn sos" recibía: "Parece que estás preguntando '¿Quién sos?' en un
   contexto informal". Comentaba cómo escribe en vez de responderle.
2. Con libro, "qn sos" recibía una clase completa sobre el material.
3. "q es una variable" no contaba como pregunta: el detector no leía "q".
"""
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.application.services.chat_tutor_service import ChatTutorService
from src.domain.services.intent_detector import IntentDetector, TutorIntent
from src.domain.services.tutor_policy import TutorPolicy


@pytest.fixture
def det():
    return IntentDetector()


# --- Preguntas sobre el tutor ---------------------------------------------------------


@pytest.mark.parametrize(
    "frase",
    ["qn sos", "quién sos?", "¿quién eres?", "hola, qn sos vos?", "q podés hacer",
     "¿qué puedes hacer?", "sos un bot?", "eres una IA?", "cómo te llamás", "¿qué es laria?"],
)
def test_preguntar_por_el_tutor_es_about(det, frase):
    assert det.detect(frase).intent == TutorIntent.ABOUT


def test_una_duda_que_empieza_igual_no_es_sobre_el_tutor(det):
    """Más de dos palabras de cola y ya es una pregunta sobre el tema."""
    assert det.detect("qué podés hacer con las ecuaciones").intent != TutorIntent.ABOUT


# --- Abreviaturas ---------------------------------------------------------------------


def test_q_es_que(det):
    """El fallo 3: sin expandir, "q es una variable" salía como conversación general."""
    assert det.detect("q es una variable").intent == TutorIntent.LEARN


def test_la_x_de_una_ecuacion_no_se_toca(det):
    """En esta plataforma "x" es casi siempre una incógnita, no "por"."""
    assert det.detect("cuánto vale x si 2x+3=7").intent != TutorIntent.ABOUT


def test_tmb_no_impide_pedir_aprender(det):
    r = det.detect("tmb quiero aprender álgebra")

    assert r.suggest_placement is True
    assert r.topic_hint == "álgebra"


# --- El prompt ------------------------------------------------------------------------


def test_sin_libro_el_tutor_sabe_quien_es():
    s = TutorPolicy().answer_question("", "qn sos", None).system

    assert "Eres LARIA" in s
    assert "el tutor con inteligencia artificial de Plenum" in s, "LARIA es el agente; Plenum, la plataforma"
    assert "eres una IA" in s, "debe decir con claridad que es una IA"


@pytest.mark.parametrize("contexto, decision", [("", None), ("Texto del libro.", "con_decision")])
def test_nunca_se_comenta_como_escribe(contexto, decision):
    """El fallo 1: señalarle su registro suena a corrección."""
    from src.domain.services.cognitive_style import CognitiveStyle
    from src.domain.services.pedagogical_engine import PedagogicalDecision, PedagogicalMode
    from src.domain.value_objects.question import Difficulty

    dec = None
    if decision:
        dec = PedagogicalDecision(
            mode=PedagogicalMode.EXPLAIN, target_difficulty=Difficulty.MEDIUM,
            focus_concepts=("variable",), anti_spoiler=False, objective="x",
            evidence_summary="", cognitive_style=CognitiveStyle.SIMPLE,
        )
    s = TutorPolicy().answer_question(contexto, "q es una variable", dec).system

    assert "nunca comentes su forma de escribir" in s


# --- Con libro, "qn sos" no es una clase ----------------------------------------------


@pytest.mark.asyncio
async def test_con_libro_una_pregunta_sobre_el_tutor_no_pasa_por_el_motor():
    """El fallo 2. Y no solo por la respuesta: pasar por el motor movía la sesión
    de tutoría y dejaba observaciones en el perfil por una pregunta que no era de
    aprendizaje."""
    motor = AsyncMock()
    gate = AsyncMock()
    gate.answer_question = AsyncMock(return_value="Soy LARIA, un tutor con IA…")
    servicio = ChatTutorService(analyze_service=motor, llm_gate=gate)

    r = await servicio.answer(uuid4(), "qn sos", uuid4())

    motor.prepare_pedagogy.assert_not_awaited()
    assert r.envelope.payload["intent"] == "about"
    assert r.envelope.payload["grounded"] is False


@pytest.mark.parametrize("frase", ["que es plenum?", "¿Qué es Plenum?", "como funciona plenum", "para que sirve plenum"])
def test_preguntar_por_la_plataforma_es_preguntar_por_el_producto(frase):
    """Contra el modelo real, "que es plenum?" caía en `learn` y el tutor le
    inventaba funciones a la plataforma ("interacción con tutores", "entorno
    colaborativo"). Como pregunta sobre el producto, responde con lo que hace."""
    assert IntentDetector().detect(frase).intent == TutorIntent.ABOUT
