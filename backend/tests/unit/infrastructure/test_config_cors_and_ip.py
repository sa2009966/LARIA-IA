"""Ramas de _parse_cors_origins y _client_ip con peer inválido."""
from __future__ import annotations

import pytest
from starlette.requests import Request

from src.infrastructure.config import Settings, _parse_cors_origins, validate_ia_settings, validate_runtime_settings
from src.infrastructure.config import settings as app_settings
from src.infrastructure.rate_limit import _client_ip


def test_parse_cors_none_and_empty():
    assert _parse_cors_origins(None) == []
    assert _parse_cors_origins("") == []
    assert _parse_cors_origins("   ") == []


def test_parse_cors_list_and_csv():
    assert _parse_cors_origins([" https://a.example/ ", "", "https://b.example"]) == [
        "https://a.example",
        "https://b.example",
    ]
    assert _parse_cors_origins("https://a.example, https://b.example/") == [
        "https://a.example",
        "https://b.example",
    ]


def test_parse_cors_json_array_and_broken_brackets():
    assert _parse_cors_origins('["https://a.example","https://b.example"]') == [
        "https://a.example",
        "https://b.example",
    ]
    # JSON inválido → fallback CSV quitando corchetes
    assert "https://a.example" in _parse_cors_origins('["https://a.example"')
    # JSON objeto (no lista) → se convierte a texto y se parte por CSV
    assert isinstance(_parse_cors_origins('{"not":"list"}'), list)


def test_validate_ia_rejects_non_openai():
    s = Settings(
        _env_file=None,
        SECRET_KEY="a" * 64,
        OPENAI_API_KEY="sk-test",
        IA_PROVIDER="kimi",
    )
    with pytest.raises(RuntimeError, match="no soportado"):
        validate_ia_settings(s)


def test_validate_ia_rejects_empty_key():
    s = Settings(
        _env_file=None,
        SECRET_KEY="a" * 64,
        OPENAI_API_KEY="  ",
        IA_PROVIDER="openai",
    )
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        validate_ia_settings(s)


def test_validate_runtime_rejects_bad_app_env():
    s = Settings(
        _env_file=None,
        SECRET_KEY="a" * 64,
        OPENAI_API_KEY="sk-test",
        APP_ENV="staging",
    )
    with pytest.raises(RuntimeError, match="APP_ENV"):
        validate_runtime_settings(s)


def test_client_ip_invalid_peer_with_trusted_proxies(monkeypatch):
    monkeypatch.setattr(app_settings, "TRUSTED_PROXIES", "10.0.0.0/8")
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [(b"x-forwarded-for", b"9.9.9.9")],
        "client": ("not-an-ip", 1234),
    }
    assert _client_ip(Request(scope)) == "not-an-ip"


def test_client_ip_trusted_cidr_uses_xff(monkeypatch):
    monkeypatch.setattr(app_settings, "TRUSTED_PROXIES", "10.0.0.0/8")
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [(b"x-forwarded-for", b"8.8.8.8")],
        "client": ("10.1.2.3", 1234),
    }
    assert _client_ip(Request(scope)) == "8.8.8.8"
