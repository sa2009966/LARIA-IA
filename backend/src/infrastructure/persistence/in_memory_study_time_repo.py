from copy import deepcopy
from typing import Optional
from uuid import UUID

from src.domain.aggregates.study_time import StudyDay
from src.domain.ports.repositories import StudyTimeRepository


class InMemoryStudyTimeRepository(StudyTimeRepository):
    def __init__(self) -> None:
        self._dias: dict[tuple, StudyDay] = {}

    async def get_day(self, student_id: UUID, day) -> Optional[StudyDay]:
        d = self._dias.get((student_id, day))
        return deepcopy(d) if d else None

    async def save_day(self, entry: StudyDay) -> None:
        self._dias[(entry.student_id, entry.day)] = deepcopy(entry)

    async def days_since(self, student_id: UUID, since) -> list[StudyDay]:
        return sorted(
            (deepcopy(d) for (s, dia), d in self._dias.items() if s == student_id and dia >= since),
            key=lambda d: d.day,
        )

    async def delete_by_student(self, student_id: UUID) -> int:
        claves = [k for k in self._dias if k[0] == student_id]
        for k in claves:
            del self._dias[k]
        return len(claves)
