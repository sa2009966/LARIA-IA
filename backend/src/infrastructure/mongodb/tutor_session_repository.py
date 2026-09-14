from typing import Optional
from uuid import UUID

from motor.motor_asyncio import AsyncIOMotorDatabase

from src.domain.aggregates.tutor_session import SessionStep, TutorSession
from src.domain.exceptions import ConcurrencyError
from src.domain.ports.repositories import TutorSessionRepository
from src.infrastructure.mongodb.database import get_database


class MongoDBTutorSessionRepository(TutorSessionRepository):

    def __init__(self, database: Optional[AsyncIOMotorDatabase] = None) -> None:
        self._database = database

    async def _get_db(self) -> AsyncIOMotorDatabase:
        if self._database is None:
            self._database = await get_database()
        return self._database

    @staticmethod
    def _to_doc(session: TutorSession, version: int) -> dict:
        return {
            "_id": f"{session.student_id}:{session.document_id}",
            "id": str(session.id),
            "student_id": str(session.student_id),
            "document_id": str(session.document_id),
            "step": session.step.value,
            "objective": session.objective,
            "focus_concepts": list(session.focus_concepts),
            "hints_given": list(session.hints_given),
            "turns": session.turns,
            "updated_at": session.updated_at,
            "version": version,
        }

    @staticmethod
    def _from_doc(doc: dict) -> TutorSession:
        return TutorSession(
            id=UUID(doc["id"]),
            student_id=UUID(doc["student_id"]),
            document_id=UUID(doc["document_id"]),
            step=SessionStep(doc.get("step", "introduce")),
            objective=doc.get("objective", ""),
            focus_concepts=list(doc.get("focus_concepts") or []),
            hints_given=list(doc.get("hints_given") or []),
            turns=int(doc.get("turns", 0)),
            updated_at=doc["updated_at"],
            version=int(doc.get("version", 0)),
        )

    async def find_by_student_document(
        self, student_id: UUID, document_id: UUID
    ) -> Optional[TutorSession]:
        db = await self._get_db()
        doc = await db.tutor_sessions.find_one({"_id": f"{student_id}:{document_id}"})
        return self._from_doc(doc) if doc else None

    async def save(self, session: TutorSession) -> None:
        db = await self._get_db()
        expected = int(session.version)
        new_version = expected + 1
        payload = self._to_doc(session, new_version)
        _id = payload["_id"]
        if expected == 0:
            existing = await db.tutor_sessions.find_one({"_id": _id}, projection={"version": 1})
            if existing is None:
                await db.tutor_sessions.insert_one(payload)
            else:
                result = await db.tutor_sessions.replace_one(
                    {
                        "_id": _id,
                        "$or": [{"version": 0}, {"version": {"$exists": False}}],
                    },
                    payload,
                )
                if result.matched_count == 0:
                    raise ConcurrencyError("TutorSession concurrent update")
        else:
            result = await db.tutor_sessions.replace_one(
                {"_id": _id, "version": expected},
                payload,
            )
            if result.matched_count == 0:
                raise ConcurrencyError("TutorSession concurrent update")
        session.version = new_version

    async def delete_by_document(self, document_id: UUID) -> int:
        db = await self._get_db()
        result = await db.tutor_sessions.delete_many({"document_id": str(document_id)})
        return int(result.deleted_count)
