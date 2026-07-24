from typing import Optional
from uuid import UUID

from src.application.concurrency import with_concurrency_retry
from src.application.dto.quiz_dto import (
    AttemptQuestionResultDTO,
    QuizAttemptResultDTO,
    QuizPublicDTO,
    QuizQuestionPublicDTO,
)
from src.domain.aggregates.quiz_aggregate import QuizAggregate
from src.domain.aggregates.quiz_attempt_aggregate import QuizAttemptAggregate
from src.domain.aggregates.tutor_session import TutorSession
from src.domain.ports.event_bus import EventBus
from src.domain.ports.ia_analyst import IAAnalyst
from src.domain.ports.repositories import (
    DocumentRepository,
    QuizAttemptRepository,
    QuizRepository,
    StudentProfileRepository,
    TutorInteractionRepository,
    TutorSessionRepository,
)
from src.application.services.llm_gate import LlmGate
from src.domain.services.concept_tagger import ConceptTagger
from src.domain.services.context_selector import ContextSelector
from src.domain.services.pedagogical_engine import PedagogicalEngine, TutorIntent
from src.domain.services.quiz_quality import ensure_quiz_quality
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
        session_repository: Optional[TutorSessionRepository] = None,
        llm_gate: Optional[LlmGate] = None,
    ) -> None:
        self._doc_repo = document_repository
        self._quiz_repo = quiz_repository
        self._attempt_repo = attempt_repository
        self._interaction_repo = interaction_repository
        self._ia_analyst = ia_analyst
        self._event_bus = event_bus
        self._profile_repo = profile_repository
        self._engine = pedagogical_engine or PedagogicalEngine()
        self._session_repo = session_repository
        self._tagger = ConceptTagger()
        self._context = ContextSelector()
        self._llm_gate = llm_gate

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
        if self._ia_analyst is None and self._llm_gate is None:
            raise ValueError("IA Analyst not configured")

        profile = None
        if self._profile_repo is not None:
            profile = await self._profile_repo.find_by_student(user_id)
        session = None
        if self._session_repo is not None:
            session = await self._session_repo.find_by_student_document(user_id, document_id)
        concepts = ()
        if document.has_analysis() and document.analysis_result is not None:
            concepts = tuple(document.analysis_result.key_concepts or ())
        decision = self._engine.select(
            profile, document_id, TutorIntent.QUIZ, concepts, session=session
        )
        ctx = self._context.select(document, decision.focus_concepts)
        if self._llm_gate is not None:
            generated = await self._llm_gate.generate_quiz(
                document,
                num_questions,
                decision=decision,
                context=ctx,
                student_id=user_id,
            )
        else:
            generated = await self._ia_analyst.generate_quiz(
                document, num_questions, decision=decision, context=ctx
            )

        questions = ensure_quiz_quality(list(generated.questions))
        questions = self._tagger.tag_questions(questions, concepts or decision.focus_concepts)
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

        if self._session_repo is not None:
            ratio = (attempt.score / attempt.total_points) if attempt.total_points else 0.0

            async def _persist_session():
                session = await self._session_repo.find_by_student_document(
                    user_id, quiz.document_id
                )
                if session is None:
                    session = TutorSession.start(user_id, quiz.document_id)
                session.record_quiz_check(ratio)
                await self._session_repo.save(session)
                return session

            await with_concurrency_retry(_persist_session)

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
