from datetime import datetime
from uuid import uuid4

from src.domain.events.domain_events import (
    DomainEventBase,
    UserRegisteredEvent, UserDeactivatedEvent,
    DocumentUploadedEvent, DocumentDeletedEvent,
    AnalysisCompletedEvent, AnalysisFailedEvent,
    EventFactory,
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

    def test_user_events_have_timestamp(self):
        uid = uuid4()
        reg = UserRegisteredEvent(aggregate_id=uid, email="a@b.com")
        deact = UserDeactivatedEvent(aggregate_id=uid)
        assert reg.timestamp is not None
        assert deact.timestamp is not None
        assert abs((reg.timestamp - deact.timestamp).total_seconds()) < 1


class TestDocumentEvents:
    def test_document_uploaded_event(self):
        doc_id = uuid4()
        owner_id = uuid4()
        event = DocumentUploadedEvent(
            aggregate_id=doc_id,
            owner_id=owner_id,
            filename="test.txt"
        )
        assert event.aggregate_id == doc_id
        assert event.owner_id == owner_id
        assert event.filename == "test.txt"
        assert event.event_type == "DocumentUploadedEvent"

    def test_document_deleted_event(self):
        doc_id = uuid4()
        owner_id = uuid4()
        event = DocumentDeletedEvent(
            aggregate_id=doc_id,
            owner_id=owner_id
        )
        assert event.aggregate_id == doc_id
        assert event.owner_id == owner_id
        assert event.event_type == "DocumentDeletedEvent"


class TestAnalysisEvents:
    def test_analysis_completed_event(self):
        aid = uuid4()
        did = uuid4()
        event = AnalysisCompletedEvent(
            aggregate_id=aid,
            document_id=did,
            summary_length=150
        )
        assert event.aggregate_id == aid
        assert event.document_id == did
        assert event.summary_length == 150
        assert event.event_type == "AnalysisCompletedEvent"

    def test_analysis_failed_event(self):
        aid = uuid4()
        did = uuid4()
        event = AnalysisFailedEvent(
            aggregate_id=aid,
            document_id=did,
            error_message="Timeout"
        )
        assert event.aggregate_id == aid
        assert event.document_id == did
        assert event.error_message == "Timeout"
        assert event.event_type == "AnalysisFailedEvent"


class TestEventFactory:
    def test_create_user_registered(self):
        uid = uuid4()
        event = EventFactory.create_user_registered(uid, "user@example.com")
        assert isinstance(event, UserRegisteredEvent)
        assert event.aggregate_id == uid
        assert event.email == "user@example.com"

    def test_create_document_uploaded(self):
        did = uuid4()
        oid = uuid4()
        event = EventFactory.create_document_uploaded(did, oid, "doc.txt")
        assert isinstance(event, DocumentUploadedEvent)
        assert event.aggregate_id == did
        assert event.owner_id == oid
        assert event.filename == "doc.txt"

    def test_create_analysis_completed(self):
        aid = uuid4()
        did = uuid4()
        event = EventFactory.create_analysis_completed(aid, did, 200)
        assert isinstance(event, AnalysisCompletedEvent)
        assert event.aggregate_id == aid
        assert event.document_id == did
        assert event.summary_length == 200

    def test_all_events_utc_timestamp(self):
        uid = uuid4()
        event = EventFactory.create_user_registered(uid, "user@example.com")
        assert event.timestamp.tzinfo is not None
