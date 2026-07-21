from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.application.services.learning_evidence_projector import LearningEvidenceProjector
from src.application.services.quiz_service import QuizService
from src.domain.aggregates.document_aggregate import DocumentAggregate
from src.domain.aggregates.quiz_aggregate import QuizAggregate
from src.domain.events.domain_events import QuizAttemptCompletedEvent, TutorQuestionAskedEvent
from src.domain.ports.event_bus import EventBus
from src.domain.ports.ia_analyst import IAAnalyst
from src.domain.ports.repositories import (
    DocumentRepository,
    QuizAttemptRepository,
    QuizRepository,
    TutorInteractionRepository,
)
from src.domain.value_objects.question import Quiz, QuizQuestion
from src.infrastructure.persistence.in_memory_event_bus import InMemoryEventBus
from src.infrastructure.persistence.in_memory_quiz_attempt_repo import InMemoryQuizAttemptRepository
from src.infrastructure.persistence.in_memory_quiz_repo import InMemoryQuizRepository
from src.infrastructure.persistence.in_memory_tutor_interaction_repo import (
    InMemoryTutorInteractionRepository,
)


def _quiz_vo() -> Quiz:
    return Quiz(
        questions=[
            QuizQuestion(text="P1", options={"A": "1", "B": "2"}, correct_answer="A"),
            QuizQuestion(text="P2", options={"A": "x", "B": "y"}, correct_answer="B"),
        ]
    )


@pytest.fixture
def doc_repo() -> AsyncMock:
    return AsyncMock(spec=DocumentRepository)


@pytest.fixture
def ia() -> AsyncMock:
    return AsyncMock(spec=IAAnalyst)


@pytest.fixture
def event_bus() -> AsyncMock:
    bus = AsyncMock(spec=EventBus)
    bus.publish = AsyncMock()
    return bus


@pytest.fixture
def quiz_repo() -> InMemoryQuizRepository:
    return InMemoryQuizRepository()


@pytest.fixture
def attempt_repo() -> InMemoryQuizAttemptRepository:
    return InMemoryQuizAttemptRepository()


@pytest.fixture
def interaction_repo() -> InMemoryTutorInteractionRepository:
    return InMemoryTutorInteractionRepository()


@pytest.fixture
def service(
    doc_repo: AsyncMock,
    quiz_repo: InMemoryQuizRepository,
    attempt_repo: InMemoryQuizAttemptRepository,
    interaction_repo: InMemoryTutorInteractionRepository,
    ia: AsyncMock,
    event_bus: AsyncMock,
) -> QuizService:
    return QuizService(
        document_repository=doc_repo,
        quiz_repository=quiz_repo,
        attempt_repository=attempt_repo,
        interaction_repository=interaction_repo,
        ia_analyst=ia,
        event_bus=event_bus,
    )


class TestQuizService:
    @pytest.mark.asyncio
    async def test_generate_persiste_y_no_expone_respuestas(
        self,
        service: QuizService,
        doc_repo: AsyncMock,
        ia: AsyncMock,
        quiz_repo: InMemoryQuizRepository,
        event_bus: AsyncMock,
    ):
        owner = uuid4()
        doc = DocumentAggregate.upload(owner, "t.txt", "contenido", "Historia")
        doc_repo.find_by_id.return_value = doc
        ia.generate_quiz.return_value = _quiz_vo()

        public = await service.generate(doc.id, owner, num_questions=2)

        assert public.document_id == doc.id
        assert len(public.questions) == 2
        assert not hasattr(public.questions[0], "correct_answer")
        stored = await quiz_repo.find_by_id(public.id)
        assert stored is not None
        assert stored.questions[0].correct_answer == "A"
        event_bus.publish.assert_awaited()
        assert event_bus.publish.await_args.args[0].event_type == "QuizGeneratedEvent"

    @pytest.mark.asyncio
    async def test_generate_permiso_denegado(self, service: QuizService, doc_repo: AsyncMock, ia: AsyncMock):
        owner = uuid4()
        doc = DocumentAggregate.upload(owner, "t.txt", "x", "Historia")
        doc_repo.find_by_id.return_value = doc
        with pytest.raises(PermissionError):
            await service.generate(doc.id, uuid4())
        ia.generate_quiz.assert_not_called()

    @pytest.mark.asyncio
    async def test_submit_attempt_califica_y_persiste(
        self,
        service: QuizService,
        quiz_repo: InMemoryQuizRepository,
        attempt_repo: InMemoryQuizAttemptRepository,
        event_bus: AsyncMock,
    ):
        owner = uuid4()
        quiz = QuizAggregate.create(uuid4(), owner, list(_quiz_vo().questions))
        quiz.clear_events()
        await quiz_repo.save(quiz)

        result = await service.submit_attempt(quiz.id, owner, {0: "A", 1: "A"})

        assert result.score == 10
        assert result.total_points == 20
        assert result.questions[0].is_correct is True
        assert result.questions[1].is_correct is False
        assert result.questions[0].correct_answer == "A"
        assert result.questions[1].correct_answer == "B"
        saved = await attempt_repo.find_by_student(owner)
        assert len(saved) == 1
        assert event_bus.publish.await_args.args[0].event_type == "QuizAttemptCompletedEvent"

    @pytest.mark.asyncio
    async def test_get_learning_history(
        self,
        service: QuizService,
        quiz_repo: InMemoryQuizRepository,
        attempt_repo: InMemoryQuizAttemptRepository,
        interaction_repo: InMemoryTutorInteractionRepository,
        event_bus: AsyncMock,
    ):
        from src.domain.aggregates.tutor_interaction import TutorInteractionAggregate

        owner = uuid4()
        quiz = QuizAggregate.create(uuid4(), owner, list(_quiz_vo().questions))
        quiz.clear_events()
        await quiz_repo.save(quiz)
        await service.submit_attempt(quiz.id, owner, {0: "A", 1: "B"})
        await interaction_repo.save(
            TutorInteractionAggregate.create(owner, quiz.document_id, "¿Qué?", "Respuesta")
        )

        history = await service.get_learning_history(owner)
        assert len(history.attempts) == 1
        assert history.attempts[0].score == 20
        assert len(history.tutor_interactions) == 1
        assert history.tutor_interactions[0].question == "¿Qué?"


class TestLearningEvidenceProjector:
    @pytest.mark.asyncio
    async def test_persiste_interaccion_al_recibir_evento(self):
        bus = InMemoryEventBus()
        repo = InMemoryTutorInteractionRepository()
        projector = LearningEvidenceProjector(repo, bus)
        await projector.register()

        student, doc = uuid4(), uuid4()
        await bus.publish(
            TutorQuestionAskedEvent(
                aggregate_id=doc,
                student_id=student,
                document_id=doc,
                question="¿Cómo funciona?",
                answer="Así.",
            )
        )

        items = await repo.find_by_student(student)
        assert len(items) == 1
        assert items[0].question == "¿Cómo funciona?"
        assert items[0].answer == "Así."
        assert items[0].document_id == doc

    @pytest.mark.asyncio
    async def test_persiste_evidencia_de_intento_quiz(self):
        bus = InMemoryEventBus()
        repo = InMemoryTutorInteractionRepository()
        projector = LearningEvidenceProjector(repo, bus)
        await projector.register()

        student, doc, quiz = uuid4(), uuid4(), uuid4()
        await bus.publish(
            QuizAttemptCompletedEvent(
                aggregate_id=quiz,
                quiz_id=quiz,
                document_id=doc,
                student_id=student,
                score=2,
                total=5,
            )
        )
        items = await repo.find_by_student(student)
        assert len(items) == 1
        assert "[quiz_attempt]" in items[0].question
        assert "2/5" in items[0].answer
