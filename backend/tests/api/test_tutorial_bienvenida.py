"""Tutorial de bienvenida (ADR-038): se muestra una vez por cuenta, no por navegador."""
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.infrastructure.mongodb.user_repository import MongoDBUserRepository
from src.main import app
from tests.conftest import clear_dependency_caches


@pytest.fixture
def c():
    clear_dependency_caches()
    with TestClient(app) as cliente:
        yield cliente
    clear_dependency_caches()


def _auth(c):
    s = uuid4().hex[:8]
    email = f"bienvenida_{s}@example.com"
    c.post("/api/v1/auth/register", json={"username": f"b_{s}", "email": email, "password": "Clave123"})
    tok = c.post("/api/v1/auth/token", data={"username": email, "password": "Clave123"}).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


def test_una_cuenta_nueva_ve_el_tutorial_y_al_terminarlo_ya_no(c):
    h = _auth(c)
    assert c.get("/api/v1/users/me", headers=h).json()["onboarding_completed"] is False

    r = c.post("/api/v1/users/me/onboarding", headers=h)
    assert r.status_code == 200 and r.json()["onboarding_completed"] is True
    # Otro dispositivo = otra petición: el dato vive en la cuenta.
    assert c.get("/api/v1/users/me", headers=h).json()["onboarding_completed"] is True
    assert c.post("/api/v1/users/me/onboarding", headers=h).status_code == 200  # idempotente


def test_sin_sesion_no_se_marca(c):
    assert c.post("/api/v1/users/me/onboarding").status_code == 401


def _doc(**extra):
    return {"_id": str(uuid4()), "username": "u", "email": "u@example.com", "hashed_password": "x",
            "role": "student", "is_active": True, "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc), **extra}


def test_en_mongo_una_cuenta_anterior_al_tutorial_no_lo_ve_y_una_nueva_si():
    antigua = MongoDBUserRepository._from_doc(_doc())
    assert antigua.onboarding_completed_at == datetime(2026, 1, 1, tzinfo=timezone.utc)
    nueva = MongoDBUserRepository._from_doc(_doc(onboarding_completed_at=None))
    assert nueva.onboarding_completed_at is None
    nueva.complete_onboarding()
    primera = nueva.onboarding_completed_at
    nueva.complete_onboarding()
    assert nueva.onboarding_completed_at == primera
    assert MongoDBUserRepository._to_doc(nueva)["onboarding_completed_at"] == primera
