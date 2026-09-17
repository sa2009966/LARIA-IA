from typing import Optional
from uuid import UUID

from motor.motor_asyncio import AsyncIOMotorDatabase

from src.domain.aggregates.learning_path import LearningModule, LearningPathAggregate
from src.domain.ports.repositories import LearningPathRepository
from src.domain.value_objects.question import Difficulty
from src.infrastructure.mongodb.database import get_database


class MongoDBLearningPathRepository(LearningPathRepository):

    def __init__(self, database: Optional[AsyncIOMotorDatabase] = None) -> None:
        self._database = database

    async def _get_db(self) -> AsyncIOMotorDatabase:
        if self._database is None:
            self._database = await get_database()
        return self._database

    @staticmethod
    def _module_to_doc(m: LearningModule) -> dict:
        return {
            "id": str(m.id),
            "title": m.title,
            "concept": m.concept,
            "difficulty": m.difficulty.value,
            "prerequisites": list(m.prerequisites),
            "status": m.status,
            "mastery": m.mastery,
            "position": m.position,
        }

    @staticmethod
    def _module_from_doc(d: dict) -> LearningModule:
        return LearningModule(
            id=UUID(d["id"]),
            title=d.get("title", ""),
            concept=d.get("concept", ""),
            difficulty=Difficulty(d.get("difficulty", "easy")),
            prerequisites=list(d.get("prerequisites", [])),
            status=d.get("status", "locked"),
            mastery=float(d.get("mastery", 0.0)),
            position=int(d.get("position", 0)),
        )

    @staticmethod
    def _to_doc(path: LearningPathAggregate) -> dict:
        return {
            "_id": str(path.id),
            "owner_id": str(path.owner_id),
            "subject": path.subject,
            "title": path.title,
            "modules": [MongoDBLearningPathRepository._module_to_doc(m) for m in path.modules],
            "created_at": path.created_at,
            "updated_at": path.updated_at,
        }

    @staticmethod
    def _from_doc(doc: dict) -> LearningPathAggregate:
        return LearningPathAggregate(
            id=UUID(doc["_id"]),
            owner_id=UUID(doc["owner_id"]),
            subject=doc.get("subject", ""),
            title=doc.get("title", "Ruta de aprendizaje"),
            modules=[MongoDBLearningPathRepository._module_from_doc(m) for m in doc.get("modules", [])],
            created_at=doc["created_at"],
            updated_at=doc["updated_at"],
        )

    async def find_by_id(self, path_id: UUID) -> Optional[LearningPathAggregate]:
        db = await self._get_db()
        doc = await db.learning_paths.find_one({"_id": str(path_id)})
        return self._from_doc(doc) if doc else None

    async def find_by_owner(self, owner_id: UUID) -> list[LearningPathAggregate]:
        db = await self._get_db()
        cursor = db.learning_paths.find({"owner_id": str(owner_id)}).sort("updated_at", -1)
        results = []
        async for doc in cursor:
            results.append(self._from_doc(doc))
        return results

    async def save(self, path: LearningPathAggregate) -> None:
        db = await self._get_db()
        doc = self._to_doc(path)
        await db.learning_paths.replace_one({"_id": doc["_id"]}, doc, upsert=True)

    async def delete(self, path_id: UUID) -> None:
        db = await self._get_db()
        await db.learning_paths.delete_one({"_id": str(path_id)})
