""""Quiero aprender X" sin material: orientar y ofrecer nivelación (ADR-017).

En una prueba real contra producción, el tutor respondía a "quiero aprender
programación" con "te recomiendo tutoriales en línea o cursos gratuitos": mandaba
al estudiante fuera del producto justo cuando decía que quería aprender.
"""
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.application.services.chat_tutor_service import ChatTutorService
from src.application.services.llm_gate import LlmGate
from src.domain.services.tutor_policy import TutorPolicy


def sistema(pregunta: str, tema: str | None = None, contexto: str = "") -> str:
    return TutorPolicy().answer_question(contexto, pregunta, None, learning_topic=tema).system


# --- El prompt -----------------------------------------------------------------------


def test_con_tema_se_orienta_y_se_ofrece_nivelacion():
    s = sistema("quiero aprender astronomía", "astronomía")

    assert "«astronomía»" in s
    assert "nivelación" in s
    assert "no le recomiendes cursos, tutoriales" in s


def test_las_preguntas_de_la_nivelacion_no_las_hace_el_modelo():
    """Si las hiciera el modelo en el chat, no se calificarían en el servidor, no
    dejarían evidencia, y el estudiante acabaría contestándolas dos veces."""
    assert "No hagas tú esas preguntas" in sistema("quiero aprender historia", "historia")


def test_sin_tema_no_cambia_nada():
    """Una pregunta normal sin material no recibe la oferta."""
    s = sistema("¿qué es una variable?")

    assert "nivelación" not in s
    assert "no le recomiendes" not in s


def test_sin_material_no_se_pide_basarse_en_un_contexto_vacio():
    """Era una instrucción imposible: el modelo respondía lo que se le ocurría."""
    assert "únicamente en el contexto" not in sistema("hola")
    assert "No hay material vinculado" in sistema("hola")


def test_con_material_si_se_pide_basarse_en_el():
    assert "únicamente en el contexto" in sistema("¿y esto?", contexto="Texto del libro.")


# --- El caché ------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_el_tema_forma_parte_de_la_clave_de_cache():
    """Sin esto, "quiero aprender X" se serviría desde la respuesta cacheada que
    recomendaba tutoriales, y el cambio no llegaría nunca al estudiante."""
    cache = AsyncMock()
    cache.get = AsyncMock(return_value=None)
    ia = AsyncMock()
    ia.answer_question_with_model = AsyncMock(return_value="ok")
    gate = LlmGate(ia, cache=cache)

    await gate.answer_question("", "quiero aprender historia", None)
    await gate.answer_question("", "quiero aprender historia", None, learning_topic="historia")

    claves = [llamada.args[0] for llamada in cache.set.await_args_list]
    assert len(set(claves)) == 2


# --- El servicio decide cuándo hay tema -----------------------------------------------


def _servicio() -> tuple[ChatTutorService, AsyncMock]:
    gate = AsyncMock()
    gate.answer_question = AsyncMock(return_value="respuesta")
    return ChatTutorService(llm_gate=gate), gate


@pytest.mark.asyncio
async def test_pedir_aprender_un_tema_llega_al_prompt():
    servicio, gate = _servicio()

    await servicio.answer(None, "quiero aprender electrónica", uuid4())

    assert gate.answer_question.await_args.kwargs["learning_topic"] == "electrónica"


@pytest.mark.asyncio
async def test_una_duda_no_lleva_oferta_al_prompt():
    """Misma condición que `suggest_placement`: el texto del tutor y el botón del
    cliente no pueden decir cosas distintas."""
    servicio, gate = _servicio()

    await servicio.answer(None, "¿qué es una variable?", uuid4())

    assert gate.answer_question.await_args.kwargs["learning_topic"] is None
