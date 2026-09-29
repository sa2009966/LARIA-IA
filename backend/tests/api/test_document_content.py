"""GET /documents/{id}/content: el archivo tal como se subió.

El visor de archivos del cliente depende de este endpoint y no existía: ningún
PDF podía mostrarse, ni los archivos de un chat antiguo tras recargar.

La especificación del cliente (`docs/BACKEND_ENDPOINT_SPEC.md`) se siguió con tres
correcciones, y cada una tiene aquí el test que la hace exigible:

1. **404, no 403**, para documentos ajenos: un 403 confirma que el id existe.
2. **Un `.html` subido no se sirve como HTML.** Se aceptan como subida, y servido
   inline desde el dominio de la API ejecutaría su `<script>` con el origen del
   backend: XSS almacenado.
3. **El nombre del archivo no rompe la cabecera**: comillas, saltos de línea y
   tildes van codificados.
"""
from __future__ import annotations

from io import BytesIO
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.application.services.document_service import DocumentService
from src.domain.aggregates.document_aggregate import DocumentAggregate
from src.infrastructure.persistence.in_memory_document_blob_store import (
    InMemoryDocumentBlobStore,
)
from src.infrastructure.persistence.in_memory_document_repo import InMemoryDocumentRepository
from src.main import app
from tests.conftest import clear_dependency_caches


@pytest.fixture
def client():
    clear_dependency_caches()
    app.dependency_overrides.clear()
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    clear_dependency_caches()


def _auth(client: TestClient) -> dict:
    s = uuid4().hex[:8]
    email = f"content_{s}@example.com"
    client.post(
        "/api/v1/auth/register",
        json={"username": f"content_{s}", "email": email, "password": "SecurePass1x"},
    )
    r = client.post("/api/v1/auth/token", data={"username": email, "password": "SecurePass1x"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _subir(client, headers, nombre: str, datos: bytes, tipo="text/plain") -> str:
    r = client.post(
        "/api/v1/documents/upload",
        headers=headers,
        files={"file": (nombre, BytesIO(datos), tipo)},
        data={"subject": "Matemática"},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


# --- Lo básico -----------------------------------------------------------------------


def test_el_dueno_recibe_los_bytes_exactos(client: TestClient):
    headers = _auth(client)
    datos = "Una variable es un valor desconocido. Ñandú, acción.".encode("utf-8")
    doc = _subir(client, headers, "nota.txt", datos)

    r = client.get(f"/api/v1/documents/{doc}/content", headers=headers)

    assert r.status_code == 200
    assert r.content == datos
    assert r.headers["content-type"].startswith("text/plain")
    assert r.headers["content-length"] == str(len(datos))
    assert r.headers["cache-control"] == "private, max-age=3600"
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["content-disposition"].startswith("inline;")


def test_sin_token_es_401(client: TestClient):
    headers = _auth(client)
    doc = _subir(client, headers, "nota.txt", b"hola")

    assert client.get(f"/api/v1/documents/{doc}/content").status_code == 401


def test_un_documento_ajeno_es_404_no_403(client: TestClient):
    """Un 403 confirmaría que ese id existe: se responde igual que si no existiera."""
    doc = _subir(client, _auth(client), "nota.txt", b"de otra persona")

    r = client.get(f"/api/v1/documents/{doc}/content", headers=_auth(client))

    assert r.status_code == 404


def test_un_id_inexistente_es_404(client: TestClient):
    r = client.get(f"/api/v1/documents/{uuid4()}/content", headers=_auth(client))

    assert r.status_code == 404


# --- Seguridad -----------------------------------------------------------------------


def test_un_html_subido_no_se_sirve_como_html(client: TestClient):
    """El XSS que la especificación no contemplaba.

    `.html` es una subida aceptada, y su tipo natural es `text/html`. Servido
    inline desde el dominio de la API, el `<script>` correría con el origen del
    backend y podría leer lo que ese origen puede leer.
    """
    headers = _auth(client)
    malicioso = b"<html><script>fetch('/api/v1/users/me')</script></html>"
    doc = _subir(client, headers, "apuntes.html", malicioso, tipo="text/html")

    r = client.get(f"/api/v1/documents/{doc}/content", headers=headers)

    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/plain"), r.headers["content-type"]
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["content-security-policy"] == "sandbox"
    assert r.content == malicioso, "el contenido se sirve intacto: solo cambia cómo"


def test_el_nombre_no_rompe_la_cabecera(client: TestClient):
    """Comillas y tildes: el nombre lo escribe el usuario."""
    headers = _auth(client)
    doc = _subir(client, headers, 'Álgebra "básica".txt', b"x")

    cabecera = client.get(f"/api/v1/documents/{doc}/content", headers=headers).headers[
        "content-disposition"
    ]

    assert "\n" not in cabecera and "\r" not in cabecera
    assert "filename*=UTF-8''%C3%81lgebra" in cabecera
    assert cabecera.count('"') == 2, "una comilla del nombre cerró la cabecera antes de tiempo"


# --- Documentos sin original ---------------------------------------------------------


def test_sin_original_se_sirve_el_texto_extraido(client: TestClient):
    """Documentos anteriores al ADR-012 o creados enviando texto: no hay original,
    pero el visor debe mostrar algo legible en vez de un error."""
    headers = _auth(client)
    r = client.post(
        "/api/v1/documents/",
        headers=headers,
        json={"filename": "resumen.txt", "content": "Texto enviado en JSON.", "subject": "Matemática"},
    )
    doc = r.json()["id"]

    r = client.get(f"/api/v1/documents/{doc}/content", headers=headers)

    assert r.status_code == 200
    assert r.text == "Texto enviado en JSON."
    assert r.headers["content-type"].startswith("text/plain")


# --- A nivel de servicio: lo que HTTP no deja montar fácil ---------------------------


class _AlmacenVacio(InMemoryDocumentBlobStore):
    """Simula R2 recién conectado: no tiene los originales de antes del cambio."""

    async def get(self, blob_id: str) -> bytes:
        raise KeyError(blob_id)


async def _doc_con_original(repo, almacen, owner, nombre, datos, tipo):
    blob = await almacen.put(datos, filename=nombre, content_type=tipo)
    doc = DocumentAggregate.upload(
        owner, nombre, content="texto extraído", subject="Matemática",
        original_blob_id=blob, original_content_type=tipo, original_size=len(datos),
    )
    await repo.save(doc)
    return doc


@pytest.mark.asyncio
async def test_un_pdf_conserva_su_tipo():
    repo, gridfs = InMemoryDocumentRepository(), InMemoryDocumentBlobStore()
    owner = uuid4()
    doc = await _doc_con_original(repo, gridfs, owner, "libro.pdf", b"%PDF-1.4 ...", "application/pdf")
    servicio = DocumentService(document_repository=repo, blob_store=gridfs)

    archivo = await servicio.get_original(doc.id, owner)

    assert archivo.content_type == "application/pdf"
    assert archivo.data == b"%PDF-1.4 ..."


@pytest.mark.asyncio
async def test_lo_subido_antes_de_pasar_a_r2_sigue_accesible():
    """El original de antes del cambio de almacén vive en GridFS, no en R2.

    Sin el segundo intento, todo lo subido antes de conectar R2 daría 404 al
    abrirlo, aunque los bytes siguen estando donde siempre.
    """
    repo, gridfs = InMemoryDocumentRepository(), InMemoryDocumentBlobStore()
    owner = uuid4()
    doc = await _doc_con_original(repo, gridfs, owner, "viejo.pdf", b"%PDF antiguo", "application/pdf")
    servicio = DocumentService(
        document_repository=repo, blob_store=gridfs, original_blob_store=_AlmacenVacio()
    )

    archivo = await servicio.get_original(doc.id, owner)

    assert archivo.data == b"%PDF antiguo"


@pytest.mark.asyncio
async def test_si_el_original_se_perdio_se_sirve_el_texto():
    repo = InMemoryDocumentRepository()
    owner = uuid4()
    doc = DocumentAggregate.upload(
        owner, "perdido.pdf", content="lo que se extrajo", subject="Matemática",
        original_blob_id="no-existe", original_content_type="application/pdf",
    )
    await repo.save(doc)
    servicio = DocumentService(
        document_repository=repo, blob_store=_AlmacenVacio(), original_blob_store=_AlmacenVacio()
    )

    archivo = await servicio.get_original(doc.id, owner)

    assert archivo.data == "lo que se extrajo".encode()
    assert archivo.content_type.startswith("text/plain")
