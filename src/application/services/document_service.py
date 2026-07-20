from uuid import UUID
from typing import Optional

from src.domain.aggregates.document_aggregate import DocumentAggregate
from src.domain.ports.repositories import DocumentRepository
from src.domain.ports.event_bus import EventBus
from src.application.dto.document_dto import DocumentDTO, UploadDocumentDTO, DocumentListDTO


class DocumentService:
    def __init__(self, document_repository: DocumentRepository, event_bus: Optional[EventBus] = None) -> None:
        self._doc_repo = document_repository
        self._event_bus = event_bus

    async def upload(self, owner_id: UUID, dto: UploadDocumentDTO) -> DocumentDTO:
        doc = DocumentAggregate.upload(owner_id, dto.filename, dto.content, dto.subject)
        await self._doc_repo.save(doc)

        if self._event_bus:
            for event in doc.events:
                await self._event_bus.publish(event)
        doc.clear_events()

        return self._to_dto(doc)

    async def get_by_id(self, document_id: UUID, requesting_user_id: UUID) -> DocumentDTO:
        doc = await self._doc_repo.find_by_id(document_id)
        if doc is None:
            raise ValueError(f"Documento con id={document_id} no encontrado")
        if not doc.is_owned_by(requesting_user_id):
            raise PermissionError("No tienes permiso para ver este documento")
        return self._to_dto(doc)

    async def list_by_owner(self, owner_id: UUID) -> DocumentListDTO:
        docs = await self._doc_repo.find_by_owner(owner_id)
        return DocumentListDTO(
            documents=[self._to_dto(d) for d in docs],
            total=len(docs),
        )

    async def delete(self, document_id: UUID, requesting_user_id: UUID) -> None:
        doc = await self._doc_repo.find_by_id(document_id)
        if doc is None:
            raise ValueError(f"Documento con id={document_id} no encontrado")
        if not doc.is_owned_by(requesting_user_id):
            raise PermissionError("No tienes permiso para eliminar este documento")
        await self._doc_repo.delete(document_id)

    def _to_dto(self, doc: DocumentAggregate) -> DocumentDTO:
        return DocumentDTO(
            id=doc.id,
            owner_id=doc.owner_id,
            filename=doc.filename,
            subject=doc.subject.value,
            status=doc.status.value,
            uploaded_at=doc.uploaded_at,
            has_analysis=doc.has_analysis(),
            error_message=doc.error_message,
        )
