"""Lo que el envelope le dice al cliente sobre la intención (ADR-017).

El cliente ofrecía nivelación cada vez que `intent == "learn"`, y eso salta con
cualquier "qué es". Ahora el payload distingue: `suggest_placement` solo cuando
el estudiante pidió aprender un tema, y `topic_hint` trae ese tema.
"""
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.application.services.chat_tutor_service import ChatTutorService


def _servicio() -> ChatTutorService:
    gate = AsyncMock()
    gate.answer_question = AsyncMock(return_value="respuesta")
    return ChatTutorService(llm_gate=gate)


@pytest.mark.asyncio
async def test_pedir_aprender_un_tema_viaja_en_el_payload():
    r = await _servicio().answer(None, "me enseñas astronomía?", uuid4())

    payload = r.envelope.payload
    assert payload["intent"] == "learn"
    assert payload["suggest_placement"] is True
    assert payload["topic_hint"] == "astronomía"


@pytest.mark.asyncio
async def test_una_duda_no_trae_oferta():
    """Ausente, no `false`: el contrato del envelope trata la ausencia como "no aplica"."""
    r = await _servicio().answer(None, "¿qué es una variable?", uuid4())

    assert r.envelope.payload["intent"] == "learn"
    assert "suggest_placement" not in r.envelope.payload


@pytest.mark.asyncio
async def test_el_streaming_trae_lo_mismo():
    """Los dos caminos arman el payload con el mismo helper y no pueden divergir."""
    servicio = _servicio()
    gate = servicio._llm_gate

    async def _tokens(*_a, **_k):
        yield "res"
        yield "puesta"

    gate.answer_question_stream = _tokens
    # El stream emite (token, None) y cierra con (contenido, envelope).
    envelope = None
    async for _texto, env in servicio.answer_stream(None, "quiero aprender historia", uuid4()):
        if env is not None:
            envelope = env
    assert envelope is not None, "el stream no emitió envelope"
    assert envelope.payload["suggest_placement"] is True
    assert envelope.payload["topic_hint"] == "historia"
