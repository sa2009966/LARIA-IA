from src.domain.entities.analysis import Analysis
from src.domain.entities.document import Document
from src.domain.ports.document_repository import DocumentRepository
from src.domain.ports.ia_analyst import IAAnalyst


class AnalyzeDocumentService:
    """Caso de uso: analizar un documento con IA y persistir el resultado.

    Depende únicamente de los puertos del dominio. No conoce ningún detalle
    de infraestructura (SQLAlchemy, Kimi, HTTP, etc.).
    """

    def __init__(
        self,
        document_repository: DocumentRepository,
        ia_analyst: IAAnalyst,
    ) -> None:
        self._document_repo = document_repository
        self._ia_analyst = ia_analyst

    def execute(self, document_id: int) -> Analysis:
        document = self._document_repo.find_by_id(document_id)
        if document is None:
            raise ValueError(f"Documento con id={document_id} no encontrado.")

        analysis = self._ia_analyst.analyze(document)

        document.analysis_result = analysis.summary
        self._document_repo.save(document)

        return analysis

    def answer_question(self, document_id: int, question: str) -> str:
        document = self._document_repo.find_by_id(document_id)
        if document is None:
            raise ValueError(f"Documento con id={document_id} no encontrado.")

        return self._ia_analyst.answer_question(
            context=document.content,
            question=question,
        )

    def generate_quiz(self, document_id: int, num_questions: int = 5) -> list[str]:
        document = self._document_repo.find_by_id(document_id)
        if document is None:
            raise ValueError(f"Documento con id={document_id} no encontrado.")

        return self._ia_analyst.generate_quiz(document, num_questions)
