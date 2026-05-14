from datetime import datetime, timezone

from src.domain.entities.analysis import Analysis
from src.domain.entities.document import Document
from src.domain.ports.document_repository import DocumentRepository
from src.domain.ports.ia_analyst import IAAnalyst


class AnalyzeDocumentService:
    """Caso de uso: analizar un documento con IA y persistir el resultado.

    Depende únicamente de los puertos del dominio. No conoce ningún detalle
    de infraestructura (SQLAlchemy, Kimi, HTTP, etc.).
    """

    # Mensaje único de autorización para operaciones de IA sobre documentos ajenos.
    _MSG_PERMISO = "No tienes permiso para operar sobre este documento"

    def __init__(
        self,
        document_repository: DocumentRepository,
        ia_analyst: IAAnalyst,
    ) -> None:
        self._document_repo = document_repository
        self._ia_analyst = ia_analyst

    def _documento_para_solicitante(self, document_id: int, requesting_user_id: int) -> Document:
        """Carga el documento o lanza error si no existe o el solicitante no es el propietario."""
        document = self._document_repo.find_by_id(document_id)
        if document is None:
            raise ValueError(f"Documento con id={document_id} no encontrado.")
        if document.owner_id != requesting_user_id:
            raise PermissionError(self._MSG_PERMISO)
        return document

    def execute(
        self,
        document_id: int,
        requesting_user_id: int,
        force_refresh: bool = False,
    ) -> Analysis:
        """Analiza con IA o devuelve resultado cacheado (`analysis_result`) para ahorrar llamadas externas."""
        document = self._documento_para_solicitante(document_id, requesting_user_id)

        # Si ya hay resumen persistido y no se fuerza refresco, no llamamos al puerto de IA.
        if (
            not force_refresh
            and document.analysis_result is not None
            and document.analysis_result.strip() != ""
        ):
            return Analysis(
                id=None,
                document_id=document.id,  # type: ignore[arg-type]
                summary=document.analysis_result,
                key_concepts=[],
                suggested_questions=[],
                model_used="cached",
                created_at=datetime.now(timezone.utc),
            )

        analysis = self._ia_analyst.analyze(document)

        document.analysis_result = analysis.summary
        self._document_repo.save(document)

        return analysis

    def answer_question(self, document_id: int, question: str, requesting_user_id: int) -> str:
        document = self._documento_para_solicitante(document_id, requesting_user_id)

        return self._ia_analyst.answer_question(
            context=document.content,
            question=question,
        )

    def generate_quiz(
        self,
        document_id: int,
        requesting_user_id: int,
        num_questions: int = 5,
    ) -> list[str]:
        document = self._documento_para_solicitante(document_id, requesting_user_id)

        return self._ia_analyst.generate_quiz(document, num_questions)
