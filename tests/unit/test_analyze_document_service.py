"""Pruebas unitarias de `AnalyzeDocumentService`.

Se mockean dos puertos:
- `DocumentRepository`: devuelve entidades `Document` en memoria, sin BD.
- `IAAnalyst`: simula a Kimi/Moonshot; no hay `httpx` ni red.

Así comprobamos el orquestado: validación de propiedad, caché de análisis,
lectura del documento, llamada al analizador solo cuando corresponde,
persistencia del resumen y devolución de resultados.
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from src.application.services.analyze_document_service import AnalyzeDocumentService
from src.domain.entities.analysis import Analysis
from src.domain.entities.document import Document

_MSG_PERMISO = "No tienes permiso para operar sobre este documento"


@pytest.fixture
def doc_repo_mock() -> MagicMock:
    """Mock del repositorio de documentos."""
    return MagicMock()


@pytest.fixture
def ia_mock() -> MagicMock:
    """Mock del puerto de IA (sustituye `KimiIAAnalyst` y cualquier cliente HTTP)."""
    return MagicMock()


@pytest.fixture
def servicio(doc_repo_mock: MagicMock, ia_mock: MagicMock) -> AnalyzeDocumentService:
    return AnalyzeDocumentService(document_repository=doc_repo_mock, ia_analyst=ia_mock)


def _documento(doc_id: int = 5, owner_id: int = 1, analysis_result: str | None = None) -> Document:
    return Document(
        id=doc_id,
        owner_id=owner_id,
        filename="apuntes.md",
        content="Contenido del tema: fotosíntesis.",
        subject="Biología",
        uploaded_at=datetime.now(UTC),
        analysis_result=analysis_result,
    )


def test_execute_envia_documento_a_ia_y_persiste_resumen(
    servicio: AnalyzeDocumentService,
    doc_repo_mock: MagicMock,
    ia_mock: MagicMock,
) -> None:
    """Flujo completo: propietario válido → analyze del mock → mutar `analysis_result` → save."""
    doc = _documento()
    doc_repo_mock.find_by_id.return_value = doc

    analisis = Analysis(
        id=None,
        document_id=5,
        summary="Resumen generado por IA de prueba.",
        key_concepts=["clorofila", "luz"],
        suggested_questions=["¿Qué es la fotosíntesis?"],
        model_used="mock-model",
        created_at=datetime.now(UTC),
    )
    ia_mock.analyze.return_value = analisis

    def save_side_effect(d: Document) -> Document:
        return d

    doc_repo_mock.save.side_effect = save_side_effect

    resultado = servicio.execute(document_id=5, requesting_user_id=1)

    ia_mock.analyze.assert_called_once_with(doc)
    assert resultado.summary == analisis.summary
    assert doc.analysis_result == analisis.summary
    doc_repo_mock.save.assert_called_once()
    guardado = doc_repo_mock.save.call_args[0][0]
    assert guardado.analysis_result == analisis.summary


def test_execute_documento_inexistente(servicio: AnalyzeDocumentService, doc_repo_mock: MagicMock) -> None:
    doc_repo_mock.find_by_id.return_value = None

    with pytest.raises(ValueError, match="Documento con id=99 no encontrado"):
        servicio.execute(99, requesting_user_id=1)

    doc_repo_mock.save.assert_not_called()


def test_execute_permiso_denegado_documento_ajeno(
    servicio: AnalyzeDocumentService,
    doc_repo_mock: MagicMock,
    ia_mock: MagicMock,
) -> None:
    """Si `owner_id` no coincide con `requesting_user_id`, no se llama a la IA."""
    doc = _documento(owner_id=100)
    doc_repo_mock.find_by_id.return_value = doc

    with pytest.raises(PermissionError, match=_MSG_PERMISO):
        servicio.execute(document_id=5, requesting_user_id=1)

    ia_mock.analyze.assert_not_called()
    doc_repo_mock.save.assert_not_called()


def test_execute_usa_cache_si_hay_analysis_result_y_no_force_refresh(
    servicio: AnalyzeDocumentService,
    doc_repo_mock: MagicMock,
    ia_mock: MagicMock,
) -> None:
    """Con resumen ya guardado, se devuelve análisis sintético sin invocar al puerto `IAAnalyst`."""
    doc = _documento(analysis_result="Resumen ya persistido.")
    doc_repo_mock.find_by_id.return_value = doc

    out = servicio.execute(5, requesting_user_id=1, force_refresh=False)

    ia_mock.analyze.assert_not_called()
    doc_repo_mock.save.assert_not_called()
    assert out.summary == "Resumen ya persistido."
    assert out.key_concepts == []
    assert out.suggested_questions == []
    assert out.model_used == "cached"


def test_execute_force_refresh_llama_ia_aunque_exista_cache(
    servicio: AnalyzeDocumentService,
    doc_repo_mock: MagicMock,
    ia_mock: MagicMock,
) -> None:
    """`force_refresh=True` ignora `analysis_result` y vuelve a consultar a la IA."""
    doc = _documento(analysis_result="Viejo")
    doc_repo_mock.find_by_id.return_value = doc
    nuevo = Analysis(
        id=None,
        document_id=5,
        summary="Nuevo desde IA",
        key_concepts=["x"],
        suggested_questions=["y?"],
        model_used="m",
        created_at=datetime.now(UTC),
    )
    ia_mock.analyze.return_value = nuevo
    doc_repo_mock.save.side_effect = lambda d: d

    out = servicio.execute(5, requesting_user_id=1, force_refresh=True)

    ia_mock.analyze.assert_called_once_with(doc)
    assert out.summary == "Nuevo desde IA"
    doc_repo_mock.save.assert_called_once()


def test_answer_question_pasa_contexto_y_pregunta_a_ia(
    servicio: AnalyzeDocumentService,
    doc_repo_mock: MagicMock,
    ia_mock: MagicMock,
) -> None:
    doc = _documento()
    doc_repo_mock.find_by_id.return_value = doc
    ia_mock.answer_question.return_value = "Respuesta corta."

    resp = servicio.answer_question(5, "¿Qué es la fotosíntesis?", requesting_user_id=1)

    assert resp == "Respuesta corta."
    ia_mock.answer_question.assert_called_once_with(
        context=doc.content,
        question="¿Qué es la fotosíntesis?",
    )


def test_answer_question_permiso_denegado(
    servicio: AnalyzeDocumentService,
    doc_repo_mock: MagicMock,
    ia_mock: MagicMock,
) -> None:
    doc = _documento(owner_id=50)
    doc_repo_mock.find_by_id.return_value = doc

    with pytest.raises(PermissionError, match=_MSG_PERMISO):
        servicio.answer_question(5, "pregunta", requesting_user_id=1)

    ia_mock.answer_question.assert_not_called()


def test_generate_quiz_propaga_numero_de_preguntas(
    servicio: AnalyzeDocumentService,
    doc_repo_mock: MagicMock,
    ia_mock: MagicMock,
) -> None:
    doc = _documento()
    doc_repo_mock.find_by_id.return_value = doc
    ia_mock.generate_quiz.return_value = ["P1", "P2", "P3"]

    preguntas = servicio.generate_quiz(5, requesting_user_id=1, num_questions=3)

    assert preguntas == ["P1", "P2", "P3"]
    ia_mock.generate_quiz.assert_called_once_with(doc, 3)


def test_generate_quiz_permiso_denegado(
    servicio: AnalyzeDocumentService,
    doc_repo_mock: MagicMock,
    ia_mock: MagicMock,
) -> None:
    doc = _documento(owner_id=2)
    doc_repo_mock.find_by_id.return_value = doc

    with pytest.raises(PermissionError, match=_MSG_PERMISO):
        servicio.generate_quiz(5, requesting_user_id=99)

    ia_mock.generate_quiz.assert_not_called()


def test_procesamiento_respuesta_execute_devuelve_estructura_de_dominio(
    servicio: AnalyzeDocumentService,
    doc_repo_mock: MagicMock,
    ia_mock: MagicMock,
) -> None:
    """Comprueba que el objeto `Analysis` devuelto conserva conceptos y preguntas sugeridas del mock."""
    doc_repo_mock.find_by_id.return_value = _documento()
    ia_mock.analyze.return_value = Analysis(
        id=None,
        document_id=5,
        summary="S",
        key_concepts=["a", "b"],
        suggested_questions=["q1"],
        model_used="x",
        created_at=datetime.now(UTC),
    )
    doc_repo_mock.save.side_effect = lambda d: d

    out = servicio.execute(5, requesting_user_id=1)

    assert out.key_concepts == ["a", "b"]
    assert out.suggested_questions == ["q1"]
    assert out.model_used == "x"
