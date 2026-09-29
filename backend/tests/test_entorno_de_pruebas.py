"""La suite no habla con servicios externos ni depende del `.env` de nadie.

Este archivo existe por un fallo real: se añadió el ajuste `ORIGINAL_STORAGE`
sin neutralizarlo en `conftest.py`, así que la suite empezó a usar el Cloudflare
R2 del desarrollador **por red**. Estaba en verde —pasaba porque la red
respondía— y reventó en la máquina de al lado, que no tenía `boto3`: `/ready`
devolvía 503 y el `pre-push` bloqueó el push.

Un ajuste nuevo que se cuele desde `.env` ahora falla aquí, que es barato, en
vez de en el push de otro, que no lo es.
"""
from __future__ import annotations


def test_los_backends_son_locales():
    from src.infrastructure.config import settings

    assert settings.DB_PROVIDER == "memory"
    assert settings.EVENT_BUS_BACKEND == "memory"
    assert settings.RATE_LIMIT_BACKEND == "memory"
    assert settings.CACHE_BACKEND == "memory"


def test_ningun_almacen_externo_esta_activo():
    """Los archivos originales se quedan en el blob local: ni R2 ni boto3."""
    from src.infrastructure.config import settings

    assert settings.ORIGINAL_STORAGE == "blob"
    assert settings.R2_ENDPOINT_URL == ""
    assert settings.R2_BUCKET == ""
    assert settings.R2_ACCESS_KEY_ID == ""
    assert settings.R2_SECRET_ACCESS_KEY == ""


def test_el_adaptador_de_originales_es_el_local():
    from src.interfaces.api.dependencies import get_original_blob_store

    assert type(get_original_blob_store()).__name__ == "InMemoryDocumentBlobStore"


def test_ready_no_depende_de_servicios_externos():
    """El síntoma exacto que bloqueó el push: `/ready` devolvía 503."""
    from fastapi.testclient import TestClient

    from src.main import app

    with TestClient(app) as client:
        resp = client.get("/ready")

    assert resp.status_code == 200, resp.text
    assert resp.json()["checks"]["storage"] == "blob"
