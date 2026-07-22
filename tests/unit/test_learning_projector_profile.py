from uuid import uuid4

import pytest

from src.application.services.learning_evidence_projector import LearningEvidenceProjector
from src.domain.events.domain_events import QuizAttemptCompletedEvent
from src.infrastructure.persistence.in_memory_event_bus import InMemoryEventBus
from src.infrastructure.persistence.in_memory_student_profile_repo import (
    InMemoryStudentProfileRepository,
)
from src.infrastructure.persistence.in_memory_tutor_interaction_repo import (
    InMemoryTutorInteractionRepository,
)


@pytest.mark.asyncio
async def test_projector_actualiza_perfil_desde_intento():
    interactions = InMemoryTutorInteractionRepository()
    profiles = InMemoryStudentProfileRepository()
    bus = InMemoryEventBus()
    projector = LearningEvidenceProjector(interactions, bus, profile_repository=profiles)
    await projector.register()

    student = uuid4()
    doc = uuid4()
    event = QuizAttemptCompletedEvent(
        aggregate_id=uuid4(),
        quiz_id=uuid4(),
        document_id=doc,
        student_id=student,
        score=20,
        total=20,
    )
    await bus.publish(event)

    profile = await profiles.find_by_student(student)
    assert profile is not None
    assert profile.mastery_for(doc) == 1.0
    assert profile.total_attempts == 1
    saved = await interactions.find_by_student(student)
    assert len(saved) == 1
