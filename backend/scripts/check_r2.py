#!/usr/bin/env python3
"""Comprueba la conexión a Cloudflare R2 y hace un ciclo completo de prueba.

No necesitas darle las credenciales a nadie: las pones en tu `.env` local (que
está en .gitignore) o en el entorno, y este script te dice si funcionan. Nunca
imprime la clave ni el secreto.

    export R2_ENDPOINT_URL='https://<account_id>.r2.cloudflarestorage.com'
    export R2_BUCKET='laria-documentos'
    export R2_ACCESS_KEY_ID='...'
    export R2_SECRET_ACCESS_KEY='...'
    python scripts/check_r2.py

    # o con lo que ya haya en la configuración del backend
    python scripts/check_r2.py --from-settings

Comprueba, en orden: que el bucket existe y las credenciales sirven, que se
puede escribir, leer byte a byte y borrar. Si los cuatro pasos pasan, el
backend puede usar R2 con `ORIGINAL_STORAGE=r2`.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

PRUEBA = b"laria-r2-check\x00\x93 bytes binarios de prueba"


def _host(endpoint: str) -> str:
    try:
        return urlsplit(endpoint).hostname or "?"
    except ValueError:
        return "(endpoint ilegible)"


async def _comprobar(endpoint: str, bucket: str, key_id: str, secret: str, prefix: str) -> int:
    from src.infrastructure.storage.r2_document_blob_store import R2DocumentBlobStore

    print(f"Bucket {bucket!r} en {_host(endpoint)}")
    print(f"  credenciales: id …{key_id[-4:]} (secreto oculto)")
    store = R2DocumentBlobStore(
        endpoint_url=endpoint,
        bucket=bucket,
        access_key_id=key_id,
        secret_access_key=secret,
        prefix=prefix,
    )
    blob_id = None
    try:
        await store.ping()
        print("  ✓ el bucket existe y las credenciales sirven")

        blob_id = await store.put(PRUEBA, filename="check.bin", content_type="application/octet-stream")
        print(f"  ✓ escritura ok · clave {blob_id}")

        leido = await store.get(blob_id)
        if leido != PRUEBA:
            print("  ✗ lo leído no coincide con lo escrito", file=sys.stderr)
            return 1
        print(f"  ✓ lectura ok · {len(leido)} bytes idénticos")

        await store.delete(blob_id)
        blob_id = None
        print("  ✓ borrado ok")
        print("\nR2 está listo. Pon ORIGINAL_STORAGE=r2 en el entorno del backend.")
        return 0
    except Exception as exc:  # noqa: BLE001 — el diagnóstico es el propósito
        print(f"\n  ✗ falló: {type(exc).__name__}", file=sys.stderr)
        print(f"    {str(exc)[:300]}", file=sys.stderr)
        print(
            "\n  Sospechas habituales:\n"
            "    · el token de API no tiene permiso 'Object Read & Write' sobre este bucket\n"
            "    · el endpoint no es el de S3 API (debe ser <account_id>.r2.cloudflarestorage.com,\n"
            "      no la URL pública del bucket ni r2.dev)\n"
            "    · el nombre del bucket no coincide exactamente\n"
            "    · se usó el token de Cloudflare en vez del par Access Key ID / Secret",
            file=sys.stderr,
        )
        return 1
    finally:
        if blob_id:
            try:
                await store.delete(blob_id)
            except Exception:  # noqa: BLE001
                print(f"  ⚠ quedó el objeto de prueba {blob_id}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-settings", action="store_true", help="usa la config del backend")
    args = parser.parse_args()

    if args.from_settings:
        from src.infrastructure.config import settings

        datos = (
            settings.R2_ENDPOINT_URL,
            settings.R2_BUCKET,
            settings.R2_ACCESS_KEY_ID,
            settings.R2_SECRET_ACCESS_KEY,
            settings.R2_PREFIX,
        )
    else:
        datos = (
            os.environ.get("R2_ENDPOINT_URL", ""),
            os.environ.get("R2_BUCKET", ""),
            os.environ.get("R2_ACCESS_KEY_ID", ""),
            os.environ.get("R2_SECRET_ACCESS_KEY", ""),
            os.environ.get("R2_PREFIX", "documents/"),
        )

    faltan = [
        nombre
        for nombre, valor in zip(
            ("R2_ENDPOINT_URL", "R2_BUCKET", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"), datos
        )
        if not (valor or "").strip()
    ]
    if faltan:
        print("Faltan variables: " + ", ".join(faltan), file=sys.stderr)
        return 2
    return asyncio.run(_comprobar(*datos))


if __name__ == "__main__":
    raise SystemExit(main())
