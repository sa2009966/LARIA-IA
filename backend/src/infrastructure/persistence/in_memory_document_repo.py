from typing import Optional
from uuid import UUID

from src.domain.aggregates.document_aggregate import DocumentAggregate
from src.domain.ports.document_blob_store import DocumentBlobStore
from src.domain.ports.repositories import DocumentRepository


class InMemoryDocumentRepository(DocumentRepository):

    def __init__(self, blob_store: Optional[DocumentBlobStore] = None) -> None:
        self._documents: dict[UUID, DocumentAggregate] = {}
        self._blob_store = blob_store

    async def find_by_id(self, document_id: UUID) -> Optional[DocumentAggregate]:
        doc = self._documents.get(document_id)
        if doc is None:
            return None
        # Copia ligera sin cuerpo (hidratación vía get_content).
        light = DocumentAggregate(
            id=doc.id,
            owner_id=doc.owner_id,
            filename=doc.filename,
            content="",
            content_blob_id=doc.content_blob_id,
            subject=doc.subject,
            status=doc.status,
            uploaded_at=doc.uploaded_at,
            error_message=doc.error_message,
        )
        light.analysis_result = doc.analysis_result
        return light

    async def find_by_owner(self, owner_id: UUID) -> list[DocumentAggregate]:
        result: list[DocumentAggregate] = []
        for d in self._documents.values():
            if d.owner_id != owner_id:
                continue
            light = DocumentAggregate(
                id=d.id,
                owner_id=d.owner_id,
                filename=d.filename,
                content="",
                content_blob_id=d.content_blob_id,
                subject=d.subject,
                status=d.status,
                uploaded_at=d.uploaded_at,
                error_message=d.error_message,
            )
            light.analysis_result = d.analysis_result
            result.append(light)
        return result

    async def get_content(self, document_id: UUID) -> Optional[str]:
        doc = self._documents.get(document_id)
        if doc is None:
            return None
        if doc.content_blob_id and self._blob_store is not None:
            try:
                raw = await self._blob_store.get(doc.content_blob_id)
            except KeyError:
                return ""
            return raw.decode("utf-8", errors="replace")
        return doc.content

    async def save(self, document: DocumentAggregate) -> None:
        # Persistir sin cuerpo inline si hay blob (espejo de Mongo).
        stored = DocumentAggregate(
            id=document.id,
            owner_id=document.owner_id,
            filename=document.filename,
            content="" if document.content_blob_id else document.content,
            content_blob_id=document.content_blob_id,
            subject=document.subject,
            status=document.status,
            uploaded_at=document.uploaded_at,
            error_message=document.error_message,
        )
        stored.analysis_result = document.analysis_result
        self._documents[document.id] = stored

    async def delete(self, document_id: UUID) -> None:
        doc = self._documents.pop(document_id, None)
        if doc and doc.content_blob_id and self._blob_store is not None:
            await self._blob_store.delete(doc.content_blob_id)
