from typing import Optional
from uuid import UUID

from src.domain.aggregates.quiz_attempt_aggregate import QuizAttemptAggregate
from src.domain.ports.repositories import QuizAttemptRepository


class InMemoryQuizAttemptRepository(QuizAttemptRepository):

    def __init__(self) -> None:
        self._attempts: dict[UUID, QuizAttemptAggregate] = {}

    async def find_by_id(self, attempt_id: UUID) -> Optional[QuizAttemptAggregate]:
        return self._attempts.get(attempt_id)

    async def find_by_quiz(self, quiz_id: UUID) -> list[QuizAttemptAggregate]:
        return [a for a in self._attempts.values() if a.quiz_id == quiz_id]

    async def find_by_student(self, student_id: UUID) -> list[QuizAttemptAggregate]:
        return [a for a in self._attempts.values() if a.student_id == student_id]

    async def save(self, attempt: QuizAttemptAggregate) -> None:
        self._attempts[attempt.id] = attempt

    async def delete_by_document(self, document_id: UUID) -> int:
        to_delete = [aid for aid, a in self._attempts.items() if a.document_id == document_id]
        for aid in to_delete:
            del self._attempts[aid]
        return len(to_delete)
