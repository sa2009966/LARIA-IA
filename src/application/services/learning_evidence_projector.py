from src.domain.aggregates.tutor_interaction import TutorInteractionAggregate
from src.domain.events.domain_events import QuizAttemptCompletedEvent
from src.domain.ports.event_bus import EventBus
from src.domain.ports.repositories import TutorInteractionRepository


class LearningEvidenceProjector:
    """Proyecta eventos educativos a evidencia persistida (memoria educativa)."""

    def __init__(
        self,
        interaction_repository: TutorInteractionRepository,
        event_bus: EventBus,
        profile_repository=None,
    ) -> None:
        self._interaction_repo = interaction_repository
        self._event_bus = event_bus
        self._profile_repo = profile_repository

    async def register(self) -> None:
        # TutorQuestionAskedEvent: la evidencia de /ask se persiste en el servicio
        # (evita "OK sin memoria" y duplicados). Solo proyectamos intentos de quiz.
        await self._event_bus.subscribe(QuizAttemptCompletedEvent, self.handle_quiz_attempt)

    async def handle_quiz_attempt(self, event: QuizAttemptCompletedEvent) -> None:
        """Registra evidencia del intento y actualiza el perfil cognitivo."""
        interaction = TutorInteractionAggregate.create(
            student_id=event.student_id,
            document_id=event.document_id,
            question=f"[quiz_attempt] quiz_id={event.quiz_id}",
            answer=f"Puntuación: {event.score}/{event.total}",
        )
        await self._interaction_repo.save(interaction)

        if self._profile_repo is not None:
            from src.domain.aggregates.student_profile import StudentProfile

            profile = await self._profile_repo.find_by_student(event.student_id)
            if profile is None:
                profile = StudentProfile.create(event.student_id)
            ratio = (event.score / event.total) if event.total else 0.0
            profile.record_quiz_result(
                document_id=event.document_id,
                score_ratio=ratio,
                missed_concepts=(),
            )
            await self._profile_repo.save(profile)
