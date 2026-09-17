from dataclasses import dataclass, field
from uuid import UUID
from typing import Optional
import logging
import time

from src.application.concurrency import with_concurrency_retry
from src.application.services.llm_gate import LlmGate
from src.domain.aggregates.concept_graph import ConceptGraph
from src.domain.aggregates.document_aggregate import DocumentAggregate, DocumentStatus
from src.domain.aggregates.student_profile import StudentProfile
from src.domain.aggregates.tutor_interaction import TutorInteractionAggregate
from src.domain.aggregates.tutor_session import TutorSession
from src.domain.events.domain_events import TutorQuestionAskedEvent
from src.domain.catalog.prerequisite_seeds import build_seeded_graph
from src.domain.exceptions import ConcurrencyError
from src.domain.ports.repositories import (
    ConceptGraphRepository,
    DocumentRepository,
    StudentProfileRepository,
    TutorInteractionRepository,
    TutorSessionRepository,
)
from src.domain.ports.ia_analyst import IAAnalysisError, IAAnalyst
from src.domain.ports.event_bus import EventBus
from src.domain.ports.metrics_port import MetricsPort
from src.domain.services.adaptive_policy import (
    DEFAULT_CUTOFFS,
    AdaptationCutoffs,
    AdaptationParameters,
    AdaptivePolicy,
    PromptShapingParameters,
    SignalKind,
)
from src.domain.services.adaptive_signal_observer import (
    AdaptiveSignalObserver,
    TurnFacts,
)
from src.domain.services.context_selector import ContextSelector
from src.domain.services.learning_signal_detector import (
    LearningSignalDetector,
    LearningSignalKind,
)
from src.domain.services.pedagogical_engine import (
    PedagogicalDecision,
    PedagogicalEngine,
    TutorIntent,
)
from src.domain.value_objects.analysis_result import AnalysisResult

logger = logging.getLogger(__name__)


@dataclass
class PedagogyPlan:
    """Todo lo decidido antes de generar lenguaje.

    Existe para que streaming y no-streaming partan del **mismo** cálculo: la
    decisión pedagógica y la adaptación se fijan aquí, antes de abrir el stream
    (ADR-004, Decisión 3).
    """

    document_id: UUID
    student_id: UUID
    question: str
    context: str
    decision: PedagogicalDecision
    adaptation: AdaptationParameters
    struggle_signals: int = 0
    signal_kind: str = LearningSignalKind.NONE.value
    signal_strength: float = 0.0
    signal_concepts: tuple[str, ...] = ()
    help_level: float = 0.0
    observations: dict[SignalKind, float] = field(default_factory=dict)
    started: float = 0.0

    @property
    def prompt_shaping(self) -> PromptShapingParameters:
        return self.adaptation.prompt_shaping


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
        llm_gate: Optional[LlmGate] = None,
        metrics: Optional[MetricsPort] = None,
        cutoffs: Optional[AdaptationCutoffs] = None,
        adaptation_enabled: bool = False,
        concept_graph_repository: Optional[ConceptGraphRepository] = None,
        graph_id: str = "default",
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
        self._llm_gate = llm_gate
        self._metrics = metrics
        self._cutoffs = cutoffs or DEFAULT_CUTOFFS
        self._adaptive = AdaptivePolicy(self._cutoffs)
        self._observer = AdaptiveSignalObserver(self._cutoffs)
        # Modo sombra: las señales se computan y persisten, pero el fragmento
        # prompt-shaping no se inyecta hasta que la política esté calibrada.
        self._adaptation_enabled = adaptation_enabled
        self._graph_repo = concept_graph_repository
        self._graph_id = graph_id

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

        if self._ia_analyst is None and self._llm_gate is None:
            raise ValueError("IA Analyst not configured")

        if force_refresh and document.status == DocumentStatus.ANALYZED:
            document.reset_for_reanalysis()
        if document.status in (DocumentStatus.ANALYZING, DocumentStatus.ERROR):
            document.reset_for_reanalysis()
        document.mark_analyzing()
        await self._doc_repo.save(document)
        try:
            if self._llm_gate is not None:
                result = await self._llm_gate.analyze(document, force_refresh=force_refresh)
            else:
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
        """Devuelve solo el texto de la respuesta del tutor (API pública)."""
        content, _ = await self.answer_question_with_pedagogy(
            document_id, question, requesting_user_id
        )
        return content

    async def answer_question_with_pedagogy(
        self, document_id: UUID, question: str, requesting_user_id: UUID
    ) -> tuple[str, "PedagogicalDecision | None"]:
        """Como answer_question, pero también devuelve la decisión pedagógica."""
        plan = await self.prepare_pedagogy(document_id, question, requesting_user_id)
        answer = await self.answer_from_plan(plan)
        await self.finalize_interaction(plan, answer)
        return answer, plan.decision

    def prompt_shaping_for(self, plan: PedagogyPlan) -> PromptShapingParameters | None:
        """Fragmento a inyectar, o None en modo sombra.

        Ambos paths (streaming y no) pasan por aquí: no pueden divergir.
        """
        return plan.prompt_shaping if self._adaptation_enabled else None

    async def answer_from_plan(self, plan: PedagogyPlan) -> str:
        """Genera la respuesta completa a partir de un plan ya decidido."""
        if self._llm_gate is not None:
            return await self._llm_gate.answer_question(
                context=plan.context,
                question=plan.question,
                decision=plan.decision,
                struggle_signals=plan.struggle_signals,
                adaptation=self.prompt_shaping_for(plan),
            )
        return await self._ia_analyst.answer_question(
            context=plan.context,
            question=plan.question,
            decision=plan.decision,
            adaptation=self.prompt_shaping_for(plan),
        )

    async def stream_from_plan(self, plan: PedagogyPlan):
        """Igual que `answer_from_plan`, en trozos.

        Consume exactamente el mismo plan y el mismo `prompt_shaping_for`, que es
        lo que impide que streaming y no-streaming adapten distinto.
        """
        if self._llm_gate is None:
            yield await self.answer_from_plan(plan)
            return
        async for token in self._llm_gate.answer_question_stream(
            context=plan.context,
            question=plan.question,
            decision=plan.decision,
            struggle_signals=plan.struggle_signals,
            adaptation=self.prompt_shaping_for(plan),
        ):
            yield token

    async def prepare_pedagogy(
        self, document_id: UUID, question: str, requesting_user_id: UUID
    ) -> PedagogyPlan:
        """Decide todo lo pedagógico **antes** de generar lenguaje.

        Aquí se calcula `interaction_gap_ms` en el borde, con wall-clock real y
        contra `StudentProfile`, que es la única fuente de verdad del estado de
        interacción (ADR-004, Decisión 2).
        """
        document = await self._get_document_if_owner(document_id, requesting_user_id)
        if self._ia_analyst is None and self._llm_gate is None:
            raise ValueError("IA Analyst not configured")
        if self._interaction_repo is None:
            raise ValueError("Repositorio de interacciones no configurado")

        started = time.monotonic()
        signal = self._signals.detect(question)
        help_level = 0.5 if signal.kind == LearningSignalKind.HELP else 0.0
        profile = None
        observations: dict[SignalKind, float] = {}
        if self._profile_repo is not None:
            profile = await self._profile_repo.find_by_student(requesting_user_id)
            if profile is None:
                profile = StudentProfile.create(requesting_user_id)
            observations = self._observer.observe(
                TurnFacts(
                    question=question,
                    gap_ms=profile.interaction_gap_ms(),
                    previous_answer_length=profile.last_answer_length,
                )
            )
            for kind, value in observations.items():
                profile.observe_signal(kind, value, alpha=self._cutoffs.ewma_alpha)
            # Mutación en memoria para esta decisión; persistencia vía projector
            if signal.kind != LearningSignalKind.NONE:
                profile.record_ask_struggle(
                    document_id=document_id,
                    strength=signal.strength,
                    concepts=signal.concepts_hint,
                    help_level=help_level,
                )

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
        graph = await self._load_graph(concepts)
        decision = self._engine.select(
            profile,
            document_id,
            TutorIntent.ASK,
            concepts,
            session=session,
            question=question,
            graph=graph,
        )
        adaptation = self._adaptive.decide(
            profile.signals_for_policy() if profile else {}
        )
        return PedagogyPlan(
            document_id=document_id,
            student_id=requesting_user_id,
            question=question,
            context=self._context.select(document, decision.focus_concepts),
            decision=decision,
            adaptation=adaptation,
            struggle_signals=profile.total_struggle_signals if profile else 0,
            signal_kind=signal.kind.value,
            signal_strength=signal.strength,
            signal_concepts=signal.concepts_hint,
            help_level=help_level,
            observations=observations,
            started=started,
        )

    async def _load_graph(self, concepts: tuple[str, ...]) -> ConceptGraph | None:
        """Carga el grafo y registra los conceptos del documento como sugerencias.

        El orden de aparición en un material es señal barata y ruidosa: entra
        como `INFERRED` y no puede bloquear a nadie (ADR-005, Decisión 2). Aquí
        —y no en el motor— porque escribir es async y el motor es puro.
        """
        if self._graph_repo is None:
            return None
        graph = await self._graph_repo.find_by_id(self._graph_id)
        if graph is None:
            graph = build_seeded_graph(self._graph_id)
            await self._save_graph(graph)
        if concepts and graph.suggest_from_document_order(concepts):
            await self._save_graph(graph)
        return graph

    async def _save_graph(self, graph: ConceptGraph) -> None:
        """Escritura best-effort: nunca romper el turno de tutoría por el grafo.

        Sin reintento a propósito: ante conflicto de versión el agregado en mano
        está obsoleto y reintentar el mismo `save` volvería a fallar. La
        sugerencia se vuelve a proponer en el turno siguiente.
        """
        try:
            await self._graph_repo.save(graph)
        except ConcurrencyError:
            logger.debug("concept_graph_suggestion_dropped graph=%s", graph.graph_id)
        except Exception:
            logger.exception("concept_graph_save_failed graph=%s", graph.graph_id)

    async def finalize_interaction(
        self,
        plan: PedagogyPlan,
        answer: str,
        celebrated_concept: str | None = None,
    ) -> None:
        """Cierra el turno: sesión, interacción, estado de interacción y evento.

        `celebrated_concept` es el hito que el turno ya comunicó al estudiante:
        viaja en el evento para que el projector —único escritor del perfil— lo
        recuerde y no se celebre dos veces (ADR-009).
        """
        latency_ms = (time.monotonic() - plan.started) * 1000.0

        if self._session_repo is not None:

            async def _persist_session():
                s = await self._session_repo.find_by_student_document(
                    plan.student_id, plan.document_id
                )
                if s is None:
                    s = TutorSession.start(plan.student_id, plan.document_id)
                hint = answer[:160].replace("\n", " ")
                s.record_ask(hint_summary=hint, focus=plan.decision.focus_concepts)
                s.objective = plan.decision.objective
                await self._session_repo.save(s)
                return s

            await with_concurrency_retry(_persist_session)

        interaction = TutorInteractionAggregate.create(
            student_id=plan.student_id,
            document_id=plan.document_id,
            question=plan.question,
            answer=answer,
        )
        await self._interaction_repo.save(interaction)

        if self._event_bus:
            try:
                await self._event_bus.publish(
                    TutorQuestionAskedEvent(
                        aggregate_id=plan.document_id,
                        student_id=plan.student_id,
                        document_id=plan.document_id,
                        question=plan.question,
                        answer=answer,
                        signal_kind=plan.signal_kind,
                        signal_strength=plan.signal_strength,
                        concepts=plan.signal_concepts,
                        latency_ms=latency_ms,
                        help_level=plan.help_level,
                        cognitive_style=plan.decision.cognitive_style.value,
                        pedagogical_mode=plan.decision.mode.value,
                        signal_observations=tuple(
                            (kind.value, value)
                            for kind, value in plan.observations.items()
                        ),
                        answer_length=len(answer),
                        focus_concepts=plan.decision.focus_concepts,
                        celebrated_concept=celebrated_concept,
                    )
                )
            except Exception:
                logger.exception(
                    "event_publish_failed event=TutorQuestionAskedEvent student=%s document=%s",
                    plan.student_id,
                    plan.document_id,
                )
                if self._metrics:
                    self._metrics.incr(
                        "event_publish_failed",
                        event="TutorQuestionAskedEvent",
                    )

    async def _hydrate_content(self, document: DocumentAggregate) -> DocumentAggregate:
        if document.content:
            return document
        body = await self._doc_repo.get_content(document.id)
        if body is None:
            raise ValueError(f"Documento con id={document.id} no encontrado")
        document.content = body
        return document

    async def _get_document_if_owner(
        self, document_id: UUID, user_id: UUID
    ) -> DocumentAggregate:
        document = await self._doc_repo.find_by_id(document_id)
        if document is None:
            raise ValueError(f"Documento con id={document_id} no encontrado")
        if not document.is_owned_by(user_id):
            raise PermissionError(self._MSG_PERMISO)
        return await self._hydrate_content(document)
