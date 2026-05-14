from src.domain.entities.document import Document
from src.domain.ports.document_repository import DocumentRepository


class DocumentService:
    """Caso de uso: gestión de documentos educativos."""

    def __init__(self, document_repository: DocumentRepository) -> None:
        self._document_repo = document_repository

    def upload(self, owner_id: int, filename: str, content: str, subject: str) -> Document:
        doc = Document(
            id=None,
            owner_id=owner_id,
            filename=filename,
            content=content,
            subject=subject,
        )
        return self._document_repo.save(doc)

    def get_by_id(self, document_id: int) -> Document:
        doc = self._document_repo.find_by_id(document_id)
        if doc is None:
            raise ValueError(f"Documento con id={document_id} no encontrado.")
        return doc

    def list_by_owner(self, owner_id: int) -> list[Document]:
        return self._document_repo.find_by_owner(owner_id)

    def delete(self, document_id: int, requesting_user_id: int) -> None:
        doc = self.get_by_id(document_id)
        if doc.owner_id != requesting_user_id:
            raise PermissionError("No tienes permiso para eliminar este documento.")
        self._document_repo.delete(document_id)
