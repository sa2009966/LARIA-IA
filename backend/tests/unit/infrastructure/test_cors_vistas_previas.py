"""Orígenes por patrón para las vistas previas de Vercel.

Cada PR del frontend tiene una URL distinta, así que no caben en CORS_ORIGINS:
sin esto, en las vistas previas no se podía iniciar sesión y no servían para
revisar. Pero un patrón mal escrito abre la API sin avisar, así que se valida
al arrancar y la app no arranca si deja pasar orígenes ajenos.
"""
import re

import pytest
from starlette.middleware.cors import CORSMiddleware

from src.infrastructure.config import Settings, _validate_cors_regex, validate_security_settings

PROYECTO = r"^https://laria-[a-z0-9-]+-ricardoalfredoaguilar1-gmailcoms-projects\.vercel\.app$"


def test_el_patron_del_proyecto_acepta_sus_vistas_previas():
    _validate_cors_regex(PROYECTO)
    for origen in (
        "https://laria-git-fix-597bdd-ricardoalfredoaguilar1-gmailcoms-projects.vercel.app",
        "https://laria-abc123def-ricardoalfredoaguilar1-gmailcoms-projects.vercel.app",
    ):
        assert re.fullmatch(PROYECTO, origen), origen


def test_no_acepta_otros_proyectos_de_vercel():
    for origen in ("https://laria-git-x-otra-persona-projects.vercel.app", "https://otro.vercel.app"):
        assert not re.fullmatch(PROYECTO, origen), origen


def test_sin_anclas_no_arranca():
    """Sin ^…$, 'https://laria-frontend.vercel.app.evil.com' también encajaría."""
    with pytest.raises(RuntimeError, match="anclado"):
        _validate_cors_regex(r"https://.*\.vercel\.app")


@pytest.mark.parametrize("patron", [r"^https://.*\.vercel\.app$", r"^https://laria.*$", r"^.*$"])
def test_un_patron_demasiado_amplio_no_arranca(patron):
    with pytest.raises(RuntimeError, match="demasiado amplio"):
        _validate_cors_regex(patron)


def test_un_patron_invalido_no_arranca():
    with pytest.raises(RuntimeError, match="no es una expresión válida"):
        _validate_cors_regex(r"^https://(laria$")


def test_la_validacion_corre_al_arrancar_en_cualquier_entorno():
    """No solo en producción: un patrón abierto en una preview también es un problema."""
    s = Settings(SECRET_KEY="x" * 40, CORS_ORIGIN_REGEX=r"^https://.*\.vercel\.app$")

    with pytest.raises(RuntimeError, match="demasiado amplio"):
        validate_security_settings(s)


def test_vacio_desactiva_el_patron():
    validate_security_settings(Settings(SECRET_KEY="x" * 40, CORS_ORIGIN_REGEX=""))


def test_el_middleware_recibe_el_patron():
    """Que el ajuste exista no sirve de nada si no llega al middleware."""
    from src.main import app

    cors = next(m for m in app.user_middleware if m.cls is CORSMiddleware)
    assert "allow_origin_regex" in cors.kwargs
