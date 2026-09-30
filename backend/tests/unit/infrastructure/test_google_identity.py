"""Verificación del ID token de Google: firma, audiencia, emisor, caducidad y correo."""
import time
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from src.domain.ports.external_identity import InvalidExternalToken
from src.infrastructure.security.google_identity import GoogleIdentityVerifier

CLIENT = "123-abc.apps.googleusercontent.com"
CLAVE = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTRA = rsa.generate_private_key(public_exponent=65537, key_size=2048)


class JwksFalso:
    def get_signing_key_from_jwt(self, token):
        return SimpleNamespace(key=CLAVE.public_key())


def _token(clave=CLAVE, **cambios):
    ahora = int(time.time())
    claims = {"iss": "https://accounts.google.com", "aud": CLIENT, "sub": "g-1",
              "email": "Ana@Gmail.com", "email_verified": True, "name": "Ana",
              "iat": ahora, "exp": ahora + 600, **cambios}
    claims = {k: v for k, v in claims.items() if v is not None}
    return jwt.encode(claims, clave, algorithm="RS256")


def _v(client=CLIENT):
    return GoogleIdentityVerifier(client, jwks_client=JwksFalso())


@pytest.mark.asyncio
async def test_un_token_valido_da_la_identidad():
    i = await _v().verify(_token())

    assert (i.subject, i.email, i.name) == ("g-1", "ana@gmail.com", "Ana")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "token",
    [
        pytest.param(_token(aud="otra-app.apps.googleusercontent.com"), id="token de otra app"),
        pytest.param(_token(iss="https://evil.example"), id="emisor ajeno"),
        pytest.param(_token(exp=int(time.time()) - 3600), id="caducado"),
        pytest.param(_token(email_verified=False), id="correo sin verificar"),
        pytest.param(_token(email=None), id="sin correo"),
        pytest.param(_token(clave=OTRA), id="firmado por otra clave"),
        pytest.param("no.es.jwt", id="basura"),
    ],
)
async def test_lo_invalido_se_rechaza(token):
    with pytest.raises(InvalidExternalToken):
        await _v().verify(token)


@pytest.mark.asyncio
async def test_sin_client_id_esta_apagado():
    with pytest.raises(InvalidExternalToken, match="no está configurado"):
        await _v(client="").verify(_token())
