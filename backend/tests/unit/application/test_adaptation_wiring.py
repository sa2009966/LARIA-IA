"""Cierre de los puntos 2 y 3 del ADR-004, verificado extremo a extremo.

- Punto 3: streaming y no-streaming producen la MISMA adaptación prompt-shaping
  ante el mismo perfil. Es la definición de "cerrado" del split-brain.
- Punto 2: el gap se mide en el borde y el estado de interacción se persiste
  una sola vez, por el projector.
"""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.application.services.analyze_document_service import AnalyzeDocumentService
from src.application.services.chat_tutor_service import ChatTutorService
from src.application.services.learning_evidence_projector import (
    _apply_interaction_state,
)
from src.application.services.llm_gate import LlmGate
from src.domain.adaptive_signals import DEFAULT_CUTOFFS, SignalKind
from src.domain.aggregates.document_aggregate import DocumentAggregate
from src.domain.aggregates.student_profile import StudentProfile
from src.domain.events.domain_events import TutorQuestionAskedEvent
from src.domain.services.tutor_policy import TutorPolicy
from src.infrastructure.persistence.in_memory_document_repo import (
    InMemoryDocumentRepository,
)
from src.infrastructure.persistence.in_memory_student_profile_repo import (
    InMemoryStudentProfileRepository,
)
from src.infrastructure.persistence.in_memory_tutor_interaction_repo import (
    InMemoryTutorInteractionRepository,
)


class RecordingAnalyst:
    """Analista falso que construye el prompt real y lo registra."""

    def __init__(self) -> None:
        self.system_prompts: list[str] = []
        self.user_prompts: list[str] = []
        self._policy = TutorPolicy()

    def _record(self, context, question, decision, adaptation) -> str:
        prompt = self._policy.answer_question(context, question, decision, adaptation)
        self.system_prompts.append(prompt.system)
        self.user_prompts.append(prompt.user)
        return "Respuesta del tutor."

    async def analyze(self, document):  # pragma: no cover - no usado aquí
        raise NotImplementedError

    async def generate_quiz(self, *a, **kw):  # pragma: no cover - no usado aquí
        raise NotImplementedError

    async def answer_question(self, context, question, decision=None, adaptation=None):
        return self._record(context, question, decision, adaptation)

    async def answer_question_with_model(
        self, context, question, decision=None, *, model, adaptation=None
    ):
        return self._record(context, question, decision, adaptation)

    async def answer_question_stream(
        self, context, question, decision=None, model=None, adaptation=None
    ):
        text = self._record(context, question, decision, adaptation)
        for chunk in (text[:8], text[8:]):
            yield chunk


def _profile_que_abandona_explicaciones_largas(student_id) -> StudentProfile:
    """Perfil con abandono alto y atención alta: el caso del conflicto."""
    profile = StudentProfile.create(student_id)
    for _ in range(DEFAULT_CUTOFFS.min_samples_for_adaptation):
        profile.observe_signal(SignalKind.LONG_EXPLANATION_ABANDONMENT, 1.0)
        profile.observe_signal(SignalKind.ATTENTION_SPAN, 1.0)
    return profile


async def _build(adaptation_enabled: bool = True):
    student_id = uuid4()
    doc_repo = InMemoryDocumentRepository()
    document = DocumentAggregate.upload(
        student_id, "alg.txt", "Una variable representa un valor.", "Matemática"
    )
    await doc_repo.save(document)

    profile_repo = InMemoryStudentProfileRepository()
    await profile_repo.save(_profile_que_abandona_explicaciones_largas(student_id))

    analyst = RecordingAnalyst()
    service = AnalyzeDocumentService(
        document_repository=doc_repo,
        ia_analyst=analyst,
        interaction_repository=InMemoryTutorInteractionRepository(),
        profile_repository=profile_repo,
        llm_gate=LlmGate(ia_analyst=analyst, cache=None),
        adaptation_enabled=adaptation_enabled,
    )
    tutor = ChatTutorService(
        analyze_service=service,
        llm_gate=service._llm_gate,
        profile_repository=profile_repo,
    )
    return tutor, analyst, document, student_id, profile_repo


@pytest.mark.asyncio
async def test_streaming_y_no_streaming_producen_la_misma_adaptacion():
    """Definición de 'cerrado' del Punto 3: ninguna divergencia entre paths."""
    tutor, analyst, document, student_id, _ = await _build()

    await tutor.answer(document.id, "¿Qué es una variable?", student_id)
    async for _ in tutor.answer_stream(document.id, "¿Qué es una variable?", student_id):
        pass

    assert len(analyst.system_prompts) == 2
    assert analyst.system_prompts[0] == analyst.system_prompts[1]


@pytest.mark.asyncio
async def test_ambos_paths_aplican_la_precedencia_del_punto_1():
    """La adaptación que llega al prompt es 'short', no 'long'."""
    tutor, analyst, document, student_id, _ = await _build()

    await tutor.answer(document.id, "¿Qué es una variable?", student_id)
    async for _ in tutor.answer_stream(document.id, "¿Qué es una variable?", student_id):
        pass

    for prompt in analyst.system_prompts:
        assert "Responde de forma breve" in prompt
        assert "Puedes desarrollar la explicación con detalle" not in prompt


@pytest.mark.asyncio
async def test_streaming_con_documento_usa_decision_pedagogica():
    """Antes el streaming ignoraba la decisión: contexto vacío y decision=None."""
    tutor, analyst, document, student_id, _ = await _build()

    envelope = None
    async for _, env in tutor.answer_stream(document.id, "¿Qué es una variable?", student_id):
        if env is not None:
            envelope = env

    assert envelope is not None
    assert envelope.payload["mode"]
    assert "chunk_explanation" in envelope.payload
    # Antes el streaming mandaba context="" y decision=None al LLM.
    assert "tutor adaptativo de LARIA" in analyst.system_prompts[0]
    assert "Una variable representa un valor." in analyst.user_prompts[0]


@pytest.mark.asyncio
async def test_modo_sombra_no_inyecta_el_fragmento():
    tutor, analyst, document, student_id, _ = await _build(adaptation_enabled=False)

    await tutor.answer(document.id, "¿Qué es una variable?", student_id)

    assert "Adaptación al estudiante" not in analyst.system_prompts[0]


@pytest.mark.asyncio
async def test_las_observaciones_viajan_en_el_evento():
    """El borde mide; el evento transporta; el projector escribe."""
    tutor, _, document, student_id, profile_repo = await _build()
    service = tutor._analyze_service

    plan = await service.prepare_pedagogy(
        document.id, "dame un ejemplo por favor", student_id
    )
    assert SignalKind.EXAMPLE_REQUEST_RATE in plan.observations


def test_gap_se_mide_contra_el_perfil():
    profile = StudentProfile.create(uuid4())
    assert profile.interaction_gap_ms() is None

    ahora = datetime.now(timezone.utc)
    profile.record_interaction(answer_length=1200, at=ahora - timedelta(minutes=30))

    gap = profile.interaction_gap_ms(ahora)
    assert gap == pytest.approx(30 * 60 * 1000, rel=1e-3)
    assert profile.last_answer_length == 1200


def test_projector_escribe_el_estado_de_interaccion():
    profile = StudentProfile.create(uuid4())
    event = TutorQuestionAskedEvent(
        aggregate_id=uuid4(),
        student_id=profile.student_id,
        document_id=uuid4(),
        question="q",
        answer="a",
        signal_observations=((SignalKind.CLARIFICATION_RATE.value, 1.0),),
        answer_length=950,
    )

    _apply_interaction_state(profile, event)

    assert profile.last_answer_length == 950
    assert profile.last_interaction_at is not None
    assert profile.adaptive_signals[SignalKind.CLARIFICATION_RATE.value].samples == 1


@pytest.mark.asyncio
async def test_estado_de_interaccion_sobrevive_al_repositorio():
    repo = InMemoryStudentProfileRepository()
    profile = StudentProfile.create(uuid4())
    profile.observe_signal(SignalKind.CLARIFICATION_RATE, 0.8)
    profile.record_interaction(answer_length=777)
    await repo.save(profile)

    recuperado = await repo.find_by_student(profile.student_id)
    assert recuperado.last_answer_length == 777
    assert recuperado.last_interaction_at == profile.last_interaction_at
    assert recuperado.adaptive_signals[SignalKind.CLARIFICATION_RATE.value].value == 0.8
