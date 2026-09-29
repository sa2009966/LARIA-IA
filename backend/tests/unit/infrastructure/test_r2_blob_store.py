"""El adaptador de R2 cumple el puerto sin hablar con la red.

El cliente de boto3 se sustituye por un doble: lo que se prueba es el contrato
del puerto (claves, `KeyError` cuando no existe, idempotencia del borrado), no
la librería de Amazon.
"""
from __future__ import annotations

import pytest

from src.infrastructure.storage.r2_document_blob_store import R2DocumentBlobStore


class _SinClave(Exception):
    """Equivalente a `client.exceptions.NoSuchKey` de botocore."""


class _Excepciones:
    NoSuchKey = _SinClave


class _Cuerpo:
    def __init__(self, data: bytes) -> None:
        self._data = data

    def read(self) -> bytes:
        return self._data


class ClienteFalso:
    exceptions = _Excepciones()

    def __init__(self) -> None:
        self.objetos: dict[str, dict] = {}
        self.borrados: list[str] = []
        self.head_calls = 0

    def put_object(self, *, Bucket, Key, Body, ContentType, Metadata=None):  # noqa: N803
        self.objetos[Key] = {
            "bucket": Bucket,
            "body": Body,
            "content_type": ContentType,
            "metadata": Metadata or {},
        }

    def get_object(self, *, Bucket, Key):  # noqa: N803
        if Key not in self.objetos:
            raise _SinClave(Key)
        return {"Body": _Cuerpo(self.objetos[Key]["body"])}

    def delete_object(self, *, Bucket, Key):  # noqa: N803
        self.borrados.append(Key)
        self.objetos.pop(Key, None)

    def head_bucket(self, *, Bucket):  # noqa: N803
        self.head_calls += 1


@pytest.fixture
def store(monkeypatch) -> tuple[R2DocumentBlobStore, ClienteFalso]:
    cliente = ClienteFalso()
    almacen = R2DocumentBlobStore(
        endpoint_url="https://cuenta.r2.cloudflarestorage.com",
        bucket="laria",
        access_key_id="id",
        secret_access_key="secreto",
        prefix="documents/",
    )
    monkeypatch.setattr(almacen, "_get_client", lambda: cliente)
    return almacen, cliente


def test_exige_endpoint_y_bucket():
    with pytest.raises(ValueError):
        R2DocumentBlobStore(
            endpoint_url="", bucket="laria", access_key_id="i", secret_access_key="s"
        )


@pytest.mark.asyncio
async def test_ciclo_completo_conserva_los_bytes(store):
    almacen, cliente = store
    datos = b"%PDF-1.4\x00\x93 binario"

    blob_id = await almacen.put(datos, filename="libro.pdf", content_type="application/pdf")

    assert blob_id.startswith("documents/")
    assert cliente.objetos[blob_id]["content_type"] == "application/pdf"
    # El nombre real viaja como metadato: la clave es opaca a propósito.
    assert cliente.objetos[blob_id]["metadata"] == {"filename": "libro.pdf"}
    assert "libro" not in blob_id

    assert await almacen.get(blob_id) == datos

    await almacen.delete(blob_id)
    assert cliente.borrados == [blob_id]


@pytest.mark.asyncio
async def test_leer_algo_que_no_existe_es_key_error(store):
    """El puerto promete `KeyError`; los repos dependen de eso."""
    almacen, _ = store

    with pytest.raises(KeyError):
        await almacen.get("documents/no-existe")


@pytest.mark.asyncio
async def test_borrar_dos_veces_no_falla(store):
    almacen, cliente = store
    blob_id = await almacen.put(b"x")

    await almacen.delete(blob_id)
    await almacen.delete(blob_id)

    assert cliente.borrados == [blob_id, blob_id]


@pytest.mark.asyncio
async def test_acepta_claves_con_y_sin_prefijo(store):
    """Los ids guardados antes de cambiar el prefijo siguen resolviendo."""
    almacen, cliente = store
    cliente.objetos["documents/abc"] = {"body": b"datos", "content_type": "", "metadata": {}}

    assert await almacen.get("abc") == b"datos"
    assert await almacen.get("documents/abc") == b"datos"


@pytest.mark.asyncio
async def test_ping_no_escribe_nada(store):
    almacen, cliente = store

    assert await almacen.ping() is True
    assert cliente.head_calls == 1
    assert cliente.objetos == {}
