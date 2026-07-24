from datetime import datetime
from uuid import uuid4

from src.domain.events.domain_events import (
    DomainEventBase,
    UserRegisteredEvent,
    UserDeactivatedEvent,
    DocumentUploadedEvent,
    DocumentDeletedEvent,
    AnalysisCompletedEvent,
    AnalysisFailedEvent,
    QuizAttemptCompletedEvent,
    TutorQuestionAskedEvent,
)


class TestDomainEventBase:
    def test_event_has_timestamp(self):
        event = DomainEventBase(aggregate_id=uuid4())
        assert isinstance(event.timestamp, datetime)
        assert event.timestamp.tzinfo is not None

    def test_event_type_name(self):
        event = DomainEventBase(aggregate_id=uuid4())
        assert event.event_type == "DomainEventBase"


class TestUserEvents:
    def test_user_registered_event(self):
        uid = uuid4()
        event = UserRegisteredEvent(aggregate_id=uid, email="user@example.com")
        assert event.aggregate_id == uid
        assert event.email == "user@example.com"
        assert event.event_type == "UserRegisteredEvent"

    def test_user_deactivated_event(self):
        uid = uuid4()
        event = UserDeactivatedEvent(aggregate_id=uid)
        assert event.aggregate_id == uid
        assert event.event_type == "UserDeactivatedEvent"


class TestDocumentEvents:
    def test_document_uploaded_event(self):
        doc_id = uuid4()
        owner_id = uuid4()
        event = DocumentUploadedEvent(
            aggregate_id=doc_id,
            owner_id=owner_id,
            filename="test.txt",
        )
        assert event.aggregate_id == doc_id
        assert event.owner_id == owner_id
        assert event.filename == "test.txt"

    def test_document_deleted_event(self):
        doc_id = uuid4()
        owner_id = uuid4()
        event = DocumentDeletedEvent(aggregate_id=doc_id, owner_id=owner_id)
        assert event.aggregate_id == doc_id
        assert event.owner_id == owner_id


class TestAnalysisEvents:
    def test_analysis_completed_event(self):
        aid = uuid4()
        did = uuid4()
        event = AnalysisCompletedEvent(
            aggregate_id=aid,
            document_id=did,
            summary_length=150,
        )
        assert event.summary_length == 150
        assert event.event_type == "AnalysisCompletedEvent"

    def test_analysis_failed_event(self):
        event = AnalysisFailedEvent(
            aggregate_id=uuid4(),
            document_id=uuid4(),
            error_message="Timeout",
        )
        assert event.error_message == "Timeout"


class TestLearningEvents:
    def test_quiz_attempt_completed(self):
        event = QuizAttemptCompletedEvent(
            aggregate_id=uuid4(),
            quiz_id=uuid4(),
            document_id=uuid4(),
            student_id=uuid4(),
            score=3,
            total=5,
        )
        assert event.score == 3
        assert event.total == 5

    def test_tutor_question_asked(self):
        event = TutorQuestionAskedEvent(
            aggregate_id=uuid4(),
            student_id=uuid4(),
            document_id=uuid4(),
            question="¿Qué es X?",
            answer="X es ...",
        )
        assert event.question.startswith("¿")
