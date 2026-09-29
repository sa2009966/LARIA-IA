import logging
from uuid import UUID
from typing import Optional

from src.application.concurrency import with_concurrency_retry
from src.application.dto.document_dto import DocumentDTO, UploadDocumentDTO, DocumentListDTO
from src.application.file_parser import content_type_for, is_supported, parse_file
from dataclasses import dataclass
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


logger = logging.getLogger("laria.http")


class DocumentTooLargeError(ValueError):
    """El material supera DOCUMENT_MAX_UPLOAD_BYTES."""


class UnsupportedFileError(ValueError):
    """El formato del archivo no está soportado o no se pudo extraer texto."""

    # Re-exportamos UnsupportedFormatError para no acoplar el router a file_parser.
    pass


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
        original_blob_store: Optional[DocumentBlobStore] = None,
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
        # Por defecto, el original vive donde el texto. Cuando haya un almacén
        # de objetos (R2), solo cambia este colaborador.
        self._original_store = original_blob_store or blob_store
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
        if not is_supported(filename):
            raise UnsupportedFileError(
                "Solo se admiten archivos de texto, PDF, DOCX, XLSX, PPTX o código."
            )
        try:
            text = parse_file(filename, data)
        except Exception as exc:
            raise UnsupportedFileError(str(exc)) from exc
        if not text or not text.strip():
            raise UnsupportedFileError("No se pudo extraer texto del archivo.")
        return await self._persist_upload(
            owner_id,
            filename=filename,
            text=text,
            subject=subject,
            raw=data,
            keep_original=True,
        )

    async def _persist_upload(
        self,
        owner_id: UUID,
        *,
        filename: str,
        text: str,
        subject: str,
        raw: bytes,
        keep_original: bool = False,
    ) -> DocumentDTO:
        self._assert_size(raw)

        # El blob de contenido guarda el TEXTO EXTRAÍDO, que es lo que leen el
        # análisis, el tutor y los quizzes. Aquí se guardaba `raw` y se tiraba
        # el texto, así que un PDF llegaba al motor decodificado como UTF-8
        # (ADR-012).
        blob_id: Optional[str] = None
        if self._blob_store is not None:
            blob_id = await self._blob_store.put(
                text.encode("utf-8"),
                filename=filename,
                content_type="text/plain; charset=utf-8",
            )

        # El archivo original se guarda aparte, con su tipo real, para
        # previsualizarlo y descargarlo. Puede vivir en otro almacén (R2).
        original_blob_id: Optional[str] = None
        original_type: Optional[str] = None
        if keep_original and self._original_store is not None:
            original_type = content_type_for(filename)
            original_blob_id = await self._original_store.put(
                raw,
                filename=filename,
                content_type=original_type,
            )

        doc = DocumentAggregate.upload(
            owner_id,
            filename,
            content=text if blob_id is None else "",
            subject=subject,
            content_blob_id=blob_id,
            original_blob_id=original_blob_id,
            original_content_type=original_type,
            original_size=len(raw) if original_blob_id else None,
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

    async def get_original(
        self, document_id: UUID, requesting_user_id: UUID
    ) -> "OriginalFile":
        """El archivo tal como se subió, para previsualizarlo o descargarlo.

        Tres orígenes, en orden:

        1. **El original**, en su almacén (R2 en producción, ADR-012).
        2. **El almacén de texto con el mismo id**, si el original no aparece:
           los documentos subidos antes de pasar a R2 guardaron el original en
           GridFS, y su id no existe en R2. Sin este paso, todo lo anterior al
           cambio de almacén daría 404.
        3. **El texto extraído**, como `text/plain`, si nunca hubo original: los
           documentos anteriores al ADR-012 y los creados enviando texto. El visor
           muestra algo legible en vez de un error.
        """
        doc = await self._doc_repo.find_by_id(document_id)
        if doc is None:
            raise ValueError("Documento no encontrado")
        if not doc.is_owned_by(requesting_user_id):
            raise PermissionError("Documento no encontrado")

        if doc.original_blob_id:
            for almacen in (self._original_store, self._blob_store):
                if almacen is None:
                    continue
                try:
                    datos = await almacen.get(doc.original_blob_id)
                except KeyError:
                    continue
                return OriginalFile(
                    data=datos,
                    content_type=doc.original_content_type or content_type_for(doc.filename),
                    filename=doc.filename,
                )
            logger.warning(
                "original_no_encontrado document=%s blob=%s",
                doc.id,
                doc.original_blob_id,
            )

        texto = doc.content or await self._doc_repo.get_content(document_id)
        if not texto:
            raise ValueError("Documento no encontrado")
        return OriginalFile(
            data=texto.encode("utf-8"),
            content_type="text/plain; charset=utf-8",
            filename=doc.filename,
        )

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

        # El repositorio borra el blob de texto; el original puede estar en otro
        # almacén, así que lo limpia quien lo escribió. Best-effort: un huérfano
        # en el bucket no puede impedir que el estudiante borre su material.
        if doc.original_blob_id and self._original_store is not None:
            try:
                await self._original_store.delete(doc.original_blob_id)
            except Exception:  # noqa: BLE001
                logger.warning(
                    "original_blob_delete_failed document=%s blob=%s",
                    document_id,
                    doc.original_blob_id,
                )

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


@dataclass(frozen=True)
class OriginalFile:
    """Bytes de un documento y cómo servirlos."""

    data: bytes
    content_type: str
    filename: str
