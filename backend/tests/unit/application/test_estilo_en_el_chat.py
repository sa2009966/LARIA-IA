"""Preguntar y elegir cómo aprender, desde el chat (ADR-023).

Contra Render: "pregúntame cómo me gusta aprender" se detectaba como pedido de
quiz y el tutor prometió "un cuestionario para que practiques cómo te gusta
aprender". Y "me siento más cómodo con esquemas y dibujos" no se guardaba: solo
duraba lo que la conversación reciente.
"""
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.application.services.chat_tutor_service import ChatTutorService
from src.application.services.learning_preferences_service import LearningPreferencesService
from src.application.services.learning_evidence_projector import LearningEvidenceProjector
from src.domain.services.intent_detector import IntentDetector, TutorIntent
from src.domain.services.learner_context import STYLE_OPTIONS, LearnerContext, style_from_option_reply
from src.domain.services.tutor_policy import TutorPolicy
from src.infrastructure.persistence.in_memory_event_bus import InMemoryEventBus
from src.infrastructure.persistence.in_memory_student_profile_repo import (
    InMemoryStudentProfileRepository,
)

OFRECIDAS = "¿Cómo prefieres aprender? " + " ".join(f"{i}. {e}." for i, (e, _) in enumerate(STYLE_OPTIONS, 1))


@pytest.mark.parametrize(
    "frase",
    [
        "Antes de empezar la clase, pregúntame cómo me gusta aprender o cómo me siento más cómodo aprendiendo.",
        "¿cuál es mi estilo de aprendizaje?",
        "ayúdame a elegir mi forma de aprender",
    ],
)
def test_pedir_que_le_pregunten_no_es_un_quiz(frase):
    i = IntentDetector().detect(frase)

    assert i.intent == TutorIntent.LEARNING_STYLE and i.ask_learning_style
    assert not i.offer_quiz


@pytest.mark.parametrize(
    "frase, estilo",
    [
        ("Me siento más cómodo con esquemas y dibujos, y con ejemplos aplicados a mi robot.", "visual"),
        ("prefiero que me lo compares con cosas de la Tierra", "analogy"),
        ("aprendo mejor paso a paso", "step_by_step"),
        ("prefiero aprender con fórmulas", "mathematical"),
    ],
)
def test_una_declaracion_de_como_aprende_trae_el_estilo(frase, estilo):
    assert IntentDetector().detect(frase).declared_style == estilo


@pytest.mark.parametrize("frase", ["ponme un ejemplo", "me gusta la física", "pregúntame sobre fracciones"])
def test_lo_demas_no_es_hablar_de_como_aprende(frase):
    i = IntentDetector().detect(frase)

    assert i.intent != TutorIntent.LEARNING_STYLE and i.declared_style is None


@pytest.mark.parametrize(
    "respuesta, estilo",
    [("4", "visual"), ("la 2", "step_by_step"), ("opción 7", None), ("con esquemas", "visual"),
     ("que lo decidas tú", None), ("paso a paso porfa", "step_by_step")],
)
def test_respuesta_a_las_opciones(respuesta, estilo):
    assert style_from_option_reply(respuesta) == (True, estilo)


def test_el_tutor_pregunta_con_las_opciones_y_no_explica():
    s = TutorPolicy().answer_question("", "pregúntame", None, learner=LearnerContext(ask_style=True)).system

    assert "4. Con esquemas y dibujos." in s and "7. Que lo decida LARIA." in s
    assert "No expliques ningún tema" in s
    assert "ofrécele una nivelación" not in s


async def _servicio():
    repo = InMemoryStudentProfileRepository()
    bus = InMemoryEventBus()
    projector = LearningEvidenceProjector.__new__(LearningEvidenceProjector)
    projector._profile_repo = repo
    from src.domain.events.domain_events import ExplanationStyleChosenEvent

    await bus.subscribe(ExplanationStyleChosenEvent, projector.handle_style_chosen)
    gate = AsyncMock()
    gate.answer_question = AsyncMock(return_value="ok")
    servicio = ChatTutorService(
        llm_gate=gate, profile_repository=repo,
        preferences=LearningPreferencesService(event_bus=bus, profile_repository=repo),
    )
    return servicio, gate, repo


@pytest.mark.asyncio
async def test_pedirlo_llega_al_tutor_y_al_cliente():
    servicio, gate, _ = await _servicio()

    r = await servicio.answer(None, "pregúntame cómo me gusta aprender", uuid4())

    assert gate.answer_question.await_args.kwargs["learner"].ask_style
    assert r.envelope.payload["ask_learning_style"] is True
    assert "offer_quiz" not in r.envelope.payload


@pytest.mark.asyncio
async def test_declararlo_en_el_chat_lo_guarda_en_el_perfil():
    servicio, gate, repo = await _servicio()
    uid = uuid4()

    r = await servicio.answer(None, "Me siento más cómodo con esquemas y dibujos", uid)

    assert (await repo.find_by_student(uid)).explanation_style_choice == "visual"
    assert r.envelope.payload["explanation_style_chosen"] == "visual"
    learner = gate.answer_question.await_args.kwargs["learner"]
    assert learner.style_just_chosen and learner.style.value == "visual"


@pytest.mark.asyncio
async def test_contestar_con_el_numero_tras_las_opciones_lo_guarda():
    servicio, _, repo = await _servicio()
    uid = uuid4()

    r = await servicio.answer(None, "la 3", uid, history=(("user", "pregúntame"), ("assistant", OFRECIDAS)))

    assert (await repo.find_by_student(uid)).explanation_style_choice == "analogy"
    assert r.envelope.payload["explanation_style_chosen"] == "analogy"


@pytest.mark.asyncio
async def test_un_numero_sin_opciones_previas_no_elige_nada():
    servicio, _, repo = await _servicio()
    uid = uuid4()

    r = await servicio.answer(None, "3", uid, history=(("assistant", "¿Cuánto es 1 + 2?"),))

    assert "explanation_style_chosen" not in r.envelope.payload
    assert await repo.find_by_student(uid) is None


@pytest.mark.asyncio
async def test_que_decida_laria_borra_la_eleccion():
    servicio, _, repo = await _servicio()
    uid = uuid4()
    await servicio.answer(None, "aprendo mejor paso a paso", uid)

    r = await servicio.answer(None, "7", uid, history=(("assistant", OFRECIDAS),))

    assert (await repo.find_by_student(uid)).explanation_style_choice == ""
    assert r.envelope.payload["explanation_style_chosen"] is None
