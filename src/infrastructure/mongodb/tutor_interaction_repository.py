from typing import Optional
from uuid import UUID

from motor.motor_asyncio import AsyncIOMotorDatabase

from src.domain.aggregates.tutor_interaction import TutorInteractionAggregate
from src.domain.ports.repositories import TutorInteractionRepository
from src.infrastructure.mongodb.database import get_database


class MongoDBTutorInteractionRepository(TutorInteractionRepository):

    def __init__(self, database: Optional[AsyncIOMotorDatabase] = None) -> None:
        self._database = database

    async def _get_db(self) -> AsyncIOMotorDatabase:
        if self._database is None:
            self._database = await get_database()
        return self._database

    @staticmethod
    def _to_doc(interaction: TutorInteractionAggregate) -> dict:
        return {
            "_id": str(interaction.id),
            "student_id": str(interaction.student_id),
            "document_id": str(interaction.document_id),
            "question": interaction.question,
            "answer": interaction.answer,
            "asked_at": interaction.asked_at,
        }

    @staticmethod
    def _from_doc(doc: dict) -> TutorInteractionAggregate:
        return TutorInteractionAggregate(
            id=UUID(doc["_id"]),
            student_id=UUID(doc["student_id"]),
            document_id=UUID(doc["document_id"]),
            question=doc["question"],
            answer=doc["answer"],
            asked_at=doc["asked_at"],
        )

    async def find_by_id(self, interaction_id: UUID) -> Optional[TutorInteractionAggregate]:
        db = await self._get_db()
        doc = await db.tutor_interactions.find_one({"_id": str(interaction_id)})
        return self._from_doc(doc) if doc else None

    async def find_by_student(self, student_id: UUID) -> list[TutorInteractionAggregate]:
        db = await self._get_db()
        cursor = db.tutor_interactions.find({"student_id": str(student_id)})
        return [self._from_doc(doc) async for doc in cursor]

    async def find_by_document(self, document_id: UUID) -> list[TutorInteractionAggregate]:
        db = await self._get_db()
        cursor = db.tutor_interactions.find({"document_id": str(document_id)})
        return [self._from_doc(doc) async for doc in cursor]

    async def save(self, interaction: TutorInteractionAggregate) -> None:
        db = await self._get_db()
        doc = self._to_doc(interaction)
        await db.tutor_interactions.replace_one({"_id": doc["_id"]}, doc, upsert=True)
