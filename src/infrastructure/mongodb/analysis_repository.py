from typing import Optional
from uuid import UUID

from motor.motor_asyncio import AsyncIOMotorDatabase

from src.domain.aggregates.analysis_aggregate import AnalysisAggregate
from src.domain.ports.repositories import AnalysisRepository
from src.domain.value_objects.analysis_result import AnalysisResult
from src.domain.value_objects.question import Quiz, QuizQuestion, Difficulty
from src.infrastructure.mongodb.database import get_database


class MongoDBAnalysisRepository(AnalysisRepository):

    def __init__(self, database: Optional[AsyncIOMotorDatabase] = None) -> None:
        self._database = database

    async def _get_db(self) -> AsyncIOMotorDatabase:
        if self._database is None:
            self._database = await get_database()
        return self._database

    @staticmethod
    def _quiz_to_doc(quiz: Quiz) -> dict:
        return {
            "questions": [
                {
                    "text": q.text,
                    "options": q.options,
                    "correct_answer": q.correct_answer,
                    "difficulty": q.difficulty.value,
                }
                for q in quiz.questions
            ],
        }

    @staticmethod
    def _quiz_from_doc(doc: dict) -> Quiz:
        questions = []
        for q in doc.get("questions", []):
            questions.append(QuizQuestion(
                text=q["text"],
                options=q["options"],
                correct_answer=q["correct_answer"],
                difficulty=Difficulty(q.get("difficulty", "medium")),
            ))
        return Quiz(questions=questions)

    @staticmethod
    def _result_to_doc(result: AnalysisResult) -> dict:
        return {
            "summary": result.summary,
            "key_concepts": [(c, s) for c, s in result.key_concepts],
            "suggested_questions": [
                {
                    "text": q.text,
                    "difficulty": q.difficulty.value,
                    "bloom_level": q.bloom_level.value,
                }
                for q in result.suggested_questions
            ],
            "confidence_score": result.confidence_score,
        }

    @staticmethod
    def _result_from_doc(doc: dict) -> Optional[AnalysisResult]:
        if doc is None:
            return None
        from src.domain.value_objects.question import Question, Difficulty, BloomLevel
        suggested = []
        for q in doc.get("suggested_questions", []):
            suggested.append(Question(
                text=q["text"],
                difficulty=Difficulty(q.get("difficulty", "easy")),
                bloom_level=BloomLevel(q.get("bloom_level", "remember")),
            ))
        return AnalysisResult(
            summary=doc["summary"],
            key_concepts=[(c, s) for c, s in doc.get("key_concepts", [])],
            suggested_questions=suggested,
            confidence_score=doc.get("confidence_score", 0.0),
        )

    @staticmethod
    def _to_doc(analysis: AnalysisAggregate) -> dict:
        doc: dict = {
            "_id": str(analysis.id),
            "document_id": str(analysis.document_id),
            "model_used": analysis.model_used,
            "created_at": analysis.created_at,
        }
        if analysis.result is not None:
            doc["result"] = MongoDBAnalysisRepository._result_to_doc(analysis.result)
        if analysis.quiz is not None:
            doc["quiz"] = MongoDBAnalysisRepository._quiz_to_doc(analysis.quiz)
        return doc

    @staticmethod
    def _from_doc(doc: dict) -> AnalysisAggregate:
        agg = AnalysisAggregate(
            id=UUID(doc["_id"]),
            document_id=UUID(doc["document_id"]),
            model_used=doc.get("model_used", ""),
            created_at=doc["created_at"],
        )
        if "result" in doc and doc["result"] is not None:
            agg.result = MongoDBAnalysisRepository._result_from_doc(doc["result"])
        if "quiz" in doc and doc["quiz"] is not None:
            agg.quiz = MongoDBAnalysisRepository._quiz_from_doc(doc["quiz"])
        return agg

    async def save(self, analysis: AnalysisAggregate) -> None:
        db = await self._get_db()
        doc = self._to_doc(analysis)
        await db.analyses.replace_one({"_id": doc["_id"]}, doc, upsert=True)

    async def find_by_document(self, document_id: UUID) -> Optional[AnalysisAggregate]:
        db = await self._get_db()
        doc = await db.analyses.find_one({"document_id": str(document_id)})
        return self._from_doc(doc) if doc else None