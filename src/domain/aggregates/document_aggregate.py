from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from src.domain.value_objects.subject import Subject
from src.domain.value_objects.analysis_result import AnalysisResult
from src.domain.events.domain_events import (
    DocumentUploadedEvent, DocumentDeletedEvent,
    AnalysisCompletedEvent, AnalysisFailedEvent, DomainEvent,
)


class DocumentStatus(Enum):
    UPLOADED = "uploaded"
    ANALYZING = "analyzing"
    ANALYZED = "analyzed"
    ERROR = "error"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class DocumentAggregate:
    id: UUID = field(default_factory=uuid4)
    owner_id: UUID = field(default_factory=uuid4)
    filename: str = ""
    content: str = ""
    subject: Subject = field(default_factory=lambda: Subject("Matemática"))
    status: DocumentStatus = DocumentStatus.UPLOADED
    uploaded_at: datetime = field(default_factory=_utc_now)
    analysis_result: Optional[AnalysisResult] = None
    error_message: Optional[str] = None
    events: list[DomainEvent] = field(default_factory=list)

    @staticmethod
    def upload(owner_id: UUID, filename: str, content: str, subject: str) -> "DocumentAggregate":
        doc = DocumentAggregate(
            owner_id=owner_id,
            filename=filename,
            content=content,
            subject=Subject(subject),
            status=DocumentStatus.UPLOADED,
        )
        doc.events.append(
            DocumentUploadedEvent(
                aggregate_id=doc.id,
                owner_id=owner_id,
                filename=filename,
            )
        )
        return doc

    def mark_analyzing(self) -> None:
        if self.status == DocumentStatus.ANALYZED:
            raise ValueError("Document already analyzed")
        if self.status == DocumentStatus.ANALYZING:
            raise ValueError("Document is already being analyzed")
        self.status = DocumentStatus.ANALYZING

    def complete_analysis(self, result: AnalysisResult) -> None:
        self.analysis_result = result
        self.status = DocumentStatus.ANALYZED
        self.error_message = None
        self.events.append(
            AnalysisCompletedEvent(
                aggregate_id=self.id,
                document_id=self.id,
                summary_length=len(result.summary),
            )
        )

    def reset_for_reanalysis(self) -> None:
        """Vuelve al estado UPLOADED para reintentar un análisis interrumpido, fallido o forzado."""
        self.status = DocumentStatus.UPLOADED
        self.analysis_result = None
        self.error_message = None

    def mark_error(self, error_msg: str) -> None:
        self.status = DocumentStatus.ERROR
        self.error_message = error_msg
        self.events.append(
            AnalysisFailedEvent(
                aggregate_id=self.id,
                document_id=self.id,
                error_message=error_msg,
            )
        )

    def mark_deleted(self) -> None:
        self.events.append(
            DocumentDeletedEvent(aggregate_id=self.id, owner_id=self.owner_id)
        )

    def has_analysis(self) -> bool:
        return self.analysis_result is not None

    def is_owned_by(self, user_id: UUID) -> bool:
        return self.owner_id == user_id

    def clear_events(self) -> None:
        self.events.clear()
