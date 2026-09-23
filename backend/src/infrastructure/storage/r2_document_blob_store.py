"""Almacén de archivos originales en Cloudflare R2 (API compatible con S3).

Implementa el mismo puerto `DocumentBlobStore` que GridFS, así que cambiar
dónde viven los libros del estudiante es cambiar un adaptador: el dominio no se
entera. Es el pago de la arquitectura hexagonal (ADR-012).

**Por qué aquí y no en Mongo:** el texto extraído es pequeño y se consulta con
el documento; el archivo original es grande y solo se devuelve entero. Meterlos
juntos hace que dos PDF llenen el cluster free de Atlas (512 MB).

El cliente de boto3 es síncrono, así que cada llamada va a un hilo: un `put` de
20 MB no puede bloquear el event loop mientras sube.
"""
from __future__ import annotations

import asyncio
import logging
from uuid import uuid4

from src.domain.ports.document_blob_store import DocumentBlobStore

logger = logging.getLogger("laria.http")


class R2DocumentBlobStore(DocumentBlobStore):
    def __init__(
        self,
        *,
        endpoint_url: str,
        bucket: str,
        access_key_id: str,
        secret_access_key: str,
        prefix: str = "documents/",
    ) -> None:
        if not endpoint_url or not bucket:
            raise ValueError("R2 exige endpoint y bucket")
        self._endpoint_url = endpoint_url
        self._bucket = bucket
        self._access_key_id = access_key_id
        self._secret_access_key = secret_access_key
        self._prefix = prefix.strip("/") + "/" if prefix else ""
        self._client = None

    def _get_client(self):
        """Cliente perezoso: construirlo no habla con la red."""
        if self._client is None:
            import boto3
            from botocore.config import Config

            self._client = boto3.session.Session().client(
                "s3",
                endpoint_url=self._endpoint_url,
                aws_access_key_id=self._access_key_id,
                aws_secret_access_key=self._secret_access_key,
                # R2 no tiene regiones: "auto" es lo que documenta Cloudflare.
                region_name="auto",
                config=Config(signature_version="s3v4", retries={"max_attempts": 3}),
            )
        return self._client

    def _key(self, blob_id: str) -> str:
        return blob_id if blob_id.startswith(self._prefix) else f"{self._prefix}{blob_id}"

    async def put(
        self,
        data: bytes,
        *,
        filename: str = "",
        content_type: str = "text/plain",
    ) -> str:
        key = f"{self._prefix}{uuid4().hex}"

        def _subir() -> None:
            self._get_client().put_object(
                Bucket=self._bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
                # El nombre real viaja como metadato: la clave es opaca a
                # propósito, para no filtrar nombres de archivo en la URL.
                Metadata={"filename": filename[:200]} if filename else {},
            )

        await asyncio.to_thread(_subir)
        return key

    async def get(self, blob_id: str) -> bytes:
        key = self._key(blob_id)

        def _bajar() -> bytes:
            cliente = self._get_client()
            try:
                respuesta = cliente.get_object(Bucket=self._bucket, Key=key)
            except cliente.exceptions.NoSuchKey as exc:
                raise KeyError(blob_id) from exc
            return respuesta["Body"].read()

        return await asyncio.to_thread(_bajar)

    async def delete(self, blob_id: str) -> None:
        key = self._key(blob_id)

        def _borrar() -> None:
            # S3/R2 borra de forma idempotente: no falla si la clave no existe.
            self._get_client().delete_object(Bucket=self._bucket, Key=key)

        await asyncio.to_thread(_borrar)

    async def ping(self) -> bool:
        """Comprueba credenciales y bucket sin escribir nada."""

        def _comprobar() -> bool:
            self._get_client().head_bucket(Bucket=self._bucket)
            return True

        return await asyncio.to_thread(_comprobar)
