from typing import Optional
from uuid import UUID

from motor.motor_asyncio import AsyncIOMotorDatabase

from src.domain.aggregates.user_aggregate import UserAggregate, UserRole
from src.domain.ports.repositories import UserRepository
from src.domain.value_objects.email import Email
from src.infrastructure.mongodb.database import get_database


class MongoDBUserRepository(UserRepository):

    def __init__(self, database: Optional[AsyncIOMotorDatabase] = None) -> None:
        self._database = database

    async def _get_db(self) -> AsyncIOMotorDatabase:
        if self._database is None:
            self._database = await get_database()
        return self._database

    @staticmethod
    def _to_doc(user: UserAggregate) -> dict:
        return {
            "_id": str(user.id),
            "username": user.username,
            "email": user.email.value,
            "hashed_password": user.hashed_password,
            "role": user.role.value,
            "is_active": user.is_active,
            "created_at": user.created_at,
        }

    @staticmethod
    def _from_doc(doc: dict) -> UserAggregate:
        user = UserAggregate(
            id=UUID(doc["_id"]),
            username=doc["username"],
            email=Email(doc["email"]),
            hashed_password=doc["hashed_password"],
            # Compatibilidad: "teacher" legado se trata como estudiante.
            role=UserRole.STUDENT if doc.get("role") == "teacher" else UserRole(doc["role"]),
            is_active=doc["is_active"],
            created_at=doc["created_at"],
        )
        return user

    async def find_by_id(self, user_id: UUID) -> Optional[UserAggregate]:
        db = await self._get_db()
        doc = await db.users.find_one({"_id": str(user_id)})
        return self._from_doc(doc) if doc else None

    async def find_by_email(self, email: Email) -> Optional[UserAggregate]:
        db = await self._get_db()
        doc = await db.users.find_one({"email": email.value})
        return self._from_doc(doc) if doc else None

    async def find_by_username(self, username: str) -> Optional[UserAggregate]:
        db = await self._get_db()
        doc = await db.users.find_one({"username": username})
        return self._from_doc(doc) if doc else None

    async def save(self, user: UserAggregate) -> None:
        db = await self._get_db()
        doc = self._to_doc(user)
        await db.users.replace_one({"_id": doc["_id"]}, doc, upsert=True)

    async def ensure_indexes(self) -> None:
        db = await self._get_db()
        await db.users.create_index("email", unique=True)
        await db.users.create_index("username", unique=True)

    async def delete(self, user_id: UUID) -> None:
        db = await self._get_db()
        await db.users.delete_one({"_id": str(user_id)})

    async def list_all(self) -> list[UserAggregate]:
        db = await self._get_db()
        cursor = db.users.find()
        return [self._from_doc(doc) async for doc in cursor]