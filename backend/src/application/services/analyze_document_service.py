from uuid import UUID
from typing import Optional

from src.application.concurrency import with_concurrency_retry
from src.domain.aggregates.document_aggregate import DocumentAggregate, DocumentStatus
from src.domain.aggregates.student_profile import StudentProfile
from src.domain.aggregates.tutor_interaction import TutorInteractionAggregate
from src.domain.aggregates.tutor_session import TutorSession
from src.domain.events.domain_events import TutorQuestionAskedEvent
from src.domain.ports.repositories import (
    DocumentRepository,
    StudentProfileRepository,
    TutorInteractionRepository,
    TutorSessionRepository,
)
from src.domain.ports.ia_analyst import IAAnalysisError, IAAnalyst
from src.domain.ports.event_bus import EventBus
from src.domain.services.context_selector import ContextSelector
from src.domain.services.learning_signal_detector import (
    LearningSignalDetector,
    LearningSignalKind,
)
from src.domain.services.pedagogical_engine import PedagogicalEngine, TutorIntent
from src.domain.value_objects.analysis_result import AnalysisResult


class AnalyzeDocumentService:
    _MSG_PERMISO = "No tienes permiso para operar sobre este documento"

    def __init__(
        self,
        document_repository: DocumentRepository,
        ia_analyst: Optional[IAAnalyst] = None,
        event_bus: Optional[EventBus] = None,
        interaction_repository: Optional[TutorInteractionRepository] = None,
        profile_repository: Optional[StudentProfileRepository] = None,
        pedagogical_engine: Optional[PedagogicalEngine] = None,
        session_repository: Optional[TutorSessionRepository] = None,
    ) -> None:
        self._doc_repo = document_repository
        self._ia_analyst = ia_analyst
        self._event_bus = event_bus
        self._interaction_repo = interaction_repository
        self._profile_repo = profile_repository
        self._engine = pedagogical_engine or PedagogicalEngine()
        self._session_repo = session_repository
        self._signals = LearningSignalDetector()
        self._context = ContextSelector()

    async def execute(
        self,
        document_id: UUID,
        requesting_user_id: UUID,
        force_refresh: bool = False,
    ) -> AnalysisResult:
        document = await self._get_document_if_owner(document_id, requesting_user_id)

        if document.has_analysis():
            if not force_refresh:
                return document.analysis_result

        if self._ia_analyst is None:
            raise ValueError("IA Analyst not configured")

        if force_refresh and document.status == DocumentStatus.ANALYZED:
            document.reset_for_reanalysis()
        if document.status in (DocumentStatus.ANALYZING, DocumentStatus.ERROR):
            document.reset_for_reanalysis()
        document.mark_analyzing()
        await self._doc_repo.save(document)
        try:
            result = await self._ia_analyst.analyze(document)
        except Exception as e:
            current = await self._doc_repo.find_by_id(document_id)
            if current is not None and current.status == DocumentStatus.ANALYZED:
                raise
            safe_message = (
                str(e) if isinstance(e, IAAnalysisError) else "Error interno durante el análisis."
            )
            target = current if current is not None else document
            target.mark_error(safe_message)
            await self._doc_repo.save(target)
            if self._event_bus:
                for event in target.events:
                    await self._event_bus.publish(event)
                target.clear_events()
            raise

        current = await self._doc_repo.find_by_id(document_id)
        if (
            current is not None
            and current.status == DocumentStatus.ANALYZED
            and current.has_analysis()
            and not force_refresh
        ):
            return current.analysis_result

        document.complete_analysis(result)
        await self._doc_repo.save(document)

        if self._event_bus:
            for event in document.events:
                await self._event_bus.publish(event)
        document.clear_events()

        return result

    async def answer_question(
        self, document_id: UUID, question: str, requesting_user_id: UUID
    ) -> str:
        document = await self._get_document_if_owner(document_id, requesting_user_id)
        if self._ia_analyst is None:
            raise ValueError("IA Analyst not configured")
        if self._interaction_repo is None:
            raise ValueError("Repositorio de interacciones no configurado")

        profile = None
        if self._profile_repo is not None:
            signal = self._signals.detect(question)

            async def _persist_struggle():
                p = await self._profile_repo.find_by_student(requesting_user_id)
                if p is None:
                    p = StudentProfile.create(requesting_user_id)
                if signal.kind != LearningSignalKind.NONE:
                    p.record_ask_struggle(
                        document_id=document_id,
                        strength=signal.strength,
                        concepts=signal.concepts_hint,
                    )
                    await self._profile_repo.save(p)
                return p

            profile = await with_concurrency_retry(_persist_struggle)

        session = None
        if self._session_repo is not None:
            session = await self._session_repo.find_by_student_document(
                requesting_user_id, document_id
            )
            if session is None:
                session = TutorSession.start(requesting_user_id, document_id)

        concepts = ()
        if document.has_analysis() and document.analysis_result is not None:
            concepts = tuple(document.analysis_result.key_concepts or ())
        decision = self._engine.select(
            profile, document_id, TutorIntent.ASK, concepts, session=session
        )
        ctx = self._context.select(document, decision.focus_concepts)

        answer = await self._ia_analyst.answer_question(
            context=ctx, question=question, decision=decision
        )

        if self._session_repo is not None:

            async def _persist_session():
                s = await self._session_repo.find_by_student_document(
                    requesting_user_id, document_id
                )
                if s is None:
                    s = TutorSession.start(requesting_user_id, document_id)
                hint = answer[:160].replace("\n", " ")
                s.record_ask(hint_summary=hint, focus=decision.focus_concepts)
                s.objective = decision.objective
                await self._session_repo.save(s)
                return s

            session = await with_concurrency_retry(_persist_session)

        interaction = TutorInteractionAggregate.create(
            student_id=requesting_user_id,
            document_id=document_id,
            question=question,
            answer=answer,
        )
        await self._interaction_repo.save(interaction)

        if self._event_bus:
            try:
                await self._event_bus.publish(
                    TutorQuestionAskedEvent(
                        aggregate_id=document_id,
                        student_id=requesting_user_id,
                        document_id=document_id,
                        question=question,
                        answer=answer,
                    )
                )
            except Exception:
                pass
        return answer

    async def _get_document_if_owner(
        self, document_id: UUID, user_id: UUID
    ) -> DocumentAggregate:
        document = await self._doc_repo.find_by_id(document_id)
        if document is None:
            raise ValueError(f"Documento con id={document_id} no encontrado")
        if not document.is_owned_by(user_id):
            raise PermissionError(self._MSG_PERMISO)
        return document
