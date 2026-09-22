"""El tutor lee texto; el alumno descarga su archivo (ADR-012).

Regresión del bug que nadie cubría: `upload_bytes` extraía el texto del PDF,
lo **tiraba**, guardaba el binario en el blob de contenido, y al leerlo para el
análisis se decodificaba como UTF-8. El motor pedagógico —análisis, tutor,
quizzes— trabajaba sobre mojibake para todo PDF, DOCX, XLSX y PPTX.
"""
from uuid import uuid4

import pytest

from src.application.dto.document_dto import UploadDocumentDTO
from src.application.services import document_service as modulo
from src.application.services.document_service import DocumentService
from src.infrastructure.persistence.in_memory_document_blob_store import (
    InMemoryDocumentBlobStore,
)
from src.infrastructure.persistence.in_memory_document_repo import (
    InMemoryDocumentRepository,
)

#: Bytes que NO son UTF-8 válido: es lo que hacía visible el bug.
PDF_FALSO = b"%PDF-1.4\n\x93\x94\xff\xfe binario que no es texto \x00\x01"
TEXTO_EXTRAIDO = "Una variable representa un valor desconocido."


@pytest.fixture
def parser_de_pdf(monkeypatch):
    """Simula la extracción sin depender de un PDF real."""
    monkeypatch.setattr(modulo, "parse_file", lambda filename, data: TEXTO_EXTRAIDO)
    return TEXTO_EXTRAIDO


def _servicio() -> tuple[DocumentService, InMemoryDocumentRepository, InMemoryDocumentBlobStore]:
    texto_store = InMemoryDocumentBlobStore()
    originales = InMemoryDocumentBlobStore()
    repo = InMemoryDocumentRepository(blob_store=texto_store)
    servicio = DocumentService(
        document_repository=repo,
        blob_store=texto_store,
        original_blob_store=originales,
    )
    return servicio, repo, originales


@pytest.mark.asyncio
async def test_el_motor_recibe_el_texto_extraido_no_el_binario(parser_de_pdf):
    servicio, repo, _ = _servicio()

    dto = await servicio.upload_bytes(
        uuid4(), filename="libro.pdf", data=PDF_FALSO, subject="Matemática"
    )

    contenido = await repo.get_content(dto.id)
    assert contenido == TEXTO_EXTRAIDO
    # Lo que rompía: el binario decodificado con caracteres de reemplazo.
    assert "�" not in contenido
    assert "%PDF" not in contenido


@pytest.mark.asyncio
async def test_el_original_se_guarda_intacto_con_su_tipo(parser_de_pdf):
    servicio, repo, originales = _servicio()

    dto = await servicio.upload_bytes(
        uuid4(), filename="libro.pdf", data=PDF_FALSO, subject="Matemática"
    )
    doc = await repo.find_by_id(dto.id)

    assert doc is not None
    assert doc.original_blob_id is not None
    assert doc.original_content_type == "application/pdf"
    assert doc.original_size == len(PDF_FALSO)
    # Byte por byte: es el archivo del estudiante, no una conversión.
    assert await originales.get(doc.original_blob_id) == PDF_FALSO


@pytest.mark.asyncio
async def test_el_texto_plano_no_duplica_almacenamiento():
    """Subir texto por JSON no tiene original que conservar: el texto ya lo es."""
    servicio, repo, originales = _servicio()

    dto = await servicio.upload(
        uuid4(),
        UploadDocumentDTO(filename="nota.txt", content="hola mundo", subject="Matemática"),
    )
    doc = await repo.find_by_id(dto.id)

    assert doc is not None
    assert doc.original_blob_id is None
    assert await repo.get_content(dto.id) == "hola mundo"


@pytest.mark.asyncio
async def test_borrar_el_documento_borra_tambien_el_original(parser_de_pdf):
    servicio, repo, originales = _servicio()
    owner = uuid4()
    dto = await servicio.upload_bytes(
        owner, filename="libro.pdf", data=PDF_FALSO, subject="Matemática"
    )
    doc = await repo.find_by_id(dto.id)
    assert doc is not None and doc.original_blob_id is not None
    blob_original = doc.original_blob_id

    await servicio.delete(dto.id, owner)

    assert await repo.find_by_id(dto.id) is None
    with pytest.raises(KeyError):
        await originales.get(blob_original)


@pytest.mark.asyncio
async def test_sin_almacen_separado_el_original_convive_con_el_texto(parser_de_pdf):
    """Por defecto (sin R2) ambos van al mismo almacén, con claves distintas."""
    store = InMemoryDocumentBlobStore()
    repo = InMemoryDocumentRepository(blob_store=store)
    servicio = DocumentService(document_repository=repo, blob_store=store)

    dto = await servicio.upload_bytes(
        uuid4(), filename="libro.pdf", data=PDF_FALSO, subject="Matemática"
    )
    doc = await repo.find_by_id(dto.id)

    assert doc is not None
    assert doc.original_blob_id != doc.content_blob_id
    assert await store.get(doc.original_blob_id) == PDF_FALSO
    assert await repo.get_content(dto.id) == TEXTO_EXTRAIDO
