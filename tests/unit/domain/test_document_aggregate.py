import pytest
from uuid import UUID, uuid4

from src.domain.aggregates.document_aggregate import DocumentAggregate, DocumentStatus
from src.domain.value_objects.analysis_result import AnalysisResult


class TestDocumentAggregate:
    def test_upload_creates_document(self):
        owner_id = uuid4()
        doc = DocumentAggregate.upload(owner_id, "test.txt", "contenido", "Matemática")
        assert isinstance(doc.id, UUID)
        assert doc.owner_id == owner_id
        assert doc.filename == "test.txt"
        assert doc.content == "contenido"
        assert doc.subject.value == "Matemática"
        assert doc.status == DocumentStatus.UPLOADED

    def test_upload_emits_event(self):
        owner_id = uuid4()
        doc = DocumentAggregate.upload(owner_id, "test.txt", "x", "Biología")
        assert len(doc.events) == 1
        assert doc.events[0].event_type == "DocumentUploadedEvent"
        assert doc.events[0].filename == "test.txt"

    def test_upload_invalid_subject(self):
        owner_id = uuid4()
        with pytest.raises(ValueError, match="invalido"):
            DocumentAggregate.upload(owner_id, "test.txt", "x", "Astrología")

    def test_mark_analyzing(self):
        owner_id = uuid4()
        doc = DocumentAggregate.upload(owner_id, "test.txt", "x", "Historia")
        doc.mark_analyzing()
        assert doc.status == DocumentStatus.ANALYZING

    def test_mark_analyzing_twice_raises(self):
        owner_id = uuid4()
        doc = DocumentAggregate.upload(owner_id, "test.txt", "x", "Historia")
        doc.mark_analyzing()
        with pytest.raises(ValueError, match="already being analyzed"):
            doc.mark_analyzing()

    def test_complete_analysis(self):
        owner_id = uuid4()
        doc = DocumentAggregate.upload(owner_id, "test.txt", "x", "Historia")
        result = AnalysisResult(summary="Resumen", confidence_score=0.95)
        doc.complete_analysis(result)
        assert doc.status == DocumentStatus.ANALYZED
        assert doc.analysis_result is not None
        assert doc.analysis_result.summary == "Resumen"
        assert doc.error_message is None

    def test_complete_analysis_emits_event(self):
        owner_id = uuid4()
        doc = DocumentAggregate.upload(owner_id, "test.txt", "x", "Historia")
        prev = len(doc.events)
        result = AnalysisResult(summary="Resumen", confidence_score=0.95)
        doc.complete_analysis(result)
        assert len(doc.events) == prev + 1
        assert doc.events[-1].event_type == "AnalysisCompletedEvent"

    def test_mark_error(self):
        owner_id = uuid4()
        doc = DocumentAggregate.upload(owner_id, "test.txt", "x", "Historia")
        doc.mark_error("API timeout")
        assert doc.status == DocumentStatus.ERROR
        assert doc.error_message == "API timeout"

    def test_mark_error_emits_event(self):
        owner_id = uuid4()
        doc = DocumentAggregate.upload(owner_id, "test.txt", "x", "Historia")
        prev = len(doc.events)
        doc.mark_error("Error")
        assert len(doc.events) == prev + 1
        assert doc.events[-1].event_type == "AnalysisFailedEvent"

    def test_has_analysis_false_initially(self):
        owner_id = uuid4()
        doc = DocumentAggregate.upload(owner_id, "test.txt", "x", "Historia")
        assert doc.has_analysis() is False

    def test_has_analysis_true_after_complete(self):
        owner_id = uuid4()
        doc = DocumentAggregate.upload(owner_id, "test.txt", "x", "Historia")
        result = AnalysisResult(summary="Resumen", confidence_score=0.95)
        doc.complete_analysis(result)
        assert doc.has_analysis() is True

    def test_is_owned_by(self):
        owner_id = uuid4()
        doc = DocumentAggregate.upload(owner_id, "test.txt", "x", "Historia")
        assert doc.is_owned_by(owner_id) is True
        assert doc.is_owned_by(uuid4()) is False

    def test_mark_deleted_emits_event(self):
        owner_id = uuid4()
        doc = DocumentAggregate.upload(owner_id, "test.txt", "x", "Historia")
        prev = len(doc.events)
        doc.mark_deleted()
        assert len(doc.events) == prev + 1
        assert doc.events[-1].event_type == "DocumentDeletedEvent"

    def test_clear_events(self):
        owner_id = uuid4()
        doc = DocumentAggregate.upload(owner_id, "test.txt", "x", "Historia")
        doc.clear_events()
        assert len(doc.events) == 0

    def test_analyzing_already_analyzed_raises(self):
        owner_id = uuid4()
        doc = DocumentAggregate.upload(owner_id, "test.txt", "x", "Historia")
        result = AnalysisResult(summary="R", confidence_score=0.9)
        doc.complete_analysis(result)
        with pytest.raises(ValueError, match="already analyzed"):
            doc.mark_analyzing()
