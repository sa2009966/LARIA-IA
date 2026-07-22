from typing import Optional
from uuid import UUID

from src.application.dto.quiz_dto import (
    AttemptQuestionResultDTO,
    LearningHistoryDTO,
    LearningRecommendationDTO,
    QuizAttemptResultDTO,
    QuizAttemptSummaryDTO,
    QuizPublicDTO,
    QuizQuestionPublicDTO,
    StudentProfileDTO,
    DocumentMasteryDTO,
    TutorInteractionSummaryDTO,
)
from src.domain.aggregates.quiz_aggregate import QuizAggregate
from src.domain.aggregates.quiz_attempt_aggregate import QuizAttemptAggregate
from src.domain.aggregates.student_profile import StudentProfile
from src.domain.ports.event_bus import EventBus
from src.domain.ports.ia_analyst import IAAnalyst
from src.domain.ports.repositories import (
    DocumentRepository,
    QuizAttemptRepository,
    QuizRepository,
    StudentProfileRepository,
    TutorInteractionRepository,
)
from src.domain.services.pedagogical_engine import PedagogicalEngine, TutorIntent
from src.domain.value_objects.question import Difficulty


class QuizService:
    _MSG_PERMISO = "No tienes permiso para operar sobre este quiz"
    _MSG_QUIZ_NO_ENCONTRADO = "Quiz no encontrado"
    _MSG_DOC_NO_ENCONTRADO = "Documento no encontrado"
    _MSG_DOC_PERMISO = "No tienes permiso para operar sobre este documento"

    def __init__(
        self,
        document_repository: DocumentRepository,
        quiz_repository: QuizRepository,
        attempt_repository: QuizAttemptRepository,
        interaction_repository: TutorInteractionRepository,
        ia_analyst: Optional[IAAnalyst] = None,
        event_bus: Optional[EventBus] = None,
        profile_repository: Optional[StudentProfileRepository] = None,
        pedagogical_engine: Optional[PedagogicalEngine] = None,
    ) -> None:
        self._doc_repo = document_repository
        self._quiz_repo = quiz_repository
        self._attempt_repo = attempt_repository
        self._interaction_repo = interaction_repository
        self._ia_analyst = ia_analyst
        self._event_bus = event_bus
        self._profile_repo = profile_repository
        self._engine = pedagogical_engine or PedagogicalEngine()

    async def generate(
        self,
        document_id: UUID,
        user_id: UUID,
        num_questions: int = 5,
    ) -> QuizPublicDTO:
        document = await self._doc_repo.find_by_id(document_id)
        if document is None:
            raise ValueError(self._MSG_DOC_NO_ENCONTRADO)
        if not document.is_owned_by(user_id):
            raise PermissionError(self._MSG_DOC_PERMISO)
        if self._ia_analyst is None:
            raise ValueError("IA Analyst not configured")

        profile = None
        if self._profile_repo is not None:
            profile = await self._profile_repo.find_by_student(user_id)
        concepts = ()
        if document.has_analysis() and document.analysis_result is not None:
            concepts = tuple(document.analysis_result.key_concepts or ())
        decision = self._engine.select(profile, document_id, TutorIntent.QUIZ, concepts)

        generated = await self._ia_analyst.generate_quiz(
            document, num_questions, decision=decision
        )
        from src.domain.services.quiz_quality import ensure_quiz_quality

        questions = ensure_quiz_quality(list(generated.questions))
        quiz = QuizAggregate.create(document_id, user_id, questions)
        await self._quiz_repo.save(quiz)

        if self._event_bus:
            for event in quiz.events:
                await self._event_bus.publish(event)
        quiz.clear_events()

        return self._to_public_dto(quiz)

    async def get_quiz(self, quiz_id: UUID, user_id: UUID) -> QuizPublicDTO:
        quiz = await self._get_quiz_if_owner(quiz_id, user_id)
        return self._to_public_dto(quiz)

    async def submit_attempt(
        self,
        quiz_id: UUID,
        user_id: UUID,
        answers: dict[int, str],
    ) -> QuizAttemptResultDTO:
        quiz = await self._get_quiz_if_owner(quiz_id, user_id)
        grade = quiz.grade(answers)
        attempt = QuizAttemptAggregate.create(
            quiz_id=quiz.id,
            document_id=quiz.document_id,
            student_id=user_id,
            answers=answers,
            grade=grade,
        )
        await self._attempt_repo.save(attempt)

        if self._event_bus:
            for event in attempt.events:
                await self._event_bus.publish(event)
        attempt.clear_events()

        return QuizAttemptResultDTO(
            attempt_id=attempt.id,
            quiz_id=quiz.id,
            document_id=quiz.document_id,
            score=attempt.score,
            total_points=attempt.total_points,
            questions=[
                AttemptQuestionResultDTO(
                    index=i,
                    text=q.text,
                    selected=answers.get(i),
                    correct_answer=q.correct_answer,
                    is_correct=attempt.per_question_correct[i],
                )
                for i, q in enumerate(quiz.questions)
            ],
            completed_at=attempt.completed_at,
        )

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
        )

    @staticmethod
    def _build_recommendations(
        profile: StudentProfile | None,
    ) -> list[LearningRecommendationDTO]:
        if profile is None or not profile.mastery_by_document:
            return [
                LearningRecommendationDTO(
                    kind="start",
                    message="Comienza con un quiz fácil sobre tu documento para medir tu nivel.",
                    document_id=None,
                )
            ]
        recs: list[LearningRecommendationDTO] = []
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
        return recs[:5]

    async def _get_quiz_if_owner(self, quiz_id: UUID, user_id: UUID) -> QuizAggregate:
        quiz = await self._quiz_repo.find_by_id(quiz_id)
        if quiz is None:
            raise ValueError(self._MSG_QUIZ_NO_ENCONTRADO)
        if not quiz.is_owned_by(user_id):
            raise PermissionError(self._MSG_PERMISO)
        return quiz

    @staticmethod
    def _difficulty_str(value) -> str:
        if isinstance(value, Difficulty):
            return value.value
        return str(value)

    def _to_public_dto(self, quiz: QuizAggregate) -> QuizPublicDTO:
        return QuizPublicDTO(
            id=quiz.id,
            document_id=quiz.document_id,
            questions=[
                QuizQuestionPublicDTO(
                    index=i,
                    text=q.text,
                    options=dict(q.options),
                    difficulty=self._difficulty_str(q.difficulty),
                )
                for i, q in enumerate(quiz.questions)
            ],
            total_points=quiz.total_points,
            created_at=quiz.created_at,
        )
