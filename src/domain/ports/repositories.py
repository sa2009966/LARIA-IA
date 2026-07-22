from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from src.domain.aggregates.user_aggregate import UserAggregate
from src.domain.aggregates.document_aggregate import DocumentAggregate
from src.domain.aggregates.quiz_aggregate import QuizAggregate
from src.domain.aggregates.quiz_attempt_aggregate import QuizAttemptAggregate
from src.domain.aggregates.student_profile import StudentProfile
from src.domain.aggregates.tutor_interaction import TutorInteractionAggregate
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


class QuizRepository(ABC):
    @abstractmethod
    async def find_by_id(self, quiz_id: UUID) -> Optional[QuizAggregate]:
        ...

    @abstractmethod
    async def find_by_document(self, document_id: UUID) -> list[QuizAggregate]:
        ...

    @abstractmethod
    async def find_by_owner(self, owner_id: UUID) -> list[QuizAggregate]:
        ...

    @abstractmethod
    async def save(self, quiz: QuizAggregate) -> None:
        ...

    @abstractmethod
    async def delete_by_document(self, document_id: UUID) -> int:
        ...


class QuizAttemptRepository(ABC):
    @abstractmethod
    async def find_by_id(self, attempt_id: UUID) -> Optional[QuizAttemptAggregate]:
        ...

    @abstractmethod
    async def find_by_quiz(self, quiz_id: UUID) -> list[QuizAttemptAggregate]:
        ...

    @abstractmethod
    async def find_by_student(self, student_id: UUID) -> list[QuizAttemptAggregate]:
        ...

    @abstractmethod
    async def save(self, attempt: QuizAttemptAggregate) -> None:
        ...

    @abstractmethod
    async def delete_by_document(self, document_id: UUID) -> int:
        ...


class TutorInteractionRepository(ABC):
    @abstractmethod
    async def find_by_id(self, interaction_id: UUID) -> Optional[TutorInteractionAggregate]:
        ...

    @abstractmethod
    async def find_by_student(self, student_id: UUID) -> list[TutorInteractionAggregate]:
        ...

    @abstractmethod
    async def find_by_document(self, document_id: UUID) -> list[TutorInteractionAggregate]:
        ...

    @abstractmethod
    async def save(self, interaction: TutorInteractionAggregate) -> None:
        ...

    @abstractmethod
    async def delete_by_document(self, document_id: UUID) -> int:
        ...


class StudentProfileRepository(ABC):
    @abstractmethod
    async def find_by_student(self, student_id: UUID) -> Optional[StudentProfile]:
        ...

    @abstractmethod
    async def save(self, profile: StudentProfile) -> None:
        ...
