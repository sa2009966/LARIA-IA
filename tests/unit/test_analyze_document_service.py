import pytest
from unittest.mock import AsyncMock
from uuid import uuid4

from src.application.services.analyze_document_service import AnalyzeDocumentService
from src.domain.aggregates.document_aggregate import DocumentAggregate
from src.domain.value_objects.analysis_result import AnalysisResult
from src.domain.value_objects.question import Quiz, QuizQuestion
from src.domain.ports.repositories import DocumentRepository
from src.domain.ports.ia_analyst import IAAnalyst
from src.domain.ports.event_bus import EventBus


_MSG_PERMISO = "No tienes permiso para operar sobre este documento"


@pytest.fixture
def doc_repo_mock() -> AsyncMock:
    mock = AsyncMock(spec=DocumentRepository)
    mock.find_by_id = AsyncMock()
    mock.save = AsyncMock()
    return mock


@pytest.fixture
def ia_mock() -> AsyncMock:
    mock = AsyncMock(spec=IAAnalyst)
    return mock


@pytest.fixture
def event_bus_mock() -> AsyncMock:
    mock = AsyncMock(spec=EventBus)
    mock.publish = AsyncMock()
    return mock


@pytest.fixture
def servicio(doc_repo_mock: AsyncMock, ia_mock: AsyncMock, event_bus_mock: AsyncMock) -> AnalyzeDocumentService:
    return AnalyzeDocumentService(
        document_repository=doc_repo_mock,
        ia_analyst=ia_mock,
        event_bus=event_bus_mock,
    )


class TestAnalyzeDocumentService:
    @pytest.mark.asyncio
    async def test_execute_envia_documento_a_ia_y_persiste_resumen(
        self, servicio: AnalyzeDocumentService, doc_repo_mock: AsyncMock, ia_mock: AsyncMock
    ):
        owner_id = uuid4()
        doc = DocumentAggregate.upload(owner_id, "apuntes.md", "Contenido sobre fotosíntesis.", "Biología")
        doc_repo_mock.find_by_id.return_value = doc
        result = AnalysisResult(summary="Resumen generado por IA.", confidence_score=0.95)
        ia_mock.analyze.return_value = result

        resultado = await servicio.execute(doc.id, owner_id)

        ia_mock.analyze.assert_awaited_once_with(doc)
        assert resultado.summary == "Resumen generado por IA."
        assert doc.analysis_result is not None
        doc_repo_mock.save.assert_awaited()

    @pytest.mark.asyncio
    async def test_execute_documento_inexistente(
        self, servicio: AnalyzeDocumentService, doc_repo_mock: AsyncMock
    ):
        doc_repo_mock.find_by_id.return_value = None
        with pytest.raises(ValueError, match="no encontrado"):
            await servicio.execute(uuid4(), uuid4())
        doc_repo_mock.save.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_permiso_denegado_documento_ajeno(
        self, servicio: AnalyzeDocumentService, doc_repo_mock: AsyncMock, ia_mock: AsyncMock
    ):
        owner = uuid4()
        doc = DocumentAggregate.upload(owner, "test.txt", "x", "Historia")
        doc_repo_mock.find_by_id.return_value = doc
        with pytest.raises(PermissionError, match=_MSG_PERMISO):
            await servicio.execute(doc.id, uuid4())
        ia_mock.analyze.assert_not_called()
        doc_repo_mock.save.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_usa_cache_si_hay_analysis(
        self, servicio: AnalyzeDocumentService, doc_repo_mock: AsyncMock, ia_mock: AsyncMock
    ):
        owner_id = uuid4()
        doc = DocumentAggregate.upload(owner_id, "test.txt", "x", "Historia")
        cached = AnalysisResult(summary="Resumen persistido.", confidence_score=0.9)
        doc.complete_analysis(cached)
        doc.clear_events()
        doc_repo_mock.find_by_id.return_value = doc

        out = await servicio.execute(doc.id, owner_id, force_refresh=False)

        ia_mock.analyze.assert_not_called()
        assert out.summary == "Resumen persistido."
        assert out.confidence_score == 0.9

    @pytest.mark.asyncio
    async def test_execute_force_refresh_llama_ia(
        self, servicio: AnalyzeDocumentService, doc_repo_mock: AsyncMock, ia_mock: AsyncMock
    ):
        owner_id = uuid4()
        doc = DocumentAggregate.upload(owner_id, "test.txt", "x", "Historia")
        old = AnalysisResult(summary="Viejo.", confidence_score=0.9)
        doc.complete_analysis(old)
        doc.clear_events()
        doc_repo_mock.find_by_id.return_value = doc

        nuevo = AnalysisResult(summary="Nuevo desde IA.", confidence_score=0.95)
        ia_mock.analyze.return_value = nuevo

        out = await servicio.execute(doc.id, owner_id, force_refresh=True)

        ia_mock.analyze.assert_awaited_once()
        assert out.summary == "Nuevo desde IA."

    @pytest.mark.asyncio
    async def test_answer_question_pasa_contexto_y_pregunta(
        self, servicio: AnalyzeDocumentService, doc_repo_mock: AsyncMock, ia_mock: AsyncMock
    ):
        owner_id = uuid4()
        doc = DocumentAggregate.upload(owner_id, "test.txt", "Contenido del tema.", "Historia")
        doc_repo_mock.find_by_id.return_value = doc
        ia_mock.answer_question.return_value = "Respuesta corta."

        resp = await servicio.answer_question(doc.id, "¿Qué es?", owner_id)

        assert resp == "Respuesta corta."
        ia_mock.answer_question.assert_awaited_once_with(context=doc.content, question="¿Qué es?")

    @pytest.mark.asyncio
    async def test_answer_question_permiso_denegado(
        self, servicio: AnalyzeDocumentService, doc_repo_mock: AsyncMock, ia_mock: AsyncMock
    ):
        owner = uuid4()
        doc = DocumentAggregate.upload(owner, "test.txt", "x", "Historia")
        doc_repo_mock.find_by_id.return_value = doc
        with pytest.raises(PermissionError, match=_MSG_PERMISO):
            await servicio.answer_question(doc.id, "pregunta", uuid4())
        ia_mock.answer_question.assert_not_called()

    @pytest.mark.asyncio
    async def test_generate_quiz_propaga_numero_de_preguntas(
        self, servicio: AnalyzeDocumentService, doc_repo_mock: AsyncMock, ia_mock: AsyncMock
    ):
        owner_id = uuid4()
        doc = DocumentAggregate.upload(owner_id, "test.txt", "x", "Historia")
        doc_repo_mock.find_by_id.return_value = doc
        quiz = Quiz(questions=[
            QuizQuestion(text="P1", options={"A": "1", "B": "2"}, correct_answer="A")
        ])
        ia_mock.generate_quiz.return_value = quiz

        preguntas = await servicio.generate_quiz(doc.id, owner_id, num_questions=3)

        ia_mock.generate_quiz.assert_awaited_once_with(doc, 3)
        assert preguntas.questions[0].text == "P1"

    @pytest.mark.asyncio
    async def test_generate_quiz_permiso_denegado(
        self, servicio: AnalyzeDocumentService, doc_repo_mock: AsyncMock, ia_mock: AsyncMock
    ):
        owner = uuid4()
        doc = DocumentAggregate.upload(owner, "test.txt", "x", "Historia")
        doc_repo_mock.find_by_id.return_value = doc
        with pytest.raises(PermissionError, match=_MSG_PERMISO):
            await servicio.generate_quiz(doc.id, uuid4())
        ia_mock.generate_quiz.assert_not_called()
