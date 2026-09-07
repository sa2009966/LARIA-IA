from io import BytesIO
from typing import Optional

from bson import ObjectId
from bson.errors import InvalidId
from motor.motor_asyncio import AsyncIOMotorDatabase, AsyncIOMotorGridFSBucket

from src.domain.ports.document_blob_store import DocumentBlobStore
from src.infrastructure.mongodb.database import get_database


class GridFSDocumentBlobStore(DocumentBlobStore):
    def __init__(self, database: Optional[AsyncIOMotorDatabase] = None) -> None:
        self._database = database

    async def _bucket(self) -> AsyncIOMotorGridFSBucket:
        if self._database is None:
            self._database = await get_database()
        return AsyncIOMotorGridFSBucket(self._database)

    async def put(
        self,
        data: bytes,
        *,
        filename: str = "",
        content_type: str = "text/plain",
    ) -> str:
        bucket = await self._bucket()
        file_id = await bucket.upload_from_stream(
            filename or "document.txt",
            BytesIO(data),
            metadata={"content_type": content_type},
        )
        return str(file_id)

    async def get(self, blob_id: str) -> bytes:
        bucket = await self._bucket()
        try:
            oid = ObjectId(blob_id)
        except (InvalidId, TypeError) as exc:
            raise KeyError(f"Blob no encontrado: {blob_id}") from exc
        buf = BytesIO()
        try:
            await bucket.download_to_stream(oid, buf)
        except Exception as exc:
            raise KeyError(f"Blob no encontrado: {blob_id}") from exc
        return buf.getvalue()

    async def delete(self, blob_id: str) -> None:
        bucket = await self._bucket()
        try:
            oid = ObjectId(blob_id)
        except (InvalidId, TypeError):
            return
        try:
            await bucket.delete(oid)
        except Exception:
            return
