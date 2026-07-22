from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.application.services.analyze_document_service import AnalyzeDocumentService
from src.domain.aggregates.document_aggregate import DocumentAggregate, DocumentStatus
from src.domain.value_objects.analysis_result import AnalysisResult
from src.domain.ports.repositories import DocumentRepository, TutorInteractionRepository
from src.domain.ports.ia_analyst import IAAnalyst, IAAnalysisError
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
def interaction_repo_mock() -> AsyncMock:
    mock = AsyncMock(spec=TutorInteractionRepository)
    mock.save = AsyncMock()
    return mock


@pytest.fixture
def profile_repo_mock() -> AsyncMock:
    mock = AsyncMock()
    mock.find_by_student = AsyncMock(return_value=None)
    mock.save = AsyncMock()
    return mock


@pytest.fixture
def servicio(
    doc_repo_mock: AsyncMock,
    ia_mock: AsyncMock,
    event_bus_mock: AsyncMock,
    interaction_repo_mock: AsyncMock,
    profile_repo_mock: AsyncMock,
) -> AnalyzeDocumentService:
    return AnalyzeDocumentService(
        document_repository=doc_repo_mock,
        ia_analyst=ia_mock,
        event_bus=event_bus_mock,
        interaction_repository=interaction_repo_mock,
        profile_repository=profile_repo_mock,
    )


class TestAnalyzeDocumentService:
    @pytest.mark.asyncio
    async def test_execute_persiste_analyzing_antes_de_ia(
        self, servicio: AnalyzeDocumentService, doc_repo_mock: AsyncMock, ia_mock: AsyncMock
    ):
        owner_id = uuid4()
        doc = DocumentAggregate.upload(owner_id, "apuntes.md", "Contenido.", "Biología")
        doc_repo_mock.find_by_id.return_value = doc
        result = AnalysisResult(summary="Resumen.", confidence_score=0.95)

        order: list[str] = []

        async def save_side_effect(document):
            order.append(f"save:{document.status.value}")

        async def analyze_side_effect(document):
            order.append("analyze")
            assert document.status == DocumentStatus.ANALYZING
            return result

        doc_repo_mock.save.side_effect = save_side_effect
        ia_mock.analyze.side_effect = analyze_side_effect

        await servicio.execute(doc.id, owner_id)

        assert order[0] == "save:analyzing"
        assert "analyze" in order
        assert order.index("save:analyzing") < order.index("analyze")

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
    async def test_execute_no_sobrescribe_analyzed_si_otra_corrida_gano(
        self, servicio: AnalyzeDocumentService, doc_repo_mock: AsyncMock, ia_mock: AsyncMock
    ):
        owner_id = uuid4()
        doc = DocumentAggregate.upload(owner_id, "test.txt", "x", "Historia")
        winner = DocumentAggregate.upload(owner_id, "test.txt", "x", "Historia")
        winner.id = doc.id
        winner.complete_analysis(AnalysisResult(summary="Ganador.", confidence_score=0.99))
        winner.clear_events()

        doc_repo_mock.find_by_id.side_effect = [doc, winner]
        ia_mock.analyze.side_effect = IAAnalysisError("falló esta corrida")

        with pytest.raises(IAAnalysisError):
            await servicio.execute(doc.id, owner_id)

        # No debe marcar ERROR sobre el documento ya ANALYZED
        assert winner.status == DocumentStatus.ANALYZED
        saves_after_error = [
            c.args[0] for c in doc_repo_mock.save.await_args_list if c.args[0].status == DocumentStatus.ERROR
        ]
        assert saves_after_error == []

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
    async def test_answer_question_persiste_interaccion_y_publica(
        self,
        servicio: AnalyzeDocumentService,
        doc_repo_mock: AsyncMock,
        ia_mock: AsyncMock,
        event_bus_mock: AsyncMock,
        interaction_repo_mock: AsyncMock,
    ):
        owner_id = uuid4()
        doc = DocumentAggregate.upload(owner_id, "test.txt", "Contenido del tema.", "Historia")
        doc_repo_mock.find_by_id.return_value = doc
        ia_mock.answer_question.return_value = "Respuesta corta."

        resp = await servicio.answer_question(doc.id, "¿Qué es?", owner_id)

        assert resp == "Respuesta corta."
        assert ia_mock.answer_question.await_count == 1
        call_kwargs = ia_mock.answer_question.await_args.kwargs
        assert call_kwargs["context"] == doc.content
        assert call_kwargs["question"] == "¿Qué es?"
        assert call_kwargs["decision"] is not None
        interaction_repo_mock.save.assert_awaited_once()
        event_bus_mock.publish.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_answer_question_ok_si_bus_falla(
        self,
        servicio: AnalyzeDocumentService,
        doc_repo_mock: AsyncMock,
        ia_mock: AsyncMock,
        event_bus_mock: AsyncMock,
        interaction_repo_mock: AsyncMock,
    ):
        owner_id = uuid4()
        doc = DocumentAggregate.upload(owner_id, "test.txt", "x", "Historia")
        doc_repo_mock.find_by_id.return_value = doc
        ia_mock.answer_question.return_value = "ok"
        event_bus_mock.publish.side_effect = RuntimeError("bus down")

        resp = await servicio.answer_question(doc.id, "¿?", owner_id)
        assert resp == "ok"
        interaction_repo_mock.save.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_answer_question_novice_actualiza_perfil_antes_de_decidir(
        self,
        servicio: AnalyzeDocumentService,
        doc_repo_mock: AsyncMock,
        ia_mock: AsyncMock,
        profile_repo_mock: AsyncMock,
    ):
        owner_id = uuid4()
        doc = DocumentAggregate.upload(owner_id, "alg.txt", "Variable x.", "Matemática")
        doc_repo_mock.find_by_id.return_value = doc
        ia_mock.answer_question.return_value = "Pista..."

        await servicio.answer_question(
            doc.id, "No sé nada de álgebra, ¿qué es una variable?", owner_id
        )

        profile_repo_mock.save.assert_awaited()
        saved = profile_repo_mock.save.await_args.args[0]
        assert saved.total_struggle_signals >= 1
        assert saved.mastery_for(doc.id) < 0.5
        decision = ia_mock.answer_question.await_args.kwargs["decision"]
        assert decision.mode.value == "scaffold"

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
