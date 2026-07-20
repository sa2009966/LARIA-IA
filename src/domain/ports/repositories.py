from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from src.domain.aggregates.user_aggregate import UserAggregate
from src.domain.aggregates.document_aggregate import DocumentAggregate
from src.domain.aggregates.analysis_aggregate import AnalysisAggregate
from src.domain.value_objects.email import Email


class UserRepository(ABC):
    @abstractmethod
    async def find_by_id(self, user_id: UUID) -> Optional[UserAggregate]:
        ...

    @abstractmethod
    async def find_by_email(self, email: Email) -> Optional[UserAggregate]:
        ...

    @abstractmethod
    async def find_by_username(self, username: str) -> Optional[UserAggregate]:
        ...

    @abstractmethod
    async def save(self, user: UserAggregate) -> None:
        ...

    @abstractmethod
    async def delete(self, user_id: UUID) -> None:
        ...

    @abstractmethod
    async def list_all(self) -> list[UserAggregate]:
        ...


class DocumentRepository(ABC):
    @abstractmethod
    async def find_by_id(self, document_id: UUID) -> Optional[DocumentAggregate]:
        ...

    @abstractmethod
    async def find_by_owner(self, owner_id: UUID) -> list[DocumentAggregate]:
        ...

    @abstractmethod
    async def save(self, document: DocumentAggregate) -> None:
        ...

    @abstractmethod
    async def delete(self, document_id: UUID) -> None:
        ...


class AnalysisRepository(ABC):
    @abstractmethod
    async def save(self, analysis: AnalysisAggregate) -> None:
        ...

    @abstractmethod
    async def find_by_document(self, document_id: UUID) -> Optional[AnalysisAggregate]:
        ...
