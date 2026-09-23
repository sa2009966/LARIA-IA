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
from src.domain.adaptive_signals import SignalKind
from src.domain.services.concept_tagger import ConceptTagger
from src.domain.services.learning_signal_detector import LearningSignalKind
import logging

logger = logging.getLogger("laria.learning")


def _observed(event: TutorQuestionAskedEvent, kind: SignalKind) -> float:
    for raw_kind, value in event.signal_observations or ():
        if raw_kind == kind.value:
            return value
    return 0.0


def _apply_conversational_evidence(
    profile: StudentProfile, event: TutorQuestionAskedEvent
) -> bool:
    """Evidencia POSITIVA desde el chat (ADR-006, fase 2).

    La autocorrección ("ah claro, ya entendí") es evidencia directa de
    aprendizaje. Se detectaba desde el ADR-004 y solo se usaba para subir la
    tasa de preguntas socráticas: el mastery nunca podía subir conversando.

    Devuelve si hubo evidencia positiva, porque de eso depende que la memoria
    pedagógica registre la estrategia y el estilo como efectivos.
    """
    if _observed(event, SignalKind.SELF_CORRECTION) <= 0.0:
        return False
    concepts = tuple(event.focus_concepts or event.concepts or ())
    if not concepts:
        return False
    profile.record_conversational_success(
        document_id=event.document_id,
        concepts=concepts,
    )
    return True


def _apply_celebration(profile: StudentProfile, event: TutorQuestionAskedEvent) -> None:
    """Marca el hito que el turno ya le reconoció al estudiante (ADR-009).

    El servicio decide y comunica; el perfil lo recuerda aquí, dentro de la
    idempotencia por `event_id`, para que el mismo logro no se celebre dos
    veces ni se pierda si el evento se reintenta.
    """
    if event.celebrated_concept:
        profile.mark_celebrated(event.celebrated_concept)


def _apply_interaction_state(
    profile: StudentProfile, event: TutorQuestionAskedEvent
) -> None:
    """Aplica al perfil las observaciones medidas en el borde.

    El projector **no** calcula el gap: lo recibe ya medido con wall-clock real
    (ADR-004, Decisión 2). Escribe aquí para que el perfil conserve un único
    escritor y la idempotencia por `event_id` siga cubriendo todo el turno.
    """
    for raw_kind, value in event.signal_observations or ():
        try:
            kind = SignalKind(raw_kind)
        except ValueError:
            continue
        profile.observe_signal(kind, value)
    profile.record_interaction(answer_length=event.answer_length)


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
                _apply_conversational_evidence(p, event)
                _apply_celebration(p, event)
                _apply_interaction_state(p, event)
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
            # La memoria de "lo que funcionó" solo se escribe cuando funcionó.
            # Antes se escribía en todos los turnos, así que
            # `last_effective_strategies` guardaba estrategias inefectivas y
            # `preferred_explanation_style` congelaba el estilo del estudiante.
            if _apply_conversational_evidence(profile, event):
                if event.cognitive_style:
                    profile.pedagogical_memory.set_preferred_style(event.cognitive_style)
                if event.pedagogical_mode:
                    profile.pedagogical_memory.remember_strategy(event.pedagogical_mode)
            _apply_celebration(profile, event)
            _apply_interaction_state(profile, event)
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

        etiquetados = 0
        sin_etiquetar = 0
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
                    if not tagged.concept_tags:
                        # Ítem sin concepto conocido: cuenta para el mastery del
                        # documento, pero no se le inventa un concepto al que
                        # atribuirle evidencia (ADR-011).
                        sin_etiquetar += 1
                        continue
                    etiquetados += 1
                    for tag in tagged.concept_tags:
                        concept_results.append((tag, item_ratio))
                        if not ok:
                            missed.append(tag)

        missed_t = tuple(dict.fromkeys(missed))
        results_t = tuple(concept_results)

        async def _persist_profile():
            profile = await self._profile_repo.find_by_student(event.student_id)
            if profile is None:
                profile = StudentProfile.create(event.student_id)
            # La comprobación de idempotencia va DENTRO del closure: con el
            # reintento por conflicto, el perfil releído puede tener el evento
            # ya aplicado y se contaría el intento dos veces.
            if profile.was_event_applied(event.event_id):
                return profile
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
                # Cobertura de etiquetado: qué parte de la evidencia sabe a qué
                # concepto pertenece. Si esto cae, el perfil se vuelve ciego.
                if etiquetados:
                    self._metrics.incr("laria_quiz_items", etiquetados, tagged="yes")
                if sin_etiquetar:
                    self._metrics.incr("laria_quiz_items", sin_etiquetar, tagged="no")
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
