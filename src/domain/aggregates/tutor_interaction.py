from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4

from src.domain.events.domain_events import DomainEvent


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class TutorInteractionAggregate:
    """Evidencia cruda de una pregunta del estudiante al tutor sobre un documento."""

    id: UUID = field(default_factory=uuid4)
    student_id: UUID = field(default_factory=uuid4)
    document_id: UUID = field(default_factory=uuid4)
    question: str = ""
    answer: str = ""
    asked_at: datetime = field(default_factory=_utc_now)
    events: list[DomainEvent] = field(default_factory=list)

    @staticmethod
    def create(
        student_id: UUID,
        document_id: UUID,
        question: str,
        answer: str,
    ) -> "TutorInteractionAggregate":
        if not question or not question.strip():
            raise ValueError("La pregunta no puede estar vacía")
        if not answer or not answer.strip():
            raise ValueError("La respuesta del tutor no puede estar vacía")
        return TutorInteractionAggregate(
            student_id=student_id,
            document_id=document_id,
            question=question.strip(),
            answer=answer.strip(),
        )

    def clear_events(self) -> None:
        self.events.clear()
