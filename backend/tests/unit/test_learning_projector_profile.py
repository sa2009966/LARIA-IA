from uuid import uuid4

import pytest

from src.application.services.learning_evidence_projector import LearningEvidenceProjector
from src.domain.aggregates.quiz_aggregate import QuizAggregate
from src.domain.aggregates.quiz_attempt_aggregate import QuizAttemptAggregate
from src.domain.events.domain_events import QuizAttemptCompletedEvent
from src.domain.value_objects.question import Difficulty, QuizQuestion
from src.infrastructure.persistence.in_memory_event_bus import InMemoryEventBus
from src.infrastructure.persistence.in_memory_quiz_attempt_repo import (
    InMemoryQuizAttemptRepository,
)
from src.infrastructure.persistence.in_memory_quiz_repo import InMemoryQuizRepository
from src.infrastructure.persistence.in_memory_student_profile_repo import (
    InMemoryStudentProfileRepository,
)
from src.infrastructure.persistence.in_memory_tutor_interaction_repo import (
    InMemoryTutorInteractionRepository,
)


@pytest.mark.asyncio
async def test_projector_maps_failed_items_to_concepts():
    interactions = InMemoryTutorInteractionRepository()
    profiles = InMemoryStudentProfileRepository()
    quizzes = InMemoryQuizRepository()
    attempts = InMemoryQuizAttemptRepository()
    bus = InMemoryEventBus()
    projector = LearningEvidenceProjector(
        interactions,
        bus,
        profile_repository=profiles,
        quiz_repository=quizzes,
        attempt_repository=attempts,
    )
    await projector.register()

    student = uuid4()
    doc = uuid4()
    questions = [
        QuizQuestion(
            text="¿Qué es una variable?",
            options={"A": "letra", "B": "número fijo", "C": "suma", "D": "resta"},
            correct_answer="A",
            difficulty=Difficulty.EASY,
            concept_tags=("variable",),
        ),
        QuizQuestion(
            text="¿Cómo se resuelve una ecuación 2x=4?",
            options={"A": "dividir", "B": "sumar letras", "C": "ignorar", "D": "restar x"},
            correct_answer="A",
            difficulty=Difficulty.EASY,
            concept_tags=("ecuacion",),
        ),
    ]
    quiz = QuizAggregate.create(doc, student, questions)
    await quizzes.save(quiz)
    grade = quiz.grade({0: "B", 1: "A"})  # falla variable, acierta ecuacion
    attempt = QuizAttemptAggregate.create(quiz.id, doc, student, {0: "B", 1: "A"}, grade)
    await attempts.save(attempt)

    await bus.publish(
        QuizAttemptCompletedEvent(
            aggregate_id=attempt.id,
            quiz_id=quiz.id,
            document_id=doc,
            student_id=student,
            score=attempt.score,
            total=attempt.total_points,
        )
    )

    profile = await profiles.find_by_student(student)
    assert profile is not None
    assert profile.concept_mastery_for("variable") == 0.0
    assert profile.concept_mastery_for("ecuacion") == 1.0
    assert "variable" in profile.frequent_errors
