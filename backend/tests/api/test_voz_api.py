"""POST /speech: leer en voz alta un trozo de la respuesta del tutor (ADR-026)."""
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.domain.ports.embodiment import AffectState, TextToSpeechPort
from src.infrastructure.config import settings
from src.interfaces.api import dependencies as deps
from src.main import app
from tests.conftest import clear_dependency_caches


class VozFalsa(TextToSpeechPort):
    def __init__(self, falla=False):
        self.recibido = []
        self.falla = falla

    async def stream(self, text, affect):
        from src.infrastructure.embodiment.openai_tts import VoiceUnavailable

        self.recibido.append((text, affect))
        if self.falla:
            raise VoiceUnavailable("caída")
        yield b"ID3"
        yield b"mp3"

    async def synthesize(self, text, affect):
        return b"ID3mp3"


@pytest.fixture
def voz():
    return VozFalsa()


@pytest.fixture
def client(voz, monkeypatch):
    clear_dependency_caches()
    monkeypatch.setattr(settings, "TTS_ENABLED", True)
    app.dependency_overrides[deps.get_text_to_speech] = lambda: voz
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    clear_dependency_caches()


def _h(c):
    s = uuid4().hex[:8]
    email = f"v_{s}@example.com"
    c.post("/api/v1/auth/register", json={"username": f"v_{s}", "email": email, "password": "Clave123"})
    return {"Authorization": "Bearer " + c.post("/api/v1/auth/token", data={"username": email, "password": "Clave123"}).json()["access_token"]}


def test_devuelve_mp3_del_texto_hablable_con_el_tono_del_envelope(client, voz):
    r = client.post("/api/v1/speech", headers=_h(client), json={"text": "La **célula** es \\(\\frac{1}{2}\\).", "emotion": "patient"})

    assert r.status_code == 200 and r.headers["content-type"] == "audio/mpeg"
    assert r.content == b"ID3mp3"
    texto, afecto = voz.recibido[0]
    assert "**" not in texto and "frac" not in texto and "célula" in texto
    assert afecto == AffectState.PATIENT


def test_solo_codigo_no_tiene_nada_que_leer_salvo_el_aviso(client, voz):
    r = client.post("/api/v1/speech", headers=_h(client), json={"text": "```\nx=1\n```"})

    assert r.status_code == 200 and "código en pantalla" in voz.recibido[0][0]


def test_demasiado_largo_se_pide_por_partes(client, monkeypatch):
    monkeypatch.setattr(settings, "TTS_MAX_CHARS", 20)

    r = client.post("/api/v1/speech", headers=_h(client), json={"text": "Una frase bastante más larga que veinte."})
    assert r.status_code == 422


def test_si_el_proveedor_falla_es_503_con_json(client):
    app.dependency_overrides[deps.get_text_to_speech] = lambda: VozFalsa(falla=True)

    r = client.post("/api/v1/speech", headers=_h(client), json={"text": "Hola."})
    assert r.status_code == 503 and "no está disponible" in r.json()["detail"]


def test_apagada_es_503_y_config_lo_dice(client, monkeypatch):
    monkeypatch.setattr(settings, "TTS_ENABLED", False)

    assert client.get("/api/v1/speech/config").json()["enabled"] is False
    assert client.post("/api/v1/speech", headers=_h(client), json={"text": "Hola."}).status_code == 503


def test_sin_sesion_es_401(client):
    assert client.post("/api/v1/speech", json={"text": "Hola."}).status_code == 401
