"""Borrar una cuenta de Clerk (ADR-041).

Antes era imposible (pedía contraseña o Google, y una cuenta de Clerk no tiene
ninguna) y, de haberse podido, la cuenta se recreaba sola: la sesión de Clerk seguía
viva y la siguiente petición creaba un usuario nuevo, vacío.
"""
import asyncio

import httpx
import pytest

from src.domain.value_objects.email import Email
from src.infrastructure.mongodb.user_repository import MongoDBUserRepository
from src.interfaces.api import dependencies as deps
from tests.api.test_sesion_clerk import _alta, _h, _tok, entorno  # noqa: F401


def _con_borrado(clerk, falla=False):
    clerk.borrados = []

    async def delete_user(user_id):
        if falla:
            raise httpx.ConnectError("Clerk caído")
        clerk.borrados.append(user_id)
        clerk.usuarios.pop(user_id, None)

    async def get_user(user_id, _orig=clerk.get_user):
        if user_id not in clerk.usuarios:
            # Como la API real: un usuario borrado da 404.
            raise httpx.HTTPStatusError("404", request=httpx.Request("GET", "x"), response=httpx.Response(404))
        return await _orig(user_id)

    clerk.delete_user = delete_user
    clerk.get_user = get_user


def test_se_borra_con_una_verificacion_reciente_y_no_vuelve_a_crearse(entorno):  # noqa: F811
    c, clerk = entorno
    _con_borrado(clerk)
    sub = _alta(clerk, "ana@example.com")
    yo = c.get("/api/v1/users/me", headers=_h(_tok(sub))).json()
    c.post("/api/v1/chats/", headers=_h(_tok(sub)), json={"title": "mío"})

    r = c.request("DELETE", "/api/v1/users/me", headers=_h(_tok(sub, fva=(2, -1))), json={})

    assert r.status_code == 204, r.text
    assert clerk.borrados == [sub]
    # El mismo token sigue firmado unos segundos: no recrea la cuenta ni ve datos.
    otra = c.get("/api/v1/users/me", headers=_h(_tok(sub)))
    assert otra.status_code in (401, 503)
    usuarios = asyncio.run(deps.get_user_repo().find_by_email(Email("ana@example.com")))
    assert usuarios is None, "la cuenta borrada no debe recrearse"
    assert yo["id"]


def test_sin_verificacion_reciente_pide_reverificar_y_no_borra(entorno):  # noqa: F811
    c, clerk = entorno
    _con_borrado(clerk)
    sub = _alta(clerk, "bea@example.com")
    for fva in ((45, -1), (-1, -1)):  # hace 45 min, o el token no lo dice
        r = c.request("DELETE", "/api/v1/users/me", headers=_h(_tok(sub, fva=fva)), json={})
        assert r.status_code == 403
        assert r.json()["reason"] == "reverification_required"
    assert clerk.borrados == []
    assert c.get("/api/v1/users/me", headers=_h(_tok(sub))).status_code == 200


def test_si_clerk_falla_no_se_borra_nada_y_se_puede_reintentar(entorno):  # noqa: F811
    c, clerk = entorno
    _con_borrado(clerk, falla=True)
    sub = _alta(clerk, "cris@example.com")
    c.post("/api/v1/chats/", headers=_h(_tok(sub)), json={"title": "mío"})

    r = c.request("DELETE", "/api/v1/users/me", headers=_h(_tok(sub, fva=(1, -1))), json={})

    assert r.status_code == 503 and "No se borró nada" in r.json()["detail"]
    # Sigue activa y con sus datos.
    assert c.get("/api/v1/users/me", headers=_h(_tok(sub))).status_code == 200
    assert len(c.get("/api/v1/chats/", headers=_h(_tok(sub))).json()) >= 1


def test_quien_entra_con_clerk_con_el_correo_en_otra_mayuscula_es_la_misma_cuenta(entorno):  # noqa: F811
    c, clerk = entorno
    alta = c.post("/api/v1/auth/register", json={"username": "dani", "email": "Dani@Example.com", "password": "Clave123"})
    assert alta.status_code == 201, alta.text
    sub = _alta(clerk, "dani@example.com")
    yo = c.get("/api/v1/users/me", headers=_h(_tok(sub))).json()
    assert yo["username"] == "dani" and yo["email"] == "dani@example.com"


def test_el_correo_se_normaliza():
    assert Email("  Ana.Perez@Example.COM ").value == "ana.perez@example.com"


@pytest.mark.asyncio
async def test_en_mongo_una_cuenta_guardada_con_mayusculas_se_encuentra():
    from mongomock_motor import AsyncMongoMockClient

    db = AsyncMongoMockClient()["t"]
    await db.users.insert_one({"_id": "00000000-0000-0000-0000-000000000001", "username": "eva", "email": "Eva@Example.com",
                               "hashed_password": "x", "role": "student", "is_active": True,
                               "created_at": __import__("datetime").datetime(2026, 1, 1)})
    repo = MongoDBUserRepository(database=db)
    encontrado = await repo.find_by_email(Email("eva@example.com"))
    assert encontrado is not None and encontrado.username == "eva"
    assert await repo.find_by_email(Email("eva.x@example.com")) is None
