from abc import ABC, abstractmethod
from typing import AsyncIterator, Optional

from src.domain.aggregates.document_aggregate import DocumentAggregate
from src.domain.services.pedagogical_engine import PedagogicalDecision
from src.domain.value_objects.analysis_result import AnalysisResult
from src.domain.value_objects.question import Quiz


class IAAnalysisError(Exception):
    """Fallo al comunicarse con el proveedor de IA o al interpretar su respuesta.

    El mensaje debe ser seguro para mostrar al usuario (sin detalles internos).
    """


class IAAnalyst(ABC):
    @abstractmethod
    async def analyze(self, document: DocumentAggregate) -> AnalysisResult:
        ...

    @abstractmethod
    async def answer_question(
        self,
        context: str,
        question: str,
        decision: Optional[PedagogicalDecision] = None,
    ) -> str:
        ...

    @abstractmethod
    async def generate_quiz(
        self,
        document: DocumentAggregate,
        num_questions: int = 5,
        decision: Optional[PedagogicalDecision] = None,
        context: Optional[str] = None,
    ) -> Quiz:
        ...


class StreamingIAAnalyst(ABC):
    """Interfaz opcional para proveedores que soportan streaming de tokens.

    Los analistas que no la implementen pueden usar `answer_question` y
    emitir el texto completo en un único chunk.
    """

    async def answer_question_stream(
        self,
        context: str,
        question: str,
        decision: Optional[PedagogicalDecision] = None,
        model: Optional[str] = None,
    ) -> "AsyncIterator[str]":
        ...
