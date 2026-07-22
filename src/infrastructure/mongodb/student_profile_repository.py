from typing import Optional
from uuid import UUID

from motor.motor_asyncio import AsyncIOMotorDatabase

from src.domain.aggregates.student_profile import DocumentMastery, StudentProfile
from src.domain.ports.repositories import StudentProfileRepository
from src.infrastructure.mongodb.database import get_database


class MongoDBStudentProfileRepository(StudentProfileRepository):

    def __init__(self, database: Optional[AsyncIOMotorDatabase] = None) -> None:
        self._database = database

    async def _get_db(self) -> AsyncIOMotorDatabase:
        if self._database is None:
            self._database = await get_database()
        return self._database

    @staticmethod
    def _to_doc(profile: StudentProfile) -> dict:
        return {
            "_id": str(profile.student_id),
            "student_id": str(profile.student_id),
            "mastery_by_document": {
                str(doc_id): {
                    "document_id": str(m.document_id),
                    "attempts": m.attempts,
                    "mastery": m.mastery,
                    "last_score_ratio": m.last_score_ratio,
                    "incorrect_streak": m.incorrect_streak,
                    "struggle_signals": m.struggle_signals,
                }
                for doc_id, m in profile.mastery_by_document.items()
            },
            "frequent_errors": list(profile.frequent_errors),
            "pace": profile.pace,
            "total_attempts": profile.total_attempts,
            "total_struggle_signals": profile.total_struggle_signals,
            "updated_at": profile.updated_at,
        }

    @staticmethod
    def _from_doc(doc: dict) -> StudentProfile:
        mastery: dict[UUID, DocumentMastery] = {}
        for key, raw in (doc.get("mastery_by_document") or {}).items():
            doc_id = UUID(raw.get("document_id", key))
            mastery[doc_id] = DocumentMastery(
                document_id=doc_id,
                attempts=int(raw.get("attempts", 0)),
                mastery=float(raw.get("mastery", 0.0)),
                last_score_ratio=float(raw.get("last_score_ratio", 0.0)),
                incorrect_streak=int(raw.get("incorrect_streak", 0)),
                struggle_signals=int(raw.get("struggle_signals", 0)),
            )
        return StudentProfile(
            student_id=UUID(doc["student_id"]),
            mastery_by_document=mastery,
            frequent_errors=list(doc.get("frequent_errors") or []),
            pace=doc.get("pace", "steady"),
            total_attempts=int(doc.get("total_attempts", 0)),
            total_struggle_signals=int(doc.get("total_struggle_signals", 0)),
            updated_at=doc["updated_at"],
        )

    async def find_by_student(self, student_id: UUID) -> Optional[StudentProfile]:
        db = await self._get_db()
        doc = await db.student_profiles.find_one({"_id": str(student_id)})
        return self._from_doc(doc) if doc else None

    async def save(self, profile: StudentProfile) -> None:
        db = await self._get_db()
        payload = self._to_doc(profile)
        await db.student_profiles.replace_one({"_id": payload["_id"]}, payload, upsert=True)
