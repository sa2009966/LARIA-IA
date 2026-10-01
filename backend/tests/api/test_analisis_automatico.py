"""Al subir un documento se analiza solo; y si no, el primer turno o quiz lo asegura (ADR-029).

Antes el análisis solo ocurría si el cliente llamaba a /analyze, y el cliente
nunca lo hacía: en producción había documentos subidos desde el chat sin resumen
ni conceptos, y el tutor trabajaba a ciegas sobre el material.
"""
from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.application.services.analyze_document_service import AnalyzeDocumentService
from src.domain.aggregates.document_aggregate import DocumentAggregate, DocumentStatus
from src.domain.value_objects.analysis_result import AnalysisResult
from src.infrastructure.config import settings
from src.infrastructure.persistence.in_memory_document_repo import InMemoryDocumentRepository
from src.interfaces.api import dependencies as deps
from src.main import app
from tests.conftest import clear_dependency_caches


class AnalistaFalso:
    def __init__(self, falla=False):
        self.llamadas = 0
        self.falla = falla

    async def analyze(self, document):
        self.llamadas += 1
        if self.falla:
            raise RuntimeError("caído")
        return AnalysisResult(summary="Resumen del libro.", key_concepts=["célula", "mitosis"])


@pytest.fixture
def client(monkeypatch):
    clear_dependency_caches()
    monkeypatch.setattr(settings, "AUTO_ANALYZE_UPLOAD", True)
    analista = AnalistaFalso()
    app.dependency_overrides[deps.get_analyze_service] = lambda: AnalyzeDocumentService(
        document_repository=deps.get_document_repo(), ia_analyst=analista
    )
    with TestClient(app) as c:
        yield c, analista
    app.dependency_overrides.clear()
    clear_dependency_caches()


def _h(c):
    s = uuid4().hex[:8]
    e = f"a_{s}@example.com"
    c.post("/api/v1/auth/register", json={"username": f"a_{s}", "email": e, "password": "Clave123"})
    return {"Authorization": "Bearer " + c.post("/api/v1/auth/token", data={"username": e, "password": "Clave123"}).json()["access_token"]}


@pytest.mark.parametrize("ruta", ["multipart", "json"])
def test_subir_un_documento_lo_analiza_sin_pedirlo(client, ruta):
    c, analista = client
    h = _h(c)
    if ruta == "multipart":
        r = c.post("/api/v1/documents/upload", headers=h, files={"file": ("a.txt", "La célula se divide por mitosis. " * 30, "text/plain")})
    else:
        r = c.post("/api/v1/documents/", headers=h, json={"filename": "a.txt", "content": "La célula se divide. " * 30})
    assert r.status_code == 201

    doc = c.get(f"/api/v1/documents/{r.json()['id']}", headers=h).json()

    assert analista.llamadas == 1
    assert doc["has_analysis"] is True and doc["status"] == "analyzed"


def test_con_el_interruptor_apagado_no_se_analiza(client, monkeypatch):
    c, analista = client
    monkeypatch.setattr(settings, "AUTO_ANALYZE_UPLOAD", False)
    h = _h(c)

    c.post("/api/v1/documents/upload", headers=h, files={"file": ("a.txt", "Texto de prueba. " * 30, "text/plain")})

    assert analista.llamadas == 0


# --- Respaldo: ensure_analysis -----------------------------------------------------------


def _servicio(analista):
    repo = InMemoryDocumentRepository()
    return AnalyzeDocumentService(document_repository=repo, ia_analyst=analista), repo


@pytest.mark.asyncio
async def test_un_documento_sin_analisis_se_analiza_antes_de_usarlo():
    analista = AnalistaFalso()
    servicio, repo = _servicio(analista)
    owner = uuid4()
    doc = DocumentAggregate.upload(owner, "a.txt", "Texto. " * 50, "Biología")
    await repo.save(doc)

    listo = await servicio.ensure_analysis(doc, owner)

    assert listo.has_analysis() and listo.analysis_result.key_concepts == ["célula", "mitosis"]


@pytest.mark.asyncio
async def test_un_analisis_en_curso_reciente_no_se_duplica():
    analista = AnalistaFalso()
    servicio, repo = _servicio(analista)
    owner = uuid4()
    doc = DocumentAggregate.upload(owner, "a.txt", "Texto. " * 50, "Biología")
    doc.mark_analyzing()
    await repo.save(doc)

    await servicio.ensure_analysis(doc, owner)

    assert analista.llamadas == 0, "se pagaría dos veces"


@pytest.mark.asyncio
async def test_un_analisis_en_curso_viejo_se_da_por_perdido_y_se_repite():
    analista = AnalistaFalso()
    servicio, repo = _servicio(analista)
    owner = uuid4()
    doc = DocumentAggregate.upload(owner, "a.txt", "Texto. " * 50, "Biología")
    doc.mark_analyzing()
    doc.uploaded_at = doc.uploaded_at - timedelta(minutes=30)
    await repo.save(doc)

    listo = await servicio.ensure_analysis(doc, owner)

    assert analista.llamadas == 1 and listo.has_analysis()


@pytest.mark.asyncio
async def test_si_el_analisis_falla_el_turno_sigue_con_el_texto():
    servicio, repo = _servicio(AnalistaFalso(falla=True))
    owner = uuid4()
    doc = DocumentAggregate.upload(owner, "a.txt", "Texto. " * 50, "Biología")
    await repo.save(doc)

    listo = await servicio.ensure_analysis(doc, owner)

    assert listo is doc and not listo.has_analysis()
