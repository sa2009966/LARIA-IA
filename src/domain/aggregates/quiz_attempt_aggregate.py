from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4

from src.domain.aggregates.quiz_aggregate import QuizGrade
from src.domain.events.domain_events import DomainEvent, QuizAttemptCompletedEvent


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class QuizAttemptAggregate:
    id: UUID = field(default_factory=uuid4)
    quiz_id: UUID = field(default_factory=uuid4)
    document_id: UUID = field(default_factory=uuid4)
    student_id: UUID = field(default_factory=uuid4)
    answers: dict[int, str] = field(default_factory=dict)
    per_question_correct: list[bool] = field(default_factory=list)
    score: int = 0
    total_points: int = 0
    completed_at: datetime = field(default_factory=_utc_now)
    events: list[DomainEvent] = field(default_factory=list)

    @staticmethod
    def create(
        quiz_id: UUID,
        document_id: UUID,
        student_id: UUID,
        answers: dict[int, str],
        grade: QuizGrade,
    ) -> "QuizAttemptAggregate":
        attempt = QuizAttemptAggregate(
            quiz_id=quiz_id,
            document_id=document_id,
            student_id=student_id,
            answers=dict(answers),
            per_question_correct=list(grade.per_question_correct),
            score=grade.score,
            total_points=grade.total_points,
        )
        attempt.events.append(
            QuizAttemptCompletedEvent(
                aggregate_id=attempt.id,
                quiz_id=quiz_id,
                document_id=document_id,
                student_id=student_id,
                score=grade.score,
                total=grade.total_points,
            )
        )
        return attempt

    def clear_events(self) -> None:
        self.events.clear()
