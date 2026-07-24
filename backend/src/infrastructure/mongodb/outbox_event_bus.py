import time
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from motor.motor_asyncio import AsyncIOMotorDatabase

from src.domain.events.domain_events import DomainEvent, QuizAttemptCompletedEvent
from src.domain.ports.event_bus import EventBus
from src.infrastructure.mongodb.database import get_database


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
    # Fallback genérico: solo tipo + aggregate
    return {
        "event_type": event.event_type,
        "aggregate_id": str(event.aggregate_id),
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
    return None


class MongoOutboxEventBus(EventBus):
    """Persiste eventos en outbox; process_pending invoca handlers locales."""

    def __init__(self, database: AsyncIOMotorDatabase | None = None) -> None:
        self._database = database
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
            except Exception as exc:  # noqa: BLE001 — worker no tumba el proceso
                await db.event_outbox.update_one(
                    {"_id": row["_id"]},
                    {
                        "$inc": {"attempts": 1},
                        "$set": {"last_error": str(exc)[:500]},
                    },
                )
        return processed
