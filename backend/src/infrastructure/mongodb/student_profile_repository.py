from typing import Optional
from uuid import UUID
from datetime import datetime

from motor.motor_asyncio import AsyncIOMotorDatabase

from src.domain.aggregates.student_profile import (
    ConceptMastery,
    DocumentMastery,
    PedagogicalMemory,
    StudentProfile,
)
from src.domain.exceptions import ConcurrencyError
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
    def _to_doc(profile: StudentProfile, version: int) -> dict:
        mem = profile.pedagogical_memory
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
            "mastery_by_concept": {
                key: {
                    "concept_key": c.concept_key,
                    "attempts": c.attempts,
                    "mastery": c.mastery,
                    "last_score_ratio": c.last_score_ratio,
                    "document_ids": [str(d) for d in c.document_ids],
                    "confidence": c.confidence,
                    "last_practiced_at": c.last_practiced_at,
                    "help_requests": c.help_requests,
                    "latency_ms_ema": c.latency_ms_ema,
                    "error_streak": c.error_streak,
                    "subject": c.subject,
                    "evidence_count": c.evidence_count,
                    "half_life_days": c.half_life_days,
                }
                for key, c in profile.mastery_by_concept.items()
            },
            "frequent_errors": list(profile.frequent_errors),
            "pace": profile.pace,
            "total_attempts": profile.total_attempts,
            "total_struggle_signals": profile.total_struggle_signals,
            "learning_velocity": profile.learning_velocity,
            "applied_event_ids": list(profile.applied_event_ids),
            "pedagogical_memory": {
                "frequent_misconceptions": list(mem.frequent_misconceptions),
                "successful_examples": list(mem.successful_examples),
                "successful_analogies": list(mem.successful_analogies),
                "preferred_explanation_style": mem.preferred_explanation_style,
                "last_effective_strategies": list(mem.last_effective_strategies),
            },
            "updated_at": profile.updated_at,
            "version": version,
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
        concepts: dict[str, ConceptMastery] = {}
        for key, raw in (doc.get("mastery_by_concept") or {}).items():
            last_practiced = raw.get("last_practiced_at")
            concepts[key] = ConceptMastery(
                concept_key=raw.get("concept_key", key),
                attempts=int(raw.get("attempts", 0)),
                mastery=float(raw.get("mastery", 0.0)),
                last_score_ratio=float(raw.get("last_score_ratio", 0.0)),
                document_ids=[UUID(d) for d in (raw.get("document_ids") or [])],
                confidence=float(raw.get("confidence", 0.0)),
                last_practiced_at=last_practiced,
                help_requests=int(raw.get("help_requests", 0)),
                latency_ms_ema=float(raw.get("latency_ms_ema", 0.0)),
                error_streak=int(raw.get("error_streak", 0)),
                subject=raw.get("subject"),
                evidence_count=int(raw.get("evidence_count", raw.get("attempts", 0))),
                half_life_days=float(raw.get("half_life_days", 14.0)),
            )
        raw_mem = doc.get("pedagogical_memory") or {}
        memory = PedagogicalMemory(
            frequent_misconceptions=list(raw_mem.get("frequent_misconceptions") or []),
            successful_examples=list(raw_mem.get("successful_examples") or []),
            successful_analogies=list(raw_mem.get("successful_analogies") or []),
            preferred_explanation_style=raw_mem.get("preferred_explanation_style", "simple"),
            last_effective_strategies=list(raw_mem.get("last_effective_strategies") or []),
        )
        return StudentProfile(
            student_id=UUID(doc["student_id"]),
            mastery_by_document=mastery,
            mastery_by_concept=concepts,
            frequent_errors=list(doc.get("frequent_errors") or []),
            pace=doc.get("pace", "steady"),
            total_attempts=int(doc.get("total_attempts", 0)),
            total_struggle_signals=int(doc.get("total_struggle_signals", 0)),
            pedagogical_memory=memory,
            learning_velocity=float(doc.get("learning_velocity", 0.0)),
            applied_event_ids=list(doc.get("applied_event_ids") or []),
            updated_at=doc["updated_at"],
            version=int(doc.get("version", 0)),
        )

    async def find_by_student(self, student_id: UUID) -> Optional[StudentProfile]:
        db = await self._get_db()
        doc = await db.student_profiles.find_one({"_id": str(student_id)})
        return self._from_doc(doc) if doc else None

    async def save(self, profile: StudentProfile) -> None:
        db = await self._get_db()
        expected = int(profile.version)
        new_version = expected + 1
        payload = self._to_doc(profile, new_version)
        _id = payload["_id"]
        if expected == 0:
            existing = await db.student_profiles.find_one({"_id": _id}, projection={"version": 1})
            if existing is None:
                await db.student_profiles.insert_one(payload)
            else:
                result = await db.student_profiles.replace_one(
                    {
                        "_id": _id,
                        "$or": [{"version": 0}, {"version": {"$exists": False}}],
                    },
                    payload,
                )
                if result.matched_count == 0:
                    raise ConcurrencyError("StudentProfile concurrent update")
        else:
            result = await db.student_profiles.replace_one(
                {"_id": _id, "version": expected},
                payload,
            )
            if result.matched_count == 0:
                raise ConcurrencyError("StudentProfile concurrent update")
        profile.version = new_version
