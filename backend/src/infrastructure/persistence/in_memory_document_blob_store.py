from uuid import uuid4

from src.domain.ports.document_blob_store import DocumentBlobStore


class InMemoryDocumentBlobStore(DocumentBlobStore):
    def __init__(self) -> None:
        self._blobs: dict[str, bytes] = {}

    async def put(
        self,
        data: bytes,
        *,
        filename: str = "",
        content_type: str = "text/plain",
    ) -> str:
        blob_id = str(uuid4())
        self._blobs[blob_id] = data
        return blob_id

    async def get(self, blob_id: str) -> bytes:
        if blob_id not in self._blobs:
            raise KeyError(f"Blob no encontrado: {blob_id}")
        return self._blobs[blob_id]

    async def delete(self, blob_id: str) -> None:
        self._blobs.pop(blob_id, None)
