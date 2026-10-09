"""Caché global de temarios investigados (ADR-039): colección `curriculum_research`.

No tiene datos personales: es el temario de un tema y un nivel, compartido por todos.
"""
from datetime import datetime, timezone
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from src.domain.ports.lesson_generator import Source, SyllabusItem
from src.infrastructure.mongodb.database import get_database


def item_to_doc(i: SyllabusItem) -> dict:
    return {
        "title": i.title,
        "prerequisites": list(i.prerequisites),
        "key_points": list(i.key_points),
        "sources": [{"title": s.title, "url": s.url} for s in i.sources],
    }


def item_from_doc(d: dict) -> SyllabusItem:
    return SyllabusItem(
        title=d.get("title", ""),
        prerequisites=tuple(d.get("prerequisites") or ()),
        key_points=tuple(d.get("key_points") or ()),
        sources=tuple(Source(s.get("title", ""), s.get("url", "")) for s in d.get("sources") or ()),
    )


class MongoDBCurriculumResearchRepository:
    def __init__(self, database: Optional[AsyncIOMotorDatabase] = None) -> None:
        self._database = database

    async def _get_db(self) -> AsyncIOMotorDatabase:
        if self._database is None:
            self._database = await get_database()
        return self._database

    @staticmethod
    def _id(topic: str, level: str) -> str:
        return f"{topic}|{level}"

    async def find(self, topic: str, level: str) -> list[SyllabusItem] | None:
        db = await self._get_db()
        d = await db.curriculum_research.find_one({"_id": self._id(topic, level)})
        return [item_from_doc(m) for m in d.get("modules") or []] if d else None

    async def save(self, topic: str, level: str, items: list[SyllabusItem]) -> None:
        db = await self._get_db()
        await db.curriculum_research.replace_one(
            {"_id": self._id(topic, level)},
            {
                "_id": self._id(topic, level),
                "topic": topic,
                "level": level,
                "modules": [item_to_doc(i) for i in items],
                "created_at": datetime.now(timezone.utc),
            },
            upsert=True,
        )
