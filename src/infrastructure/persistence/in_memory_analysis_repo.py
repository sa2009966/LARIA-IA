from typing import Optional
from uuid import UUID

from src.domain.aggregates.analysis_aggregate import AnalysisAggregate
from src.domain.ports.repositories import AnalysisRepository


class InMemoryAnalysisRepository(AnalysisRepository):

    def __init__(self) -> None:
        self._analyses: dict[UUID, AnalysisAggregate] = {}

    async def save(self, analysis: AnalysisAggregate) -> None:
        self._analyses[analysis.id] = analysis

    async def find_by_document(self, document_id: UUID) -> Optional[AnalysisAggregate]:
        for a in self._analyses.values():
            if a.document_id == document_id:
                return a
        return None