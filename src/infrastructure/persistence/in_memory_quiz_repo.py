from typing import Optional
from uuid import UUID

from src.domain.aggregates.quiz_aggregate import QuizAggregate
from src.domain.ports.repositories import QuizRepository


class InMemoryQuizRepository(QuizRepository):

    def __init__(self) -> None:
        self._quizzes: dict[UUID, QuizAggregate] = {}

    async def find_by_id(self, quiz_id: UUID) -> Optional[QuizAggregate]:
        return self._quizzes.get(quiz_id)

    async def find_by_document(self, document_id: UUID) -> list[QuizAggregate]:
        return [q for q in self._quizzes.values() if q.document_id == document_id]

    async def find_by_owner(self, owner_id: UUID) -> list[QuizAggregate]:
        return [q for q in self._quizzes.values() if q.owner_id == owner_id]

    async def save(self, quiz: QuizAggregate) -> None:
        self._quizzes[quiz.id] = quiz
