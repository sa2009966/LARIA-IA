"""Lecturas de aprendizaje (historial, perfil, recomendaciones)."""
from uuid import UUID

from src.application.dto.quiz_dto import (
    ConceptMasteryDTO,
    DocumentMasteryDTO,
    LearningHistoryDTO,
    LearningRecommendationDTO,
    PedagogicalMemoryDTO,
    QuizAttemptSummaryDTO,
    StudentProfileDTO,
    TutorInteractionSummaryDTO,
)
from src.domain.aggregates.student_profile import StudentProfile
from src.domain.ports.repositories import (
    QuizAttemptRepository,
    StudentProfileRepository,
    TutorInteractionRepository,
)
from src.domain.services.recommendation_engine import RecommendationEngine


class LearningQueryService:
    def __init__(
        self,
        attempt_repository: QuizAttemptRepository,
        interaction_repository: TutorInteractionRepository,
        profile_repository: StudentProfileRepository | None = None,
        recommendation_engine: RecommendationEngine | None = None,
    ) -> None:
        self._attempt_repo = attempt_repository
        self._interaction_repo = interaction_repository
        self._profile_repo = profile_repository
        self._recs = recommendation_engine or RecommendationEngine()

    async def get_learning_history(self, user_id: UUID) -> LearningHistoryDTO:
        attempts = await self._attempt_repo.find_by_student(user_id)
        interactions = await self._interaction_repo.find_by_student(user_id)
        profile = None
        if self._profile_repo is not None:
            profile = await self._profile_repo.find_by_student(user_id)
        return LearningHistoryDTO(
            attempts=[
                QuizAttemptSummaryDTO(
                    attempt_id=a.id,
                    quiz_id=a.quiz_id,
                    document_id=a.document_id,
                    score=a.score,
                    total_points=a.total_points,
                    completed_at=a.completed_at,
                )
                for a in sorted(attempts, key=lambda x: x.completed_at, reverse=True)
            ],
            tutor_interactions=[
                TutorInteractionSummaryDTO(
                    id=i.id,
                    document_id=i.document_id,
                    question=i.question,
                    answer=i.answer,
                    asked_at=i.asked_at,
                )
                for i in sorted(interactions, key=lambda x: x.asked_at, reverse=True)
            ],
            recommendations=[
                LearningRecommendationDTO(
                    kind=r.kind,
                    message=r.message,
                    document_id=r.document_id,
                    concept=r.concept,
                    priority=r.priority,
                    suggested_minutes=r.suggested_minutes,
                )
                for r in self._recs.build(profile)
            ],
        )

    async def get_profile(self, user_id: UUID) -> StudentProfileDTO:
        if self._profile_repo is None:
            raise ValueError("Repositorio de perfil no configurado")
        profile = await self._profile_repo.find_by_student(user_id)
        if profile is None:
            profile = StudentProfile.create(user_id)
        mem = profile.pedagogical_memory
        return StudentProfileDTO(
            student_id=profile.student_id,
            pace=profile.pace,
            total_attempts=profile.total_attempts,
            total_struggle_signals=profile.total_struggle_signals,
            frequent_errors=list(profile.frequent_errors),
            updated_at=profile.updated_at,
            learning_velocity=profile.learning_velocity,
            pedagogical_memory=PedagogicalMemoryDTO(
                frequent_misconceptions=list(mem.frequent_misconceptions),
                successful_examples=list(mem.successful_examples),
                successful_analogies=list(mem.successful_analogies),
                preferred_explanation_style=mem.preferred_explanation_style,
                last_effective_strategies=list(mem.last_effective_strategies),
            ),
            mastery_by_document=[
                DocumentMasteryDTO(
                    document_id=m.document_id,
                    attempts=m.attempts,
                    mastery=m.mastery,
                    last_score_ratio=m.last_score_ratio,
                    struggle_signals=m.struggle_signals,
                )
                for m in profile.mastery_by_document.values()
            ],
            mastery_by_concept=[
                ConceptMasteryDTO(
                    concept_key=c.concept_key,
                    attempts=c.attempts,
                    mastery=c.mastery,
                    last_score_ratio=c.last_score_ratio,
                    effective_mastery=c.effective_mastery(),
                    confidence=c.confidence,
                    last_practiced_at=c.last_practiced_at,
                    subject=c.subject,
                    help_requests=c.help_requests,
                    error_streak=c.error_streak,
                )
                for c in profile.mastery_by_concept.values()
            ],
        )
