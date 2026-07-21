from typing import Optional
from uuid import UUID

from motor.motor_asyncio import AsyncIOMotorDatabase

from src.domain.aggregates.quiz_aggregate import QuizAggregate
from src.domain.ports.repositories import QuizRepository
from src.domain.value_objects.question import Difficulty, QuizQuestion
from src.infrastructure.mongodb.database import get_database


class MongoDBQuizRepository(QuizRepository):

    def __init__(self, database: Optional[AsyncIOMotorDatabase] = None) -> None:
        self._database = database

    async def _get_db(self) -> AsyncIOMotorDatabase:
        if self._database is None:
            self._database = await get_database()
        return self._database

    @staticmethod
    def _question_to_doc(q: QuizQuestion) -> dict:
        difficulty = q.difficulty.value if isinstance(q.difficulty, Difficulty) else str(q.difficulty)
        return {
            "text": q.text,
            "options": dict(q.options),
            "correct_answer": q.correct_answer,
            "difficulty": difficulty,
        }

    @staticmethod
    def _question_from_doc(doc: dict) -> QuizQuestion:
        return QuizQuestion(
            text=doc["text"],
            options=dict(doc["options"]),
            correct_answer=doc["correct_answer"],
            difficulty=Difficulty(doc.get("difficulty", "medium")),
        )

    @staticmethod
    def _to_doc(quiz: QuizAggregate) -> dict:
        return {
            "_id": str(quiz.id),
            "document_id": str(quiz.document_id),
            "owner_id": str(quiz.owner_id),
            "questions": [MongoDBQuizRepository._question_to_doc(q) for q in quiz.questions],
            "created_at": quiz.created_at,
        }

    @staticmethod
    def _from_doc(doc: dict) -> QuizAggregate:
        return QuizAggregate(
            id=UUID(doc["_id"]),
            document_id=UUID(doc["document_id"]),
            owner_id=UUID(doc["owner_id"]),
            questions=[MongoDBQuizRepository._question_from_doc(q) for q in doc.get("questions", [])],
            created_at=doc["created_at"],
        )

    async def find_by_id(self, quiz_id: UUID) -> Optional[QuizAggregate]:
        db = await self._get_db()
        doc = await db.quizzes.find_one({"_id": str(quiz_id)})
        return self._from_doc(doc) if doc else None

    async def find_by_document(self, document_id: UUID) -> list[QuizAggregate]:
        db = await self._get_db()
        cursor = db.quizzes.find({"document_id": str(document_id)})
        return [self._from_doc(doc) async for doc in cursor]

    async def find_by_owner(self, owner_id: UUID) -> list[QuizAggregate]:
        db = await self._get_db()
        cursor = db.quizzes.find({"owner_id": str(owner_id)})
        return [self._from_doc(doc) async for doc in cursor]

    async def save(self, quiz: QuizAggregate) -> None:
        db = await self._get_db()
        doc = self._to_doc(quiz)
        await db.quizzes.replace_one({"_id": doc["_id"]}, doc, upsert=True)
