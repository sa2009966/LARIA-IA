from abc import ABC, abstractmethod

from src.domain.entities.analysis import Analysis
from src.domain.entities.document import Document


class IAAnalyst(ABC):
    """Puerto de salida: contrato para el análisis de documentos con IA.

    La capa de infraestructura (adaptador Kimi) implementa este contrato.
    El dominio y la aplicación dependen únicamente de esta abstracción.
    """

    @abstractmethod
    def analyze(self, document: Document) -> Analysis:
        """Analiza el contenido de un documento y devuelve un Analysis."""
        ...

    @abstractmethod
    def answer_question(self, context: str, question: str) -> str:
        """Responde una pregunta dado un contexto textual."""
        ...

    @abstractmethod
    def generate_quiz(self, document: Document, num_questions: int = 5) -> list[str]:
        """Genera preguntas de comprensión a partir de un documento."""
        ...
