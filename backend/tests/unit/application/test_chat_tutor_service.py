from uuid import uuid4

import pytest

from src.application.services.analyze_document_service import PedagogyPlan
from src.application.services.chat_tutor_service import ChatTutorService
from src.domain.adaptive_signals import Signal, SignalKind
from src.domain.ports.embodiment import AffectState
from src.domain.services.adaptive_policy import AdaptationParameters, AdaptivePolicy
from src.domain.services.pedagogical_engine import PedagogicalDecision, PedagogicalMode
from src.domain.value_objects.question import Difficulty


def make_decision() -> PedagogicalDecision:
    return PedagogicalDecision(
        mode=PedagogicalMode.EXPLAIN,
        target_difficulty=Difficulty.MEDIUM,
        focus_concepts=("variable",),
        anti_spoiler=True,
        objective="objetivo",
        evidence_summary="evidencia",
    )


def make_plan(document_id, student_id, question, adaptation=None) -> PedagogyPlan:
    return PedagogyPlan(
        document_id=document_id,
        student_id=student_id,
        question=question,
        context="ctx",
        decision=make_decision(),
        adaptation=adaptation or AdaptationParameters(),
    )


class FakeAnalyzeBase:
    """Doble del servicio con la colaboración nueva (plan → generar → cerrar)."""

    def __init__(self):
        self.finalized = []

    def prompt_shaping_for(self, plan):
        return plan.prompt_shaping

    async def finalize_interaction(self, plan, answer):
        self.finalized.append((plan, answer))


class TestChatTutorService:

    @pytest.mark.asyncio
    async def test_mode_libre_usa_llm_gate(self):
        captured = {}

        class FakeLlmGate:
            async def answer_question(self, context, question, decision=None, **kw):
                captured["context"] = context
                captured["question"] = question
                captured["decision"] = decision
                return "respuesta libre"

        svc = ChatTutorService(llm_gate=FakeLlmGate())
        result = await svc.answer(document_id=None, question="hola", student_id=uuid4())
        assert result.content == "respuesta libre"
        assert result.envelope.type == "answer"
        assert result.envelope.emotion in (AffectState.CALM, AffectState.ENCOURAGING)
        assert captured["question"] == "hola"
        assert captured["decision"] is None

    @pytest.mark.asyncio
    async def test_modo_documento_usa_plan_pedagogico(self):
        captured = {}

        class FakeAnalyze(FakeAnalyzeBase):
            async def prepare_pedagogy(self, document_id, question, student_id):
                captured["document_id"] = document_id
                captured["question"] = question
                captured["student_id"] = student_id
                return make_plan(document_id, student_id, question)

            async def answer_from_plan(self, plan):
                return "respuesta con doc"

        svc = ChatTutorService(analyze_service=FakeAnalyze())
        doc_id = uuid4()
        student_id = uuid4()
        result = await svc.answer(document_id=doc_id, question="q", student_id=student_id)
        assert result.content == "respuesta con doc"
        assert result.envelope.type in ("answer", "hint", "quiz", "explanation")
        assert captured["document_id"] == doc_id
        assert captured["student_id"] == student_id

    @pytest.mark.asyncio
    async def test_modo_documento_sin_analyze_raises(self):
        svc = ChatTutorService(llm_gate=object())
        with pytest.raises(ValueError, match="Servicio de análisis"):
            await svc.answer(document_id=uuid4(), question="q", student_id=uuid4())

    @pytest.mark.asyncio
    async def test_modo_libre_sin_llm_gate_raises(self):
        svc = ChatTutorService()
        with pytest.raises(ValueError, match="LLM gate"):
            await svc.answer(document_id=None, question="q", student_id=uuid4())

    @pytest.mark.asyncio
    async def test_envelope_captures_intent_learn(self):
        captured = {}

        class FakeLlmGate:
            async def answer_question(self, context, question, decision=None, **kw):
                return "explicación"

        svc = ChatTutorService(llm_gate=FakeLlmGate())
        result = await svc.answer(document_id=None, question="explica qué es un grafo", student_id=uuid4())
        assert result.envelope.payload["intent"] == "learn"
