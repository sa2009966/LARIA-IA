from abc import ABC, abstractmethod

from src.domain.aggregates.document_aggregate import DocumentAggregate
from src.domain.value_objects.analysis_result import AnalysisResult
from src.domain.value_objects.question import Quiz


class IAAnalyst(ABC):
    @abstractmethod
    async def analyze(self, document: DocumentAggregate) -> AnalysisResult:
        ...

    @abstractmethod
    async def answer_question(self, context: str, question: str) -> str:
        ...

    @abstractmethod
    async def generate_quiz(self, document: DocumentAggregate, num_questions: int = 5) -> Quiz:
        ...
