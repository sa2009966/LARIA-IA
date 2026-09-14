import pytest

from src.infrastructure.persistence.in_memory_document_blob_store import (
    InMemoryDocumentBlobStore,
)


@pytest.mark.asyncio
async def test_in_memory_blob_put_get_delete():
    store = InMemoryDocumentBlobStore()
    blob_id = await store.put(b"hola", filename="a.txt")
    assert await store.get(blob_id) == b"hola"
    await store.delete(blob_id)
    with pytest.raises(KeyError):
        await store.get(blob_id)
