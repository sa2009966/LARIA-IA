"""Ramas adicionales de AnalyzeDocumentService."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.application.services.analyze_document_service import AnalyzeDocumentService
from src.application.services.llm_gate import LlmGate
from src.domain.aggregates.document_aggregate import DocumentAggregate, DocumentStatus
from src.domain.aggregates.tutor_session import TutorSession
from src.domain.ports.ia_analyst import IAAnalysisError
from src.domain.value_objects.analysis_result import AnalysisResult
from src.infrastructure.metrics.in_memory_metrics import InMemoryMetrics
from src.infrastructure.persistence.in_memory_document_repo import InMemoryDocumentRepository
from src.infrastructure.persistence.in_memory_tutor_interaction_repo import (
    InMemoryTutorInteractionRepository,
)
from src.infrastructure.persistence.in_memory_tutor_session_repo import (
    InMemoryTutorSessionRepository,
)


class _GateAnalyst:
    async def analyze_with_model(self, document, model: str):
        return AnalysisResult(summary="via gate", key_concepts=[], suggested_questions=[], confidence_score=0.7)

    async def answer_question_with_model(self, context, question, decision=None, *, model: str):
        return "gate-answer"


@pytest.mark.asyncio
async def test_execute_sin_ia_ni_gate_falla():
    repo = InMemoryDocumentRepository()
    owner = uuid4()
    doc = DocumentAggregate.upload(owner, "f.txt", "body", "Historia")
    await repo.save(doc)
    svc = AnalyzeDocumentService(document_repository=repo)
    with pytest.raises(ValueError, match="IA Analyst not configured"):
        await svc.execute(doc.id, owner)


@pytest.mark.asyncio
async def test_execute_via_llm_gate():
    repo = InMemoryDocumentRepository()
    owner = uuid4()
    doc = DocumentAggregate.upload(owner, "f.txt", "body", "Historia")
    await repo.save(doc)
    gate = LlmGate(_GateAnalyst(), metrics=InMemoryMetrics())
    svc = AnalyzeDocumentService(document_repository=repo, llm_gate=gate)
    result = await svc.execute(doc.id, owner)
    assert result.summary == "via gate"


@pytest.mark.asyncio
async def test_execute_error_generico_marca_documento():
    repo = AsyncMock()
    owner = uuid4()
    doc = DocumentAggregate.upload(owner, "f.txt", "body", "Historia")
    repo.find_by_id.side_effect = [doc, doc]
    repo.save = AsyncMock()
    ia = AsyncMock()
    ia.analyze.side_effect = RuntimeError("boom")
    bus = AsyncMock()
    svc = AnalyzeDocumentService(document_repository=repo, ia_analyst=ia, event_bus=bus)
    with pytest.raises(RuntimeError):
        await svc.execute(doc.id, owner)
    assert doc.status == DocumentStatus.ERROR


@pytest.mark.asyncio
async def test_execute_resetea_estado_analyzing_o_error():
    repo = AsyncMock()
    owner = uuid4()
    doc = DocumentAggregate.upload(owner, "f.txt", "body", "Historia")
    doc.mark_analyzing()
    repo.find_by_id.return_value = doc
    repo.save = AsyncMock()
    ia = AsyncMock()
    ia.analyze.return_value = AnalysisResult(summary="ok", key_concepts=[], suggested_questions=[], confidence_score=0.5)
    svc = AnalyzeDocumentService(document_repository=repo, ia_analyst=ia)
    await svc.execute(doc.id, owner, force_refresh=True)
    assert doc.status == DocumentStatus.ANALYZED


@pytest.mark.asyncio
async def test_answer_question_via_llm_gate_y_session_repo():
    repo = InMemoryDocumentRepository()
    interactions = InMemoryTutorInteractionRepository()
    sessions = InMemoryTutorSessionRepository()
    owner = uuid4()
    doc = DocumentAggregate.upload(owner, "f.txt", "algebra x", "Matemática")
    doc.complete_analysis(AnalysisResult(summary="s", key_concepts=["algebra"], suggested_questions=[], confidence_score=0.8))
    await repo.save(doc)
    gate = LlmGate(_GateAnalyst())
    svc = AnalyzeDocumentService(
        document_repository=repo,
        interaction_repository=interactions,
        session_repository=sessions,
        llm_gate=gate,
    )
    answer = await svc.answer_question(doc.id, "No entiendo las variables", owner)
    assert answer == "gate-answer"
    saved = await sessions.find_by_student_document(owner, doc.id)
    assert saved is not None
    assert saved.turns >= 1


@pytest.mark.asyncio
async def test_answer_question_sin_interaction_repo_falla():
    repo = InMemoryDocumentRepository()
    owner = uuid4()
    doc = DocumentAggregate.upload(owner, "f.txt", "x", "Historia")
    await repo.save(doc)
    svc = AnalyzeDocumentService(document_repository=repo, ia_analyst=AsyncMock())
    with pytest.raises(ValueError, match="interacciones"):
        await svc.answer_question(doc.id, "?", owner)


@pytest.mark.asyncio
async def test_answer_question_event_publish_failure_metrics():
    repo = AsyncMock()
    interactions = AsyncMock()
    interactions.save = AsyncMock()
    owner = uuid4()
    doc = DocumentAggregate.upload(owner, "f.txt", "x", "Historia")
    repo.find_by_id.return_value = doc
    ia = AsyncMock()
    ia.answer_question.return_value = "ok"
    bus = AsyncMock()
    bus.publish.side_effect = RuntimeError("bus")
    metrics = InMemoryMetrics()
    svc = AnalyzeDocumentService(
        document_repository=repo,
        ia_analyst=ia,
        interaction_repository=interactions,
        event_bus=bus,
        metrics=metrics,
    )
    assert await svc.answer_question(doc.id, "¿?", owner) == "ok"
    snap = metrics.snapshot()
    assert any("event_publish_failed" in k for k in snap["counters"])
