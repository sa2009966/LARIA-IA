""""Ponme un quiz de X": el cliente abre uno interactivo, el tutor no lo escribe.

Contra producción, el tutor respondía a "Ponme un quiz de fracciones" escribiendo
el quiz como texto ("1. ¿Cuál es la fracción equivalente a 1/2? a) 2/4…"): no se
corregía en el servidor, no dejaba evidencia y el estudiante lo contestaba en
texto libre. Y el detector de "quiz" era tan amplio que "ponme un ejemplo" lo
activaba: con el quiz interactivo encima, pedir un ejemplo habría abierto un
cuestionario.
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


@pytest.mark.parametrize(
    "frase, tema",
    [
        ("Ponme un quiz de fracciones", "fracciones"),
        ("hazme un examen de historia de México", "historia de México"),
        ("quiero practicar ecuaciones", "ecuaciones"),
        ("dame ejercicios de derivadas por favor", "derivadas"),
        ("evalúame en álgebra", "álgebra"),
        ("me haces unas preguntas sobre la fotosíntesis?", "fotosíntesis"),
    ],
)
def test_pedir_un_cuestionario_lo_ofrece_con_su_tema(det, frase, tema):
    r = det.detect(frase)

    assert r.intent == TutorIntent.QUIZ
    assert r.offer_quiz is True
    assert r.topic_hint == tema


@pytest.mark.parametrize(
    "frase",
    ["ponme un ejemplo", "explícame la prueba de hipótesis", "el test de Turing qué es",
     "¿cuál es la práctica más común?"],
)
def test_una_palabra_suelta_no_es_pedir_un_cuestionario(det, frase):
    """El patrón viejo saltaba con "ponme", "prueba" o "test" sueltos."""
    r = det.detect(frase)

    assert r.offer_quiz is False
    assert r.intent != TutorIntent.QUIZ


def test_sin_tema_tambien_se_ofrece(det):
    r = det.detect("ponme un quiz")

    assert r.offer_quiz is True
    assert r.topic_hint is None


def test_un_quiz_no_es_ademas_una_nivelacion(det):
    r = det.detect("quiero practicar fracciones")

    assert r.offer_quiz is True and r.suggest_placement is False


# --- El tutor no escribe el cuestionario ----------------------------------------------


def _sistema(pedido, con_material=False):
    dec = None
    if con_material:
        from src.domain.services.cognitive_style import CognitiveStyle
        from src.domain.services.pedagogical_engine import PedagogicalDecision, PedagogicalMode
        from src.domain.value_objects.question import Difficulty

        dec = PedagogicalDecision(
            mode=PedagogicalMode.EXPLAIN, target_difficulty=Difficulty.MEDIUM,
            focus_concepts=("fraccion",), anti_spoiler=False, objective="x",
            evidence_summary="", cognitive_style=CognitiveStyle.SIMPLE,
        )
    contexto = "Texto del libro." if con_material else ""
    return TutorPolicy().answer_question(contexto, "ponme un quiz", dec, quiz_request=pedido).system


@pytest.mark.parametrize("con_material", [False, True])
def test_pidiendo_cuestionario_el_tutor_no_escribe_preguntas(con_material):
    assert "No escribas preguntas, opciones ni ejercicios" in _sistema("fracciones", con_material)


def test_sin_tema_el_tutor_pregunta_de_que():
    s = _sistema("")

    assert "pregúntale sobre qué tema quiere practicar" in s


def test_sin_pedido_no_cambia_nada():
    assert "No escribas preguntas" not in _sistema(None)


@pytest.mark.asyncio
async def test_el_envelope_trae_la_senal_y_el_tutor_recibe_el_pedido():
    gate = AsyncMock()
    gate.answer_question = AsyncMock(return_value="¡Te preparo unas preguntas!")
    servicio = ChatTutorService(llm_gate=gate)

    r = await servicio.answer(None, "Ponme un quiz de fracciones", uuid4())

    assert r.envelope.payload["offer_quiz"] is True
    assert r.envelope.payload["topic_hint"] == "fracciones"
    assert gate.answer_question.await_args.kwargs["quiz_request"] == "fracciones"


@pytest.mark.asyncio
async def test_pedir_un_ejemplo_no_trae_senal_de_quiz():
    gate = AsyncMock()
    gate.answer_question = AsyncMock(return_value="Por ejemplo…")
    servicio = ChatTutorService(llm_gate=gate)

    r = await servicio.answer(None, "ponme un ejemplo", uuid4())

    assert "offer_quiz" not in r.envelope.payload
    assert gate.answer_question.await_args.kwargs["quiz_request"] is None
