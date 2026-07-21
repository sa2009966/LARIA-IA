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
        return [d for d in self._documents.values() if d.owner_id == owner_id]

    async def save(self, document: DocumentAggregate) -> None:
        self._documents[document.id] = document

    async def delete(self, document_id: UUID) -> None:
        self._documents.pop(document_id, None)