from uuid import UUID
from typing import Optional

from src.application.concurrency import with_concurrency_retry
from src.application.dto.document_dto import DocumentDTO, UploadDocumentDTO, DocumentListDTO
from src.domain.aggregates.document_aggregate import DocumentAggregate
from src.domain.ports.document_blob_store import DocumentBlobStore
from src.domain.ports.event_bus import EventBus
from src.domain.ports.repositories import (
    DocumentRepository,
    QuizAttemptRepository,
    QuizRepository,
    StudentProfileRepository,
    TutorInteractionRepository,
    TutorSessionRepository,
)

# Default alineado a Settings.DOCUMENT_MAX_UPLOAD_BYTES (inyectado desde DI).
_DEFAULT_MAX_UPLOAD_BYTES = 209_715_200


class DocumentTooLargeError(ValueError):
    """El material supera DOCUMENT_MAX_UPLOAD_BYTES."""


class DocumentService:
    def __init__(
        self,
        document_repository: DocumentRepository,
        event_bus: Optional[EventBus] = None,
        quiz_repository: Optional[QuizRepository] = None,
        attempt_repository: Optional[QuizAttemptRepository] = None,
        interaction_repository: Optional[TutorInteractionRepository] = None,
        profile_repository: Optional[StudentProfileRepository] = None,
        session_repository: Optional[TutorSessionRepository] = None,
        blob_store: Optional[DocumentBlobStore] = None,
        max_upload_bytes: int = _DEFAULT_MAX_UPLOAD_BYTES,
    ) -> None:
        self._doc_repo = document_repository
        self._event_bus = event_bus
        self._quiz_repo = quiz_repository
        self._attempt_repo = attempt_repository
        self._interaction_repo = interaction_repository
        self._profile_repo = profile_repository
        self._session_repo = session_repository
        self._blob_store = blob_store
        self._max_upload_bytes = int(max_upload_bytes)

    def _assert_size(self, raw: bytes) -> None:
        max_bytes = self._max_upload_bytes
        if len(raw) > max_bytes:
            raise DocumentTooLargeError(
                f"El archivo supera el límite de {max_bytes} bytes "
                f"(DOCUMENT_MAX_UPLOAD_BYTES)."
            )

    async def upload(self, owner_id: UUID, dto: UploadDocumentDTO) -> DocumentDTO:
        raw = dto.content.encode("utf-8")
        return await self._persist_upload(
            owner_id,
            filename=dto.filename,
            text=dto.content,
            subject=dto.subject,
            raw=raw,
        )

    async def upload_bytes(
        self,
        owner_id: UUID,
        *,
        filename: str,
        data: bytes,
        subject: str,
    ) -> DocumentDTO:
        self._assert_size(data)
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(
                "Solo se admiten archivos de texto UTF-8 (.txt, .md) en esta fase."
            ) from exc
        return await self._persist_upload(
            owner_id,
            filename=filename,
            text=text,
            subject=subject,
            raw=data,
        )

    async def _persist_upload(
        self,
        owner_id: UUID,
        *,
        filename: str,
        text: str,
        subject: str,
        raw: bytes,
    ) -> DocumentDTO:
        self._assert_size(raw)

        blob_id: Optional[str] = None
        if self._blob_store is not None:
            blob_id = await self._blob_store.put(
                raw,
                filename=filename,
                content_type="text/plain; charset=utf-8",
            )

        doc = DocumentAggregate.upload(
            owner_id,
            filename,
            content=text if blob_id is None else "",
            subject=subject,
            content_blob_id=blob_id,
        )
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

        if self._attempt_repo is not None:
            await self._attempt_repo.delete_by_document(document_id)
        if self._quiz_repo is not None:
            await self._quiz_repo.delete_by_document(document_id)
        if self._interaction_repo is not None:
            await self._interaction_repo.delete_by_document(document_id)
        if self._profile_repo is not None:

            async def _clear_profile():
                profile = await self._profile_repo.find_by_student(requesting_user_id)
                if profile is None:
                    return None
                profile.clear_document(document_id)
                await self._profile_repo.save(profile)
                return profile

            await with_concurrency_retry(_clear_profile)
        if self._session_repo is not None:
            await self._session_repo.delete_by_document(document_id)

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
