from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from src.infrastructure.config import settings

_client: AsyncIOMotorClient | None = None


async def get_database() -> AsyncIOMotorDatabase:
    global _client
    if _client is None:
        # Timeout corto: evita cuelgues largos si Mongo no está (tests / misconfig).
        _client = AsyncIOMotorClient(
            settings.MONGODB_URL,
            serverSelectionTimeoutMS=3_000,
            connectTimeoutMS=3_000,
        )
    return _client[settings.MONGODB_DB_NAME]


async def close_database() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None