from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from src.domain.value_objects.question import Quiz
from src.domain.value_objects.analysis_result import AnalysisResult
from src.domain.events.domain_events import (
    AnalysisCompletedEvent, AnalysisFailedEvent, DomainEvent,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class AnalysisAggregate:
    id: UUID = field(default_factory=uuid4)
    document_id: UUID = field(default_factory=uuid4)
    result: Optional[AnalysisResult] = None
    quiz: Optional[Quiz] = None
    model_used: str = ""
    created_at: datetime = field(default_factory=_utc_now)
    events: list[DomainEvent] = field(default_factory=list)

    @staticmethod
    def create(document_id: UUID, result: AnalysisResult, model_used: str = "gpt-4o-mini") -> "AnalysisAggregate":
        analysis = AnalysisAggregate(
            document_id=document_id,
            result=result,
            model_used=model_used,
        )
        analysis.events.append(
            AnalysisCompletedEvent(
                aggregate_id=analysis.id,
                document_id=document_id,
                summary_length=len(result.summary),
            )
        )
        return analysis

    @staticmethod
    def create_failed(document_id: UUID, error_message: str) -> "AnalysisAggregate":
        analysis = AnalysisAggregate(
            document_id=document_id,
            model_used="",
        )
        analysis.events.append(
            AnalysisFailedEvent(
                aggregate_id=analysis.id,
                document_id=document_id,
                error_message=error_message,
            )
        )
        return analysis

    def add_quiz(self, quiz: Quiz) -> None:
        self.quiz = quiz

    def has_quiz(self) -> bool:
        return self.quiz is not None

    def clear_events(self) -> None:
        self.events.clear()
