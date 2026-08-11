"""Outbox Mongo: persiste eventos y los despacha a handlers locales.

Eventos soportados (serialize/deserialize completo):
- QuizAttemptCompletedEvent
- TutorQuestionAskedEvent

Cualquier otro DomainEvent se marca processed con last_error=unsupported_event
(documentado a propósito: no inventar proyección para eventos aún no cableados).
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from motor.motor_asyncio import AsyncIOMotorDatabase

from src.domain.events.domain_events import (
    DomainEvent,
    QuizAttemptCompletedEvent,
    TutorQuestionAskedEvent,
)
from src.domain.ports.event_bus import EventBus
from src.domain.ports.metrics_port import MetricsPort
from src.infrastructure.mongodb.database import get_database

logger = logging.getLogger(__name__)

_SUPPORTED = frozenset({"QuizAttemptCompletedEvent", "TutorQuestionAskedEvent"})


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _serialize(event: DomainEvent) -> dict[str, Any]:
    if isinstance(event, QuizAttemptCompletedEvent):
        return {
            "event_type": event.event_type,
            "aggregate_id": str(event.aggregate_id),
            "timestamp": event.timestamp.isoformat(),
            "quiz_id": str(event.quiz_id),
            "document_id": str(event.document_id),
            "student_id": str(event.student_id),
            "score": event.score,
            "total": event.total,
        }
    if isinstance(event, TutorQuestionAskedEvent):
        return {
            "event_type": event.event_type,
            "aggregate_id": str(event.aggregate_id),
            "timestamp": event.timestamp.isoformat(),
            "student_id": str(event.student_id),
            "document_id": str(event.document_id),
            "question": event.question,
            "answer": event.answer,
            "signal_kind": event.signal_kind,
            "signal_strength": event.signal_strength,
            "concepts": list(event.concepts),
            "latency_ms": event.latency_ms,
            "help_level": event.help_level,
            "cognitive_style": event.cognitive_style,
            "pedagogical_mode": event.pedagogical_mode,
        }
    return {
        "event_type": getattr(event, "event_type", type(event).__name__),
        "aggregate_id": str(getattr(event, "aggregate_id", "")),
        "timestamp": getattr(event, "timestamp", _utc_now()).isoformat(),
        "payload": {},
    }


def _deserialize(doc: dict[str, Any]) -> DomainEvent | None:
    et = doc.get("event_type")
    payload = doc.get("payload") or doc
    if et == "QuizAttemptCompletedEvent":
        return QuizAttemptCompletedEvent(
            aggregate_id=UUID(payload["aggregate_id"]),
            quiz_id=UUID(payload["quiz_id"]),
            document_id=UUID(payload["document_id"]),
            student_id=UUID(payload["student_id"]),
            score=int(payload["score"]),
            total=int(payload["total"]),
        )
    if et == "TutorQuestionAskedEvent":
        concepts = payload.get("concepts") or ()
        if isinstance(concepts, list):
            concepts = tuple(concepts)
        return TutorQuestionAskedEvent(
            aggregate_id=UUID(payload["aggregate_id"]),
            student_id=UUID(payload["student_id"]),
            document_id=UUID(payload["document_id"]),
            question=str(payload.get("question", "")),
            answer=str(payload.get("answer", "")),
            signal_kind=str(payload.get("signal_kind", "none")),
            signal_strength=float(payload.get("signal_strength", 0.0)),
            concepts=tuple(concepts),
            latency_ms=(
                float(payload["latency_ms"])
                if payload.get("latency_ms") is not None
                else None
            ),
            help_level=float(payload.get("help_level", 0.0)),
            cognitive_style=payload.get("cognitive_style"),
            pedagogical_mode=payload.get("pedagogical_mode"),
        )
    return None


class MongoOutboxEventBus(EventBus):
    """Persiste eventos en outbox; process_pending invoca handlers locales."""

    def __init__(
        self,
        database: AsyncIOMotorDatabase | None = None,
        metrics: MetricsPort | None = None,
    ) -> None:
        self._database = database
        self._metrics = metrics
        self._subscribers: dict[type, list[Callable[[DomainEvent], Any]]] = {}

    async def _get_db(self) -> AsyncIOMotorDatabase:
        if self._database is None:
            self._database = await get_database()
        return self._database

    async def publish(self, event: DomainEvent) -> None:
        db = await self._get_db()
        payload = _serialize(event)
        await db.event_outbox.insert_one(
            {
                "_id": str(uuid4()),
                "event_type": payload["event_type"],
                "payload": payload,
                "created_at": _utc_now(),
                "processed_at": None,
                "attempts": 0,
                "last_error": None,
            }
        )

    async def subscribe(self, event_type: type, handler: Callable[[DomainEvent], Any]) -> None:
        self._subscribers.setdefault(event_type, []).append(handler)

    async def count_pending(self) -> int:
        db = await self._get_db()
        return int(await db.event_outbox.count_documents({"processed_at": None}))

    async def process_pending(self, limit: int = 20) -> int:
        db = await self._get_db()
        cursor = (
            db.event_outbox.find({"processed_at": None})
            .sort("created_at", 1)
            .limit(limit)
        )
        processed = 0
        async for row in cursor:
            event = _deserialize(row)
            if event is None:
                await db.event_outbox.update_one(
                    {"_id": row["_id"]},
                    {
                        "$set": {
                            "processed_at": _utc_now(),
                            "last_error": "unsupported_event",
                        }
                    },
                )
                if self._metrics:
                    self._metrics.incr("outbox_failed", reason="unsupported_event")
                et = row.get("event_type", "?")
                if et not in _SUPPORTED:
                    logger.warning("outbox_unsupported_event type=%s", et)
                continue
            handlers = self._subscribers.get(type(event), [])
            try:
                for handler in handlers:
                    result = handler(event)
                    if hasattr(result, "__await__"):
                        await result
                await db.event_outbox.update_one(
                    {"_id": row["_id"]},
                    {"$set": {"processed_at": _utc_now(), "last_error": None}},
                )
                processed += 1
                if self._metrics:
                    self._metrics.incr("outbox_processed")
            except Exception as exc:  # noqa: BLE001 — worker no tumba el proceso
                logger.exception("outbox_handler_failed id=%s", row.get("_id"))
                await db.event_outbox.update_one(
                    {"_id": row["_id"]},
                    {
                        "$inc": {"attempts": 1},
                        "$set": {"last_error": str(exc)[:500]},
                    },
                )
                if self._metrics:
                    self._metrics.incr("outbox_failed", reason="handler_error")
        if self._metrics:
            pending = await self.count_pending()
            self._metrics.gauge("outbox_pending", float(pending))
        return processed
