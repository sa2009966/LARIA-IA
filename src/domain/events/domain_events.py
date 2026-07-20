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


class EventFactory:
    @staticmethod
    def create_user_registered(user_id: UUID, email: str) -> UserRegisteredEvent:
        return UserRegisteredEvent(aggregate_id=user_id, email=email)

    @staticmethod
    def create_document_uploaded(document_id: UUID, owner_id: UUID, filename: str) -> DocumentUploadedEvent:
        return DocumentUploadedEvent(
            aggregate_id=document_id, owner_id=owner_id, filename=filename
        )

    @staticmethod
    def create_analysis_completed(analysis_id: UUID, document_id: UUID, summary_length: int) -> AnalysisCompletedEvent:
        return AnalysisCompletedEvent(
            aggregate_id=analysis_id, document_id=document_id, summary_length=summary_length
        )
