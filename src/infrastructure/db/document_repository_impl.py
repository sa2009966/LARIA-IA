from typing import Optional

from sqlalchemy.orm import Session

from src.domain.entities.document import Document
from src.domain.ports.document_repository import DocumentRepository
from src.infrastructure.db.models import DocumentModel


class SQLAlchemyDocumentRepository(DocumentRepository):
    """Adaptador: implementa DocumentRepository usando SQLAlchemy + MySQL."""

    def __init__(self, session: Session) -> None:
        self._session = session

    @staticmethod
    def _to_entity(model: DocumentModel) -> Document:
        return Document(
            id=model.id,
            owner_id=model.owner_id,
            filename=model.filename,
            content=model.content,
            subject=model.subject,
            uploaded_at=model.uploaded_at,
            analysis_result=model.analysis_result,
        )

    @staticmethod
    def _to_model(doc: Document) -> DocumentModel:
        return DocumentModel(
            id=doc.id,
            owner_id=doc.owner_id,
            filename=doc.filename,
            content=doc.content,
            subject=doc.subject,
            uploaded_at=doc.uploaded_at,
            analysis_result=doc.analysis_result,
        )

    def find_by_id(self, document_id: int) -> Optional[Document]:
        model = self._session.get(DocumentModel, document_id)
        return self._to_entity(model) if model else None

    def find_by_owner(self, owner_id: int) -> list[Document]:
        models = self._session.query(DocumentModel).filter_by(owner_id=owner_id).all()
        return [self._to_entity(m) for m in models]

    def save(self, document: Document) -> Document:
        if document.id is None:
            model = self._to_model(document)
            self._session.add(model)
        else:
            model = self._session.get(DocumentModel, document.id)
            if model is None:
                raise ValueError(f"Documento con id={document.id} no encontrado en BD.")
            model.filename = document.filename
            model.content = document.content
            model.subject = document.subject
            model.analysis_result = document.analysis_result

        self._session.commit()
        self._session.refresh(model)
        return self._to_entity(model)

    def delete(self, document_id: int) -> None:
        model = self._session.get(DocumentModel, document_id)
        if model:
            self._session.delete(model)
            self._session.commit()
