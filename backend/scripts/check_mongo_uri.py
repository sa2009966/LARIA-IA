#!/usr/bin/env python3
"""Comprueba una conexión a MongoDB (Atlas o local) y dice qué hay dentro.

Sirve para separar dos cosas que se confunden: que el cluster exista y
funcione, y que el servicio lo esté usando. `/ready` con `mongodb: "skipped"`
significa que la app **no intentó conectarse** (`DB_PROVIDER` no es `mongodb`),
no que el cluster falle.

    # La URI se lee del entorno. No la escribas en este archivo: una cadena
    # mongodb+srv con usuario, clave y host .mongodb.net dispara el escáner
    # de secretos de GitHub aunque usuario y clave sean de mentira.
    export MONGODB_URL   # cópiala del dashboard de Atlas, solo en tu shell o .env
    python scripts/check_mongo_uri.py

    # o con la configuración del backend ya cargada (.env)
    python scripts/check_mongo_uri.py --from-settings

Nunca imprime la URI ni las credenciales.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

#: Colecciones que la app crea/usa; se listan sus conteos para ver si hay datos.
COLECCIONES = (
    "users",
    "documents",
    "chats",
    "quizzes",
    "quiz_attempts",
    "tutor_interactions",
    "tutor_sessions",
    "student_profiles",
    "concept_graphs",
    "learning_paths",
    "event_outbox",
)


def _host_seguro(uri: str) -> str:
    """Host y esquema, sin usuario ni contraseña."""
    try:
        partes = urlsplit(uri)
        host = partes.hostname or "?"
        return f"{partes.scheme}://{host}"
    except ValueError:
        return "(uri ilegible)"


async def _comprobar(uri: str, db_name: str, timeout_ms: int) -> int:
    from motor.motor_asyncio import AsyncIOMotorClient

    print(f"Conectando a {_host_seguro(uri)} · base {db_name!r} (timeout {timeout_ms} ms)")
    cliente = AsyncIOMotorClient(
        uri, serverSelectionTimeoutMS=timeout_ms, connectTimeoutMS=timeout_ms
    )
    try:
        info = await cliente.admin.command("ping")
        if not info.get("ok"):
            print("  ✗ el ping no devolvió ok", file=sys.stderr)
            return 1
        build = await cliente.admin.command("buildInfo")
        print(f"  ✓ conexión establecida · MongoDB {build.get('version', '?')}")

        db = cliente[db_name]
        existentes = set(await db.list_collection_names())
        print(f"\n  colecciones en la base: {len(existentes)}")
        con_datos = 0
        for nombre in COLECCIONES:
            if nombre not in existentes:
                print(f"    · {nombre:22} —")
                continue
            n = await db[nombre].count_documents({})
            con_datos += 1 if n else 0
            print(f"    · {nombre:22} {n} documento(s)")

        otras = sorted(existentes - set(COLECCIONES))
        if otras:
            print(f"    (otras colecciones: {', '.join(otras)})")

        if not existentes:
            print(
                "\n  La base está vacía: normal si nadie ha escrito todavía. Los índices y las "
                "colecciones se crean al arrancar la app con DB_PROVIDER=mongodb."
            )
        elif not con_datos:
            print("\n  Hay colecciones pero sin documentos: la app arrancó, nadie usó la API aún.")
        return 0
    except Exception as exc:  # noqa: BLE001 — el diagnóstico es el propósito
        print(f"\n  ✗ no se pudo usar la conexión: {type(exc).__name__}", file=sys.stderr)
        print(f"    {str(exc)[:300]}", file=sys.stderr)
        print(
            "\n  Sospechas habituales:\n"
            "    · IP no permitida en Atlas (Network Access → 0.0.0.0/0 para Render free)\n"
            "    · usuario/clave incorrectos, o clave con caracteres sin escapar en la URI\n"
            "    · la URI apunta a un cluster pausado",
            file=sys.stderr,
        )
        return 1
    finally:
        cliente.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--from-settings",
        action="store_true",
        help="usa MONGODB_URL y MONGODB_DB_NAME de la configuración del backend (.env)",
    )
    parser.add_argument("--db", default=None, help="nombre de base (por defecto laria_db)")
    parser.add_argument("--timeout-ms", type=int, default=10_000)
    args = parser.parse_args()

    if args.from_settings:
        from src.infrastructure.config import settings

        uri, db_name = settings.MONGODB_URL, settings.MONGODB_DB_NAME
    else:
        uri = os.environ.get("MONGODB_URL", "")
        db_name = args.db or os.environ.get("MONGODB_DB_NAME", "laria_db")

    if not uri:
        print(
            "Falta la URI. Exporta MONGODB_URL o usa --from-settings.",
            file=sys.stderr,
        )
        return 2
    return asyncio.run(_comprobar(uri, args.db or db_name, args.timeout_ms))


if __name__ == "__main__":
    raise SystemExit(main())
