from uuid import uuid4

import pytest

from src.application.services.chat_tutor_service import ChatTutorService


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
        answer = await svc.answer(document_id=None, question="hola", student_id=uuid4())
        assert answer == "respuesta libre"
        assert captured["question"] == "hola"
        assert captured["decision"] is None

    @pytest.mark.asyncio
    async def test_modo_documento_usa_analyze_service(self):
        captured = {}

        class FakeAnalyze:
            async def answer_question(self, document_id, question, student_id):
                captured["document_id"] = document_id
                captured["question"] = question
                captured["student_id"] = student_id
                return "respuesta con doc"

        svc = ChatTutorService(analyze_service=FakeAnalyze())
        doc_id = uuid4()
        student_id = uuid4()
        answer = await svc.answer(document_id=doc_id, question="q", student_id=student_id)
        assert answer == "respuesta con doc"
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
