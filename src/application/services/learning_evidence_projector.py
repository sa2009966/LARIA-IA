from src.domain.aggregates.tutor_interaction import TutorInteractionAggregate
from src.domain.events.domain_events import QuizAttemptCompletedEvent, TutorQuestionAskedEvent
from src.domain.ports.event_bus import EventBus
from src.domain.ports.repositories import TutorInteractionRepository


class LearningEvidenceProjector:
    """Proyecta eventos educativos a evidencia persistida (memoria educativa)."""

    def __init__(
        self,
        interaction_repository: TutorInteractionRepository,
        event_bus: EventBus,
    ) -> None:
        self._interaction_repo = interaction_repository
        self._event_bus = event_bus

    async def register(self) -> None:
        await self._event_bus.subscribe(TutorQuestionAskedEvent, self.handle_tutor_question)
        await self._event_bus.subscribe(QuizAttemptCompletedEvent, self.handle_quiz_attempt)

    async def handle_tutor_question(self, event: TutorQuestionAskedEvent) -> None:
        interaction = TutorInteractionAggregate.create(
            student_id=event.student_id,
            document_id=event.document_id,
            question=event.question,
            answer=event.answer,
        )
        await self._interaction_repo.save(interaction)

    async def handle_quiz_attempt(self, event: QuizAttemptCompletedEvent) -> None:
        """Registra evidencia mínima del intento (score) en el stream de interacciones."""
        interaction = TutorInteractionAggregate.create(
            student_id=event.student_id,
            document_id=event.document_id,
            question=f"[quiz_attempt] quiz_id={event.quiz_id}",
            answer=f"Puntuación: {event.score}/{event.total}",
        )
        await self._interaction_repo.save(interaction)
