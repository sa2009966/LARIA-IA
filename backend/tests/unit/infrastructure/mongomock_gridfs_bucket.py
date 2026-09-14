"""GridFS async sobre colecciones mongomock (Motor GridFS no compatible con mongomock)."""
from __future__ import annotations

from io import BytesIO

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase


class MongomockAsyncGridFSBucket:
    """Bucket mínimo compatible con GridFSDocumentBlobStore para tests de integración."""

    def __init__(self, database: AsyncIOMotorDatabase) -> None:
        self._files = database["fs.files"]
        self._chunks = database["fs.chunks"]

    async def upload_from_stream(
        self,
        filename: str,
        stream: BytesIO,
        metadata: dict | None = None,
    ) -> ObjectId:
        data = stream.read()
        file_id = ObjectId()
        await self._files.insert_one(
            {
                "_id": file_id,
                "filename": filename,
                "length": len(data),
                "metadata": metadata or {},
            }
        )
        await self._chunks.insert_one(
            {
                "files_id": file_id,
                "n": 0,
                "data": data,
            }
        )
        return file_id

    async def download_to_stream(self, file_id: ObjectId, stream: BytesIO) -> None:
        doc = await self._files.find_one({"_id": file_id})
        if doc is None:
            raise RuntimeError("missing")
        chunk = await self._chunks.find_one({"files_id": file_id, "n": 0})
        if chunk is None:
            raise RuntimeError("missing")
        stream.write(chunk["data"])

    async def delete(self, file_id: ObjectId) -> None:
        await self._chunks.delete_many({"files_id": file_id})
        result = await self._files.delete_one({"_id": file_id})
        if result.deleted_count == 0:
            raise RuntimeError("missing")
