from uuid import UUID, uuid4

from src.domain.aggregates.analysis_aggregate import AnalysisAggregate
from src.domain.value_objects.analysis_result import AnalysisResult
from src.domain.value_objects.question import Quiz, QuizQuestion


class TestAnalysisAggregate:
    def test_create_analysis(self):
        doc_id = uuid4()
        result = AnalysisResult(summary="Resumen educativo", confidence_score=0.95)
        analysis = AnalysisAggregate.create(doc_id, result)
        assert isinstance(analysis.id, UUID)
        assert analysis.document_id == doc_id
        assert analysis.result is not None
        assert analysis.result.summary == "Resumen educativo"
        assert analysis.model_used == "gpt-4o-mini"

    def test_create_analysis_emits_event(self):
        doc_id = uuid4()
        result = AnalysisResult(summary="Resumen", confidence_score=0.95)
        analysis = AnalysisAggregate.create(doc_id, result)
        assert len(analysis.events) == 1
        assert analysis.events[0].event_type == "AnalysisCompletedEvent"
        assert analysis.events[0].document_id == doc_id

    def test_create_failed_analysis(self):
        doc_id = uuid4()
        analysis = AnalysisAggregate.create_failed(doc_id, "Timeout error")
        assert analysis.document_id == doc_id
        assert analysis.result is None
        assert analysis.quiz is None

    def test_create_failed_emits_event(self):
        doc_id = uuid4()
        analysis = AnalysisAggregate.create_failed(doc_id, "Error")
        assert len(analysis.events) == 1
        assert analysis.events[0].event_type == "AnalysisFailedEvent"
        assert analysis.events[0].error_message == "Error"

    def test_add_quiz(self):
        doc_id = uuid4()
        result = AnalysisResult(summary="Resumen", confidence_score=0.9)
        analysis = AnalysisAggregate.create(doc_id, result)

        qq = QuizQuestion(
            text="¿2+2?",
            options={"A": "3", "B": "4", "C": "5", "D": "6"},
            correct_answer="B",
        )
        quiz = Quiz(questions=[qq])
        analysis.add_quiz(quiz)

        assert analysis.has_quiz() is True
        assert analysis.quiz is not None
        assert analysis.quiz.total_questions == 1

    def test_no_quiz_initially(self):
        doc_id = uuid4()
        result = AnalysisResult(summary="Resumen", confidence_score=0.9)
        analysis = AnalysisAggregate.create(doc_id, result)
        assert analysis.has_quiz() is False

    def test_clear_events(self):
        doc_id = uuid4()
        result = AnalysisResult(summary="Resumen", confidence_score=0.9)
        analysis = AnalysisAggregate.create(doc_id, result)
        analysis.clear_events()
        assert len(analysis.events) == 0

    def test_custom_model(self):
        doc_id = uuid4()
        result = AnalysisResult(summary="Resumen", confidence_score=0.9)
        analysis = AnalysisAggregate.create(doc_id, result, model_used="gpt-4")
        assert analysis.model_used == "gpt-4"
