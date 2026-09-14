"""Tests de outbox y rate-limit rules."""
from uuid import uuid4

import pytest

from src.domain.events.domain_events import QuizAttemptCompletedEvent
from src.infrastructure.persistence.in_memory_event_bus import InMemoryEventBus
from src.infrastructure.rate_limit import SlidingWindowCounter, _match_rule


def test_rate_rules_prefer_ia_paths():
    assert _match_rule("/api/v1/documents/abc/analyze", "POST")[0] == "ia:analyze"
    assert _match_rule("/api/v1/documents/abc/ask", "POST")[0] == "ia:ask"
    assert _match_rule("/api/v1/documents/abc/quiz", "POST")[0] == "ia:quiz"
    assert _match_rule("/api/v1/documents/", "GET")[0] == "/api/v1/documents/"


def test_sliding_window_memory():
    c = SlidingWindowCounter()
    assert c.allow("k", 2, 60)
    assert c.allow("k", 2, 60)
    assert not c.allow("k", 2, 60)


@pytest.mark.asyncio
async def test_memory_bus_still_sync_for_tests():
    bus = InMemoryEventBus()
    seen = []

    async def handler(event):
        seen.append(event.score)

    await bus.subscribe(QuizAttemptCompletedEvent, handler)
    await bus.publish(
        QuizAttemptCompletedEvent(
            aggregate_id=uuid4(),
            quiz_id=uuid4(),
            document_id=uuid4(),
            student_id=uuid4(),
            score=1,
            total=3,
        )
    )
    assert seen == [1]
