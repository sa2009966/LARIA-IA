from typing import Optional
from uuid import UUID

from src.domain.aggregates.tutor_interaction import TutorInteractionAggregate
from src.domain.ports.repositories import TutorInteractionRepository


class InMemoryTutorInteractionRepository(TutorInteractionRepository):

    def __init__(self) -> None:
        self._interactions: dict[UUID, TutorInteractionAggregate] = {}

    async def find_by_id(self, interaction_id: UUID) -> Optional[TutorInteractionAggregate]:
        return self._interactions.get(interaction_id)

    async def find_by_student(self, student_id: UUID) -> list[TutorInteractionAggregate]:
        return [i for i in self._interactions.values() if i.student_id == student_id]

    async def find_by_document(self, document_id: UUID) -> list[TutorInteractionAggregate]:
        return [i for i in self._interactions.values() if i.document_id == document_id]

    async def save(self, interaction: TutorInteractionAggregate) -> None:
        self._interactions[interaction.id] = interaction
