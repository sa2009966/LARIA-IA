from copy import deepcopy
from typing import Optional
from uuid import UUID

from src.domain.aggregates.learning_path import LearningPathAggregate
from src.domain.ports.repositories import LearningPathRepository


class InMemoryLearningPathRepository(LearningPathRepository):

    def __init__(self) -> None:
        self._paths: dict[UUID, LearningPathAggregate] = {}

    async def find_by_id(self, path_id: UUID) -> Optional[LearningPathAggregate]:
        p = self._paths.get(path_id)
        return deepcopy(p) if p else None

    async def find_by_owner(self, owner_id: UUID) -> list[LearningPathAggregate]:
        paths = [deepcopy(p) for p in self._paths.values() if p.owner_id == owner_id]
        paths.sort(key=lambda p: p.updated_at, reverse=True)
        return paths

    async def save(self, path: LearningPathAggregate) -> None:
        self._paths[path.id] = deepcopy(path)

    async def delete(self, path_id: UUID) -> None:
        self._paths.pop(path_id, None)
