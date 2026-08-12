from src.application.concurrency import with_concurrency_retry
from src.domain.aggregates.student_profile import HIGH_LATENCY_THRESHOLD_MS, StudentProfile
from src.domain.aggregates.tutor_interaction import TutorInteractionAggregate
from src.domain.events.domain_events import QuizAttemptCompletedEvent, TutorQuestionAskedEvent
from src.domain.ports.event_bus import EventBus
from src.domain.ports.metrics_port import MetricsPort
from src.domain.ports.repositories import (
    QuizAttemptRepository,
    QuizRepository,
    StudentProfileRepository,
    TutorInteractionRepository,
)
from src.domain.services.concept_tagger import ConceptTagger
from src.domain.services.learning_signal_detector import LearningSignalKind
import logging

logger = logging.getLogger("laria.learning")


class LearningEvidenceProjector:
    """Proyecta eventos educativos a evidencia persistida (memoria educativa)."""

    def __init__(
        self,
        interaction_repository: TutorInteractionRepository,
        event_bus: EventBus,
        profile_repository: StudentProfileRepository | None = None,
        quiz_repository: QuizRepository | None = None,
        attempt_repository: QuizAttemptRepository | None = None,
        metrics: MetricsPort | None = None,
    ) -> None:
        self._interaction_repo = interaction_repository
        self._event_bus = event_bus
        self._profile_repo = profile_repository
        self._quiz_repo = quiz_repository
        self._attempt_repo = attempt_repository
        self._tagger = ConceptTagger()
        self._metrics = metrics

    async def register(self) -> None:
        await self._event_bus.subscribe(QuizAttemptCompletedEvent, self.handle_quiz_attempt)
        await self._event_bus.subscribe(TutorQuestionAskedEvent, self.handle_tutor_question)

    async def handle_tutor_question(self, event: TutorQuestionAskedEvent) -> None:
        """Unifica ask → perfil (además de la interacción ya guardada en el servicio)."""
        if self._profile_repo is None:
            return

        high_latency = (
            event.latency_ms is not None
            and event.latency_ms >= HIGH_LATENCY_THRESHOLD_MS
        )
        is_none = (event.signal_kind or "none") == LearningSignalKind.NONE.value
        if is_none and not high_latency and not event.cognitive_style:

            async def _mark_empty():
                p = await self._profile_repo.find_by_student(event.student_id)
                if p is None:
                    p = StudentProfile.create(event.student_id)
                if p.was_event_applied(event.event_id):
                    return p
                p.mark_event_applied(event.event_id)
                await self._profile_repo.save(p)
                return p

            await with_concurrency_retry(_mark_empty)
            return

        async def _persist_profile():
            profile = await self._profile_repo.find_by_student(event.student_id)
            if profile is None:
                profile = StudentProfile.create(event.student_id)
            if profile.was_event_applied(event.event_id):
                return profile
            if not is_none:
                profile.record_ask_struggle(
                    document_id=event.document_id,
                    strength=event.signal_strength or 0.5,
                    concepts=event.concepts or (),
                    latency_ms=event.latency_ms,
                    help_level=event.help_level,
                )
            elif high_latency:
                profile.record_high_latency(
                    event.document_id,
                    event.concepts or (),
                    event.latency_ms or 0.0,
                )
            if event.cognitive_style:
                profile.pedagogical_memory.set_preferred_style(event.cognitive_style)
            if event.pedagogical_mode:
                profile.pedagogical_memory.remember_strategy(event.pedagogical_mode)
            profile.mark_event_applied(event.event_id)
            await self._profile_repo.save(profile)
            if self._metrics:
                self._metrics.incr("profile_updates", source="ask")
                if not is_none:
                    self._metrics.incr(
                        "laria_struggle_signals",
                        kind=event.signal_kind or "unknown",
                    )
                if high_latency:
                    self._metrics.incr("laria_high_latency")
                weak = len(profile.weakest_concepts(limit=20, use_effective=True))
                mastered = len(profile.mastered_concepts(limit=50))
                self._metrics.gauge("laria_concepts_weak", float(weak), student="agg")
                self._metrics.gauge("laria_concepts_mastered", float(mastered), student="agg")
            return profile

        await with_concurrency_retry(_persist_profile)

    async def handle_quiz_attempt(self, event: QuizAttemptCompletedEvent) -> None:
        if self._profile_repo is not None:
            existing = await self._profile_repo.find_by_student(event.student_id)
            if existing is not None and existing.was_event_applied(event.event_id):
                return

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
            profile.mark_event_applied(event.event_id)
            await self._profile_repo.save(profile)
            if self._metrics:
                self._metrics.incr("profile_updates", source="quiz")
                self._metrics.incr("laria_quiz_attempts")
                self._metrics.observe("laria_quiz_score_ratio", ratio)
                weak = len(profile.weakest_concepts(limit=20, use_effective=True))
                mastered = len(profile.mastered_concepts(limit=50))
                self._metrics.gauge("laria_concepts_weak", float(weak), student="agg")
                self._metrics.gauge("laria_concepts_mastered", float(mastered), student="agg")
            logger.info(
                "quiz_projected student=%s score_ratio=%.2f concepts=%s",
                event.student_id,
                ratio,
                len(results_t),
            )
            return profile

        await with_concurrency_retry(_persist_profile)
