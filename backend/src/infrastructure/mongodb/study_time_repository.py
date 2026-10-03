from datetime import date
from typing import Optional
from uuid import UUID

from motor.motor_asyncio import AsyncIOMotorDatabase

from src.domain.aggregates.study_time import StudyDay
from src.domain.ports.repositories import StudyTimeRepository
from src.infrastructure.mongodb.database import get_database


class MongoDBStudyTimeRepository(StudyTimeRepository):
    def __init__(self, database: Optional[AsyncIOMotorDatabase] = None) -> None:
        self._database = database

    async def _get_db(self) -> AsyncIOMotorDatabase:
        if self._database is None:
            self._database = await get_database()
        return self._database

    @staticmethod
    def _id(student_id: UUID, day: date) -> str:
        return f"{student_id}:{day.isoformat()}"

    @staticmethod
    def _from_doc(d: dict) -> StudyDay:
        return StudyDay(
            student_id=UUID(d["student_id"]),
            day=date.fromisoformat(d["day"]),
            seconds=int(d.get("seconds", 0)),
            last_ping_at=d.get("last_ping_at"),
        )

    async def get_day(self, student_id: UUID, day: date) -> Optional[StudyDay]:
        db = await self._get_db()
        d = await db.study_time.find_one({"_id": self._id(student_id, day)})
        return self._from_doc(d) if d else None

    async def save_day(self, entry: StudyDay) -> None:
        db = await self._get_db()
        await db.study_time.replace_one(
            {"_id": self._id(entry.student_id, entry.day)},
            {
                "_id": self._id(entry.student_id, entry.day),
                "student_id": str(entry.student_id),
                "day": entry.day.isoformat(),
                "seconds": entry.seconds,
                "last_ping_at": entry.last_ping_at,
            },
            upsert=True,
        )

    async def days_since(self, student_id: UUID, since: date) -> list[StudyDay]:
        db = await self._get_db()
        cursor = db.study_time.find(
            {"student_id": str(student_id), "day": {"$gte": since.isoformat()}}
        ).sort("day", 1)
        return [self._from_doc(d) async for d in cursor]

    async def delete_by_student(self, student_id: UUID) -> int:
        db = await self._get_db()
        r = await db.study_time.delete_many({"student_id": str(student_id)})
        return int(r.deleted_count)
