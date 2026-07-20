from typing import Optional
from uuid import UUID

from motor.motor_asyncio import AsyncIOMotorDatabase

from src.domain.aggregates.document_aggregate import DocumentAggregate, DocumentStatus
from src.domain.ports.repositories import DocumentRepository
from src.domain.value_objects.analysis_result import AnalysisResult
from src.domain.value_objects.question import Question, Difficulty, BloomLevel
from src.domain.value_objects.subject import Subject
from src.infrastructure.mongodb.database import get_database


class MongoDBDocumentRepository(DocumentRepository):

    def __init__(self, database: Optional[AsyncIOMotorDatabase] = None) -> None:
        self._database = database

    async def _get_db(self) -> AsyncIOMotorDatabase:
        if self._database is None:
            self._database = await get_database()
        return self._database

    @staticmethod
    def _analysis_result_to_doc(result: AnalysisResult) -> dict:
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
    def _analysis_result_from_doc(doc: dict) -> AnalysisResult:
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
    def _to_doc(doc: DocumentAggregate) -> dict:
        result = {
            "_id": str(doc.id),
            "owner_id": str(doc.owner_id),
            "filename": doc.filename,
            "content": doc.content,
            "subject": doc.subject.value,
            "status": doc.status.value,
            "uploaded_at": doc.uploaded_at,
            "error_message": doc.error_message,
        }
        if doc.analysis_result is not None:
            result["analysis_result"] = MongoDBDocumentRepository._analysis_result_to_doc(doc.analysis_result)
        return result

    @staticmethod
    def _from_doc(doc: dict) -> DocumentAggregate:
        subject = Subject(doc["subject"])
        agg = DocumentAggregate(
            id=UUID(doc["_id"]),
            owner_id=UUID(doc["owner_id"]),
            filename=doc["filename"],
            content=doc["content"],
            subject=subject,
            status=DocumentStatus(doc["status"]),
            uploaded_at=doc["uploaded_at"],
            error_message=doc.get("error_message"),
        )
        if "analysis_result" in doc and doc["analysis_result"] is not None:
            agg.analysis_result = MongoDBDocumentRepository._analysis_result_from_doc(doc["analysis_result"])
        return agg

    async def find_by_id(self, document_id: UUID) -> Optional[DocumentAggregate]:
        db = await self._get_db()
        doc = await db.documents.find_one({"_id": str(document_id)})
        return self._from_doc(doc) if doc else None

    async def find_by_owner(self, owner_id: UUID) -> list[DocumentAggregate]:
        db = await self._get_db()
        cursor = db.documents.find({"owner_id": str(owner_id)})
        return [self._from_doc(doc) async for doc in cursor]

    async def save(self, document: DocumentAggregate) -> None:
        db = await self._get_db()
        doc = self._to_doc(document)
        await db.documents.replace_one({"_id": doc["_id"]}, doc, upsert=True)

    async def delete(self, document_id: UUID) -> None:
        db = await self._get_db()
        await db.documents.delete_one({"_id": str(document_id)})