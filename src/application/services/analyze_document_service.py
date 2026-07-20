from uuid import UUID
from typing import Optional

from src.domain.aggregates.document_aggregate import DocumentAggregate, DocumentStatus
from src.domain.aggregates.analysis_aggregate import AnalysisAggregate
from src.domain.ports.repositories import DocumentRepository
from src.domain.ports.ia_analyst import IAAnalyst
from src.domain.ports.event_bus import EventBus


class AnalyzeDocumentService:
    _MSG_PERMISO = "No tienes permiso para operar sobre este documento"

    def __init__(
        self,
        document_repository: DocumentRepository,
        ia_analyst: Optional[IAAnalyst] = None,
        event_bus: Optional[EventBus] = None,
    ) -> None:
        self._doc_repo = document_repository
        self._ia_analyst = ia_analyst
        self._event_bus = event_bus

    async def execute(
        self,
        document_id: UUID,
        requesting_user_id: UUID,
        force_refresh: bool = False,
    ) -> "AnalysisResult":
        document = await self._get_document_if_owner(document_id, requesting_user_id)

        if document.has_analysis():
            if not force_refresh:
                return document.analysis_result

        if self._ia_analyst is None:
            raise ValueError("IA Analyst not configured")

        if force_refresh and document.status == DocumentStatus.ANALYZED:
            document.status = DocumentStatus.UPLOADED
            document.analysis_result = None
        document.mark_analyzing()
        try:
            result = await self._ia_analyst.analyze(document)
        except Exception as e:
            document.mark_error(str(e))
            await self._doc_repo.save(document)
            raise

        document.complete_analysis(result)
        await self._doc_repo.save(document)

        analysis = AnalysisAggregate.create(document_id, result)
        if self._event_bus:
            for event in document.events:
                await self._event_bus.publish(event)
            for event in analysis.events:
                await self._event_bus.publish(event)
        document.clear_events()
        analysis.clear_events()

        return result

    async def answer_question(self, document_id: UUID, question: str, requesting_user_id: UUID) -> str:
        document = await self._get_document_if_owner(document_id, requesting_user_id)
        if self._ia_analyst is None:
            raise ValueError("IA Analyst not configured")
        return await self._ia_analyst.answer_question(context=document.content, question=question)

    async def generate_quiz(
        self,
        document_id: UUID,
        requesting_user_id: UUID,
        num_questions: int = 5,
    ) -> "Quiz":
        document = await self._get_document_if_owner(document_id, requesting_user_id)
        if self._ia_analyst is None:
            raise ValueError("IA Analyst not configured")
        return await self._ia_analyst.generate_quiz(document, num_questions)

    async def _get_document_if_owner(self, document_id: UUID, user_id: UUID) -> DocumentAggregate:
        document = await self._doc_repo.find_by_id(document_id)
        if document is None:
            raise ValueError(f"Documento con id={document_id} no encontrado")
        if not document.is_owned_by(user_id):
            raise PermissionError(self._MSG_PERMISO)
        return document
