from typing import Optional
from uuid import UUID

from src.application.dto.quiz_dto import (
    AttemptQuestionResultDTO,
    LearningHistoryDTO,
    QuizAttemptResultDTO,
    QuizAttemptSummaryDTO,
    QuizPublicDTO,
    QuizQuestionPublicDTO,
    TutorInteractionSummaryDTO,
)
from src.domain.aggregates.quiz_aggregate import QuizAggregate
from src.domain.aggregates.quiz_attempt_aggregate import QuizAttemptAggregate
from src.domain.ports.event_bus import EventBus
from src.domain.ports.ia_analyst import IAAnalyst
from src.domain.ports.repositories import (
    DocumentRepository,
    QuizAttemptRepository,
    QuizRepository,
    TutorInteractionRepository,
)
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
    ) -> None:
        self._doc_repo = document_repository
        self._quiz_repo = quiz_repository
        self._attempt_repo = attempt_repository
        self._interaction_repo = interaction_repository
        self._ia_analyst = ia_analyst
        self._event_bus = event_bus

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

        generated = await self._ia_analyst.generate_quiz(document, num_questions)
        quiz = QuizAggregate.create(document_id, user_id, list(generated.questions))
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
        )

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
