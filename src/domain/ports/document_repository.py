from abc import ABC, abstractmethod
from typing import Optional

from src.domain.entities.document import Document


class DocumentRepository(ABC):
    """Puerto de salida: contrato para la persistencia de documentos."""

    @abstractmethod
    def find_by_id(self, document_id: int) -> Optional[Document]:
        ...

    @abstractmethod
    def find_by_owner(self, owner_id: int) -> list[Document]:
        ...

    @abstractmethod
    def save(self, document: Document) -> Document:
        ...

    @abstractmethod
    def delete(self, document_id: int) -> None:
        ...
