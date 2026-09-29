"""Sin material, el tutor usa el nivel de la nivelación y el estilo elegido (ADR-022).

El nivel se guardaba y solo lo leía el generador de quizzes: el estudiante se
nivelaba en "ecuaciones" y el chat le volvía a ofrecer nivelarse y le explicaba
desde cero.
"""
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.application.services.chat_tutor_service import ChatTutorService
from src.application.services.topic_catalog import TopicCatalog
from src.domain.aggregates.student_profile import StudentProfile
from src.domain.services.cognitive_style import CognitiveStyle
from src.infrastructure.persistence.in_memory_student_profile_repo import (
    InMemoryStudentProfileRepository,
)


async def _servicio(perfil: StudentProfile | None):
    repo = InMemoryStudentProfileRepository()
    if perfil is not None:
        await repo.save(perfil)
    gate = AsyncMock()
    gate.answer_question = AsyncMock(return_value="ok")
    return ChatTutorService(llm_gate=gate, profile_repository=repo, topic_catalog=TopicCatalog()), gate


@pytest.mark.asyncio
async def test_el_nivel_se_encuentra_por_el_tema_canonico():
    """Se guarda como "ecuaciones lineales"; el estudiante escribe "ecuaciones"."""
    uid = uuid4()
    perfil = StudentProfile.create(uid)
    clave = await TopicCatalog().canonical("ecuaciones")
    perfil.record_placement(clave, "intermedio", "Ecuaciones")
    servicio, gate = await _servicio(perfil)

    r = await servicio.answer(None, "quiero aprender ecuaciones", uid)

    learner = gate.answer_question.await_args.kwargs["learner"]
    assert learner.topic_level == ("Ecuaciones", "intermedio")
    assert "suggest_placement" not in r.envelope.payload
    assert r.envelope.payload["placement_level"] == "intermedio"


@pytest.mark.asyncio
async def test_sin_nivel_en_el_tema_se_ofrece_nivelarse_como_antes():
    uid = uuid4()
    servicio, gate = await _servicio(StudentProfile.create(uid))

    r = await servicio.answer(None, "quiero aprender fracciones", uid)

    assert gate.answer_question.await_args.kwargs["learner"] is None
    assert r.envelope.payload["suggest_placement"] is True
    assert "placement_level" not in r.envelope.payload


@pytest.mark.asyncio
async def test_el_estilo_elegido_llega_aunque_no_haya_nivelacion():
    uid = uuid4()
    perfil = StudentProfile.create(uid)
    perfil.choose_explanation_style("analogy")
    servicio, gate = await _servicio(perfil)

    await servicio.answer(None, "¿qué es la inflación?", uid)

    assert gate.answer_question.await_args.kwargs["learner"].style == CognitiveStyle.ANALOGY


@pytest.mark.asyncio
async def test_una_pregunta_suelta_recibe_los_niveles_conocidos():
    uid = uuid4()
    perfil = StudentProfile.create(uid)
    perfil.record_placement("historia", "avanzado", "Historia")
    servicio, gate = await _servicio(perfil)

    await servicio.answer(None, "¿por qué cayó Roma?", uid)

    assert gate.answer_question.await_args.kwargs["learner"].levels == (("Historia", "avanzado"),)


@pytest.mark.asyncio
async def test_el_streaming_recibe_lo_mismo():
    uid = uuid4()
    perfil = StudentProfile.create(uid)
    perfil.choose_explanation_style("visual")
    servicio, gate = await _servicio(perfil)
    recibido = {}

    async def stream(**kw):
        recibido.update(kw)
        yield "ok"

    gate.answer_question_stream = stream
    async for _ in servicio.answer_stream(None, "¿qué es un átomo?", uid):
        pass

    assert recibido["learner"].style == CognitiveStyle.VISUAL
