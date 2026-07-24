"""Lecturas de aprendizaje (historial, perfil, recomendaciones)."""
from uuid import UUID

from src.application.dto.quiz_dto import (
    ConceptMasteryDTO,
    DocumentMasteryDTO,
    LearningHistoryDTO,
    LearningRecommendationDTO,
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


class LearningQueryService:
    def __init__(
        self,
        attempt_repository: QuizAttemptRepository,
        interaction_repository: TutorInteractionRepository,
        profile_repository: StudentProfileRepository | None = None,
    ) -> None:
        self._attempt_repo = attempt_repository
        self._interaction_repo = interaction_repository
        self._profile_repo = profile_repository

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
            recommendations=self._build_recommendations(profile),
        )

    async def get_profile(self, user_id: UUID) -> StudentProfileDTO:
        if self._profile_repo is None:
            raise ValueError("Repositorio de perfil no configurado")
        profile = await self._profile_repo.find_by_student(user_id)
        if profile is None:
            profile = StudentProfile.create(user_id)
        return StudentProfileDTO(
            student_id=profile.student_id,
            pace=profile.pace,
            total_attempts=profile.total_attempts,
            total_struggle_signals=profile.total_struggle_signals,
            frequent_errors=list(profile.frequent_errors),
            updated_at=profile.updated_at,
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
                )
                for c in profile.mastery_by_concept.values()
            ],
        )

    @staticmethod
    def _build_recommendations(
        profile: StudentProfile | None,
    ) -> list[LearningRecommendationDTO]:
        if profile is None or (
            not profile.mastery_by_document and not profile.mastery_by_concept
        ):
            return [
                LearningRecommendationDTO(
                    kind="start",
                    message="Comienza con un quiz fácil sobre tu documento para medir tu nivel.",
                    document_id=None,
                )
            ]
        recs: list[LearningRecommendationDTO] = []
        for concept in profile.weakest_concepts(limit=3):
            mastery = profile.concept_mastery_for(concept)
            if mastery < 0.5:
                recs.append(
                    LearningRecommendationDTO(
                        kind="review_concept",
                        message=f"Repasa: {concept}.",
                        document_id=None,
                    )
                )
        for doc_id in profile.weakest_documents(limit=2):
            mastery = profile.mastery_for(doc_id)
            if mastery < 0.4:
                recs.append(
                    LearningRecommendationDTO(
                        kind="review",
                        message="Repasa el documento con explicación guiada (andamiaje).",
                        document_id=doc_id,
                    )
                )
                recs.append(
                    LearningRecommendationDTO(
                        kind="easier_quiz",
                        message="Haz un quiz más fácil para consolidar lo básico.",
                        document_id=doc_id,
                    )
                )
            elif mastery < 0.7:
                recs.append(
                    LearningRecommendationDTO(
                        kind="guided_explain",
                        message="Pide una explicación guiada de los puntos débiles.",
                        document_id=doc_id,
                    )
                )
            else:
                recs.append(
                    LearningRecommendationDTO(
                        kind="challenge",
                        message="Practica con un quiz más exigente o preguntas socráticas.",
                        document_id=doc_id,
                    )
                )
        return recs[:6]
