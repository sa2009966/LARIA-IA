from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DomainEvent:
    aggregate_id: UUID
    timestamp: datetime
    event_type: str


@dataclass(kw_only=True)
class DomainEventBase(DomainEvent):
    aggregate_id: UUID
    timestamp: datetime = field(default_factory=_utc_now)

    @property
    def event_type(self) -> str:
        return type(self).__name__


@dataclass(kw_only=True)
class UserRegisteredEvent(DomainEventBase):
    email: str


@dataclass(kw_only=True)
class UserDeactivatedEvent(DomainEventBase):
    pass


@dataclass(kw_only=True)
class DocumentUploadedEvent(DomainEventBase):
    owner_id: UUID
    filename: str


@dataclass(kw_only=True)
class DocumentDeletedEvent(DomainEventBase):
    owner_id: UUID


@dataclass(kw_only=True)
class AnalysisCompletedEvent(DomainEventBase):
    document_id: UUID
    summary_length: int


@dataclass(kw_only=True)
class AnalysisFailedEvent(DomainEventBase):
    document_id: UUID
    error_message: str


@dataclass(kw_only=True)
class QuizGeneratedEvent(DomainEventBase):
    document_id: UUID
    owner_id: UUID
    num_questions: int


@dataclass(kw_only=True)
class QuizAttemptCompletedEvent(DomainEventBase):
    quiz_id: UUID
    document_id: UUID
    student_id: UUID
    score: int
    total: int


@dataclass(kw_only=True)
class TutorQuestionAskedEvent(DomainEventBase):
    student_id: UUID
    document_id: UUID
    question: str
    answer: str
