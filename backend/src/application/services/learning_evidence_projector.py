from src.application.concurrency import with_concurrency_retry
from src.domain.aggregates.student_profile import StudentProfile
from src.domain.aggregates.tutor_interaction import TutorInteractionAggregate
from src.domain.events.domain_events import QuizAttemptCompletedEvent
from src.domain.ports.event_bus import EventBus
from src.domain.ports.repositories import (
    QuizAttemptRepository,
    QuizRepository,
    StudentProfileRepository,
    TutorInteractionRepository,
)
from src.domain.services.concept_tagger import ConceptTagger


class LearningEvidenceProjector:
    """Proyecta eventos educativos a evidencia persistida (memoria educativa)."""

    def __init__(
        self,
        interaction_repository: TutorInteractionRepository,
        event_bus: EventBus,
        profile_repository: StudentProfileRepository | None = None,
        quiz_repository: QuizRepository | None = None,
        attempt_repository: QuizAttemptRepository | None = None,
    ) -> None:
        self._interaction_repo = interaction_repository
        self._event_bus = event_bus
        self._profile_repo = profile_repository
        self._quiz_repo = quiz_repository
        self._attempt_repo = attempt_repository
        self._tagger = ConceptTagger()

    async def register(self) -> None:
        await self._event_bus.subscribe(QuizAttemptCompletedEvent, self.handle_quiz_attempt)

    async def handle_quiz_attempt(self, event: QuizAttemptCompletedEvent) -> None:
        interaction = TutorInteractionAggregate.create(
            student_id=event.student_id,
            document_id=event.document_id,
            question=f"[quiz_attempt] quiz_id={event.quiz_id}",
            answer=f"Puntuación: {event.score}/{event.total}",
        )
        await self._interaction_repo.save(interaction)

        if self._profile_repo is None:
            return

        ratio = (event.score / event.total) if event.total else 0.0
        missed: list[str] = []
        concept_results: list[tuple[str, float]] = []

        if self._quiz_repo is not None and self._attempt_repo is not None:
            quiz = await self._quiz_repo.find_by_id(event.quiz_id)
            attempt = await self._attempt_repo.find_by_id(event.aggregate_id)
            if quiz is not None and attempt is not None:
                for i, question in enumerate(quiz.questions):
                    tagged = self._tagger.tag_question(question)
                    ok = (
                        attempt.per_question_correct[i]
                        if i < len(attempt.per_question_correct)
                        else False
                    )
                    item_ratio = 1.0 if ok else 0.0
                    tags = tagged.concept_tags or ("general",)
                    for tag in tags:
                        concept_results.append((tag, item_ratio))
                        if not ok:
                            missed.append(tag)

        missed_t = tuple(dict.fromkeys(missed))
        results_t = tuple(concept_results)

        async def _persist_profile():
            profile = await self._profile_repo.find_by_student(event.student_id)
            if profile is None:
                profile = StudentProfile.create(event.student_id)
            profile.record_quiz_result(
                document_id=event.document_id,
                score_ratio=ratio,
                missed_concepts=missed_t,
                concept_results=results_t,
            )
            await self._profile_repo.save(profile)
            return profile

        await with_concurrency_retry(_persist_profile)
