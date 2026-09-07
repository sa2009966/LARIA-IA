"""Round-trip outbox: TutorQuestionAskedEvent → projector → StudentProfile."""
from __future__ import annotations

from uuid import uuid4

import pytest
from unittest.mock import AsyncMock, patch

from src.application.services.learning_evidence_projector import LearningEvidenceProjector
from src.domain.events.domain_events import (
    QuizAttemptCompletedEvent,
    TutorQuestionAskedEvent,
    UserRegisteredEvent,
)
from src.infrastructure.metrics.in_memory_metrics import InMemoryMetrics
from src.infrastructure.mongodb.outbox_event_bus import (
    MongoOutboxEventBus,
    _deserialize,
    _serialize,
)
from src.infrastructure.persistence.in_memory_student_profile_repo import (
    InMemoryStudentProfileRepository,
)
from src.infrastructure.persistence.in_memory_tutor_interaction_repo import (
    InMemoryTutorInteractionRepository,
)


class _FakeCursor:
    def __init__(self, rows):
        self._rows = list(rows)

    def sort(self, *_a, **_k):
        return self

    def limit(self, n):
        self._rows = self._rows[:n]
        return self

    def __aiter__(self):
        self._it = iter(self._rows)
        return self

    async def __anext__(self):
        try:
            return next(self._it)
        except StopIteration as exc:
            raise StopAsyncIteration from exc


class _FakeCollection:
    def __init__(self):
        self.docs: list[dict] = []

    async def insert_one(self, doc):
        for i, existing in enumerate(self.docs):
            if existing.get("_id") == doc.get("_id"):
                self.docs[i] = doc
                return
        self.docs.append(doc)

    def find(self, query):
        rows = [d for d in self.docs if d.get("processed_at") is None]
        return _FakeCursor(rows)

    async def update_one(self, filt, update):
        for d in self.docs:
            if d.get("_id") == filt.get("_id"):
                if "$set" in update:
                    d.update(update["$set"])
                if "$inc" in update:
                    for k, v in update["$inc"].items():
                        d[k] = d.get(k, 0) + v
                return

    async def count_documents(self, query):
        return sum(1 for d in self.docs if d.get("processed_at") is None)


class _FakeDB:
    def __init__(self):
        self.event_outbox = _FakeCollection()


def test_serialize_tutor_question_keeps_pedagogical_fields():
    sid, did = uuid4(), uuid4()
    event = TutorQuestionAskedEvent(
        aggregate_id=did,
        student_id=sid,
        document_id=did,
        question="¿qué es una fracción?",
        answer="Una parte de un todo.",
        signal_kind="struggle",
        signal_strength=0.8,
        concepts=("fracciones",),
        latency_ms=120.0,
        help_level=0.5,
        cognitive_style="visual",
        pedagogical_mode="socratic",
    )
    payload = _serialize(event)
    assert payload["event_type"] == "TutorQuestionAskedEvent"
    assert payload["event_id"] == str(event.event_id)
    assert payload["signal_kind"] == "struggle"
    assert payload["concepts"] == ["fracciones"]
    assert payload["cognitive_style"] == "visual"
    restored = _deserialize({"event_type": payload["event_type"], "payload": payload})
    assert restored is not None
    assert restored.event_id == event.event_id
    assert restored.student_id == sid
    assert restored.concepts == ("fracciones",)
    assert restored.pedagogical_mode == "socratic"


def test_unsupported_event_serializes_empty_payload():
    event = UserRegisteredEvent(aggregate_id=uuid4(), email="a@b.com")
    payload = _serialize(event)
    assert payload.get("payload") == {}
    assert _deserialize({"event_type": payload["event_type"], "payload": payload}) is None


@pytest.mark.asyncio
async def test_process_pending_projects_ask_into_profile():
    metrics = InMemoryMetrics()
    bus = MongoOutboxEventBus(database=_FakeDB(), metrics=metrics)
    profiles = InMemoryStudentProfileRepository()
    interactions = InMemoryTutorInteractionRepository()
    projector = LearningEvidenceProjector(
        interactions,
        bus,
        profile_repository=profiles,
        metrics=metrics,
    )
    await projector.register()

    student_id = uuid4()
    document_id = uuid4()
    await bus.publish(
        TutorQuestionAskedEvent(
            aggregate_id=document_id,
            student_id=student_id,
            document_id=document_id,
            question="no entiendo",
            answer="pista...",
            signal_kind="struggle",
            signal_strength=0.9,
            concepts=("algebra",),
            cognitive_style="analytical",
            pedagogical_mode="guided",
        )
    )
    n = await bus.process_pending(limit=10)
    assert n == 1
    profile = await profiles.find_by_student(student_id)
    assert profile is not None
    assert profile.total_struggle_signals >= 1
    row = bus._database.event_outbox.docs[0]
    assert row["last_error"] is None
    assert row["processed_at"] is not None
    snap = metrics.snapshot()
    assert any(k.startswith("outbox_processed") for k in snap["counters"])
    assert any(k.startswith("profile_updates") for k in snap["counters"])


@pytest.mark.asyncio
async def test_process_pending_projects_quiz_into_profile():
    metrics = InMemoryMetrics()
    bus = MongoOutboxEventBus(database=_FakeDB(), metrics=metrics)
    profiles = InMemoryStudentProfileRepository()
    interactions = InMemoryTutorInteractionRepository()
    projector = LearningEvidenceProjector(
        interactions,
        bus,
        profile_repository=profiles,
        metrics=metrics,
    )
    await projector.register()

    student_id = uuid4()
    document_id = uuid4()
    quiz_id = uuid4()
    await bus.publish(
        QuizAttemptCompletedEvent(
            aggregate_id=uuid4(),
            quiz_id=quiz_id,
            document_id=document_id,
            student_id=student_id,
            score=2,
            total=3,
        )
    )
    n = await bus.process_pending(limit=10)
    assert n == 1
    profile = await profiles.find_by_student(student_id)
    assert profile is not None
    assert profile.total_attempts >= 1
    assert profile.mastery_for(document_id) == pytest.approx(2 / 3)
    row = bus._database.event_outbox.docs[0]
    assert row["last_error"] is None
    assert row["processed_at"] is not None
    snap = metrics.snapshot()
    assert any(k.startswith("outbox_processed") for k in snap["counters"])
    assert any("profile_updates" in k for k in snap["counters"])


@pytest.mark.asyncio
async def test_unsupported_increments_outbox_unsupported_not_failed():
    metrics = InMemoryMetrics()
    bus = MongoOutboxEventBus(database=_FakeDB(), metrics=metrics)
    await bus.publish(UserRegisteredEvent(aggregate_id=uuid4(), email="x@y.com"))
    n = await bus.process_pending(limit=5)
    assert n == 0
    row = bus._database.event_outbox.docs[0]
    assert row["last_error"] == "unsupported_event"
    assert row["processed_at"] is not None
    snap = metrics.snapshot()
    assert any("outbox_unsupported" in k for k in snap["counters"])
    assert not any(
        k.startswith('outbox_failed{reason="unsupported_event"}') or k == "outbox_failed"
        for k in snap["counters"]
    )


@pytest.mark.asyncio
async def test_outbox_handler_failure_increments_failed_metric():
    metrics = InMemoryMetrics()
    bus = MongoOutboxEventBus(database=_FakeDB(), metrics=metrics)
    student_id, document_id = uuid4(), uuid4()

    async def _boom(_event):
        raise RuntimeError("handler exploded")

    await bus.subscribe(TutorQuestionAskedEvent, _boom)
    await bus.publish(
        TutorQuestionAskedEvent(
            aggregate_id=document_id,
            student_id=student_id,
            document_id=document_id,
            question="q",
            answer="a",
        )
    )
    assert await bus.process_pending(limit=5) == 0
    row = bus._database.event_outbox.docs[0]
    assert row["last_error"] == "handler exploded"
    assert row["processed_at"] is None
    assert row["attempts"] == 1
    snap = metrics.snapshot()
    assert any("outbox_failed" in k for k in snap["counters"])


@pytest.mark.asyncio
async def test_outbox_lazy_database_via_get_db():
    mock_db = _FakeDB()
    bus = MongoOutboxEventBus()
    with patch(
        "src.infrastructure.mongodb.outbox_event_bus.get_database",
        AsyncMock(return_value=mock_db),
    ):
        assert await bus.count_pending() == 0


@pytest.mark.asyncio
async def test_outbox_reprocess_same_row_does_not_double_evidence():
    metrics = InMemoryMetrics()
    bus = MongoOutboxEventBus(database=_FakeDB(), metrics=metrics)
    profiles = InMemoryStudentProfileRepository()
    interactions = InMemoryTutorInteractionRepository()
    projector = LearningEvidenceProjector(
        interactions,
        bus,
        profile_repository=profiles,
        metrics=metrics,
    )
    await projector.register()

    student_id = uuid4()
    document_id = uuid4()
    event = TutorQuestionAskedEvent(
        aggregate_id=document_id,
        student_id=student_id,
        document_id=document_id,
        question="no entiendo",
        answer="pista...",
        signal_kind="confusion",
        signal_strength=0.9,
        concepts=("algebra",),
    )
    await bus.publish(event)
    assert await bus.process_pending(limit=10) == 1
    profile = await profiles.find_by_student(student_id)
    assert profile is not None
    assert profile.total_struggle_signals == 1

    row = bus._database.event_outbox.docs[0]
    row["processed_at"] = None
    row["last_error"] = None
    n = await bus.process_pending(limit=10)
    assert n == 1
    profile = await profiles.find_by_student(student_id)
    assert profile is not None
    assert profile.total_struggle_signals == 1
    assert row["last_error"] is None
