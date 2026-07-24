from typing import Optional
from uuid import UUID

from src.domain.aggregates.document_aggregate import DocumentAggregate
from src.domain.ports.repositories import DocumentRepository


class InMemoryDocumentRepository(DocumentRepository):

    def __init__(self) -> None:
        self._documents: dict[UUID, DocumentAggregate] = {}

    async def find_by_id(self, document_id: UUID) -> Optional[DocumentAggregate]:
        return self._documents.get(document_id)

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
        return doc.content

    async def save(self, document: DocumentAggregate) -> None:
        self._documents[document.id] = document

    async def delete(self, document_id: UUID) -> None:
        self._documents.pop(document_id, None)
