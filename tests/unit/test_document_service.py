"""Pruebas unitarias de `DocumentService`.

El puerto `DocumentRepository` se sustituye por un `MagicMock`: no hay sesión
SQLAlchemy ni motor MySQL. Verificamos la construcción de la entidad `Document`
y las reglas de negocio sobre `owner_id` al eliminar.
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from src.application.services.document_service import DocumentService
from src.domain.entities.document import Document


@pytest.fixture
def repo_mock() -> MagicMock:
    """Mock del repositorio de documentos (adaptador de persistencia simulado)."""
    return MagicMock()


@pytest.fixture
def servicio(repo_mock: MagicMock) -> DocumentService:
    return DocumentService(repo_mock)


def test_upload_crea_documento_con_owner_id(servicio: DocumentService, repo_mock: MagicMock) -> None:
    """Al subir, el servicio fija `owner_id` del JWT simulado y delega el `save` al mock."""

    def save_side_effect(doc: Document) -> Document:
        # Simulamos que la BD asigna un id autoincremental tras insertar.
        doc.id = 10
        return doc

    repo_mock.save.side_effect = save_side_effect

    resultado = servicio.upload(owner_id=7, filename="nota.txt", content="texto", subject="Matemáticas")

    assert resultado.owner_id == 7
    assert resultado.id == 10
    repo_mock.save.assert_called_once()
    pasado = repo_mock.save.call_args[0][0]
    assert pasado.owner_id == 7
    assert pasado.filename == "nota.txt"
    assert pasado.content == "texto"
    assert pasado.subject == "Matemáticas"


def test_get_by_id_lanza_si_no_existe(servicio: DocumentService, repo_mock: MagicMock) -> None:
    repo_mock.find_by_id.return_value = None

    with pytest.raises(ValueError, match="Documento con id=42 no encontrado"):
        servicio.get_by_id(42, requesting_user_id=1)


def test_get_by_id_denegado_si_owner_no_coincide_con_solicitante(
    servicio: DocumentService,
    repo_mock: MagicMock,
) -> None:
    """Solo el propietario puede obtener el documento por id; otro usuario recibe `PermissionError`."""
    doc = Document(
        id=3,
        owner_id=100,
        filename="f.txt",
        content="cuerpo",
        subject="Física",
        uploaded_at=datetime.now(UTC),
    )
    repo_mock.find_by_id.return_value = doc

    with pytest.raises(PermissionError, match="No tienes permiso para ver este documento"):
        servicio.get_by_id(document_id=3, requesting_user_id=999)


def test_list_by_owner_delega_filtro(servicio: DocumentService, repo_mock: MagicMock) -> None:
    docs = [
        Document(
            id=1,
            owner_id=5,
            filename="a.pdf",
            content="x",
            subject="Historia",
            uploaded_at=datetime.now(UTC),
        )
    ]
    repo_mock.find_by_owner.return_value = docs

    assert servicio.list_by_owner(5) == docs
    repo_mock.find_by_owner.assert_called_once_with(5)


def test_delete_permite_solo_al_propietario(servicio: DocumentService, repo_mock: MagicMock) -> None:
    """Regla de pertenencia: `requesting_user_id` debe coincidir con `owner_id` del documento."""
    doc = Document(
        id=3,
        owner_id=100,
        filename="f.txt",
        content="cuerpo",
        subject="Física",
        uploaded_at=datetime.now(UTC),
    )
    repo_mock.find_by_id.return_value = doc

    servicio.delete(document_id=3, requesting_user_id=100)

    repo_mock.delete.assert_called_once_with(3)


def test_delete_denegado_si_otro_usuario(servicio: DocumentService, repo_mock: MagicMock) -> None:
    doc = Document(
        id=3,
        owner_id=100,
        filename="f.txt",
        content="cuerpo",
        subject="Física",
        uploaded_at=datetime.now(UTC),
    )
    repo_mock.find_by_id.return_value = doc

    with pytest.raises(PermissionError, match="No tienes permiso"):
        servicio.delete(document_id=3, requesting_user_id=999)

    repo_mock.delete.assert_not_called()
