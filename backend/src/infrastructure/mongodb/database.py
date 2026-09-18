from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from src.infrastructure.config import settings

_client: AsyncIOMotorClient | None = None


async def get_database() -> AsyncIOMotorDatabase:
    global _client
    if _client is None:
        # Timeout acotado: evita cuelgues largos si Mongo no está (tests /
        # misconfig). Configurable porque 3 s bastan contra un Mongo local pero
        # se quedan cortos contra Atlas en frío: resolución SRV + TLS + tier
        # compartido pueden pasar de ahí, y el fallo se vería como "no hay BD".
        timeout_ms = max(1_000, int(settings.MONGODB_TIMEOUT_MS))
        _client = AsyncIOMotorClient(
            settings.MONGODB_URL,
            serverSelectionTimeoutMS=timeout_ms,
            connectTimeoutMS=timeout_ms,
        )
    return _client[settings.MONGODB_DB_NAME]


async def close_database() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None