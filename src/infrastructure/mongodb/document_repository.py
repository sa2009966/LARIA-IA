from typing import Optional
from uuid import UUID

from motor.motor_asyncio import AsyncIOMotorDatabase

from src.domain.aggregates.document_aggregate import DocumentAggregate, DocumentStatus
from src.domain.ports.repositories import DocumentRepository
from src.domain.value_objects.analysis_result import AnalysisResult
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
            "key_concepts": list(result.key_concepts),
            "suggested_questions": list(result.suggested_questions),
            "confidence_score": result.confidence_score,
        }

    @staticmethod
    def _analysis_result_from_doc(doc: dict) -> AnalysisResult:
        concepts_raw = doc.get("key_concepts", [])
        concepts: list[str] = []
        for item in concepts_raw:
            # Compatibilidad con documentos antiguos (tuple concept, score).
            if isinstance(item, (list, tuple)) and item:
                concepts.append(str(item[0]))
            else:
                concepts.append(str(item))
        questions_raw = doc.get("suggested_questions", [])
        questions: list[str] = []
        for item in questions_raw:
            if isinstance(item, dict):
                questions.append(str(item.get("text", "")))
            else:
                questions.append(str(item))
        return AnalysisResult(
            summary=doc["summary"],
            key_concepts=concepts,
            suggested_questions=questions,
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