"""LARIA habla de sí misma con el género de la voz que se oye (ADR-030).

Con una voz masculina, la vista previa decía "soy tu tutora", y el chat y la
clase también hablaban en femenino.
"""
from uuid import uuid4
from unittest.mock import AsyncMock

import pytest

from src.application.services.chat_tutor_service import ChatTutorService
from src.domain.aggregates.learning_path import LessonVariant
from src.domain.aggregates.student_profile import StudentProfile
from src.domain.catalog.voices import SAMPLE_TEXTS, VOICES, persona_for
from src.domain.ports.lesson_generator import LessonRequest
from src.domain.services.learner_context import LearnerContext
from src.domain.services.tutor_policy import TutorPolicy
from src.domain.value_objects.question import Difficulty
from src.infrastructure.embodiment.openai_tts import OpenAITextToSpeech
from src.domain.ports.embodiment import AffectState
from src.infrastructure.persistence.in_memory_student_profile_repo import InMemoryStudentProfileRepository


def test_cada_voz_tiene_su_persona_y_sin_eleccion_manda_la_de_por_defecto():
    for v in VOICES:
        assert persona_for(v.id) == v.gender
    assert persona_for(None) == "femenina"  # coral, la de por defecto


def test_las_frases_de_muestra_concuerdan():
    assert "tu tutor de" in SAMPLE_TEXTS["masculina"] and "tutora" not in SAMPLE_TEXTS["masculina"]
    assert "tu tutora de" in SAMPLE_TEXTS["femenina"]


@pytest.mark.parametrize("persona, sale, no_sale", [("masculina", "soy tu tutor", "tutora"), ("femenina", "soy tu tutora", "encantado")])
def test_el_chat_libre_habla_con_ese_genero(persona, sale, no_sale):
    s = TutorPolicy().answer_question("", "hola", None, learner=LearnerContext(persona=persona)).system

    assert sale in s and no_sale not in s


def test_la_clase_tambien():
    req = LessonRequest(topic_label="Fracciones", concept="fraccion", concept_title="Fracciones",
                        variant=LessonVariant.INTRODUCE, check_difficulties=(Difficulty.EASY,), persona="masculina")

    assert "soy tu tutor" in TutorPolicy().teaching_lesson(req).system


def test_las_instrucciones_de_la_voz_concuerdan_con_la_voz():
    tts = OpenAITextToSpeech("k", "gpt-4o-mini-tts", "coral")

    assert "el tutor" in tts._payload("x", AffectState.CALM, "cedar")["instructions"]
    assert "la tutora" in tts._payload("x", AffectState.CALM, "nova")["instructions"]


@pytest.mark.asyncio
async def test_el_chat_toma_el_genero_de_la_voz_elegida():
    repo = InMemoryStudentProfileRepository()
    uid = uuid4()
    perfil = StudentProfile.create(uid)
    perfil.choose_voice("onyx")
    await repo.save(perfil)
    gate = AsyncMock()
    gate.answer_question = AsyncMock(return_value="ok")

    await ChatTutorService(llm_gate=gate, profile_repository=repo).answer(None, "hola", uid)

    assert gate.answer_question.await_args.kwargs["learner"].persona == "masculina"
