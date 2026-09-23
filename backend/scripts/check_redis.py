#!/usr/bin/env python3
"""Comprueba una conexión a Redis (Upstash o local) antes de meterla en Render.

Existe para separar dos fallos que se confunden: que la URL sea mala y que el
servicio no la esté usando. `/ready` con `redis: "skipped"` significa que la app
**no intentó conectarse** (`RATE_LIMIT_BACKEND` y `CACHE_BACKEND` siguen en
`memory`), no que Redis falle.

    # La URL se lee del entorno. No la escribas en este archivo: una cadena
    # rediss://default:clave@….upstash.io dispara el escáner de secretos
    # aunque la clave sea de mentira. Upstash usa rediss:// (dos eses), no redis://.
    export REDIS_URL   # cópiala de Upstash, solo en tu shell o .env
    python scripts/check_redis.py

    # o con la configuración del backend ya cargada (.env)
    python scripts/check_redis.py --from-settings

Comprueba, en orden: que conecta, que escribe y lee, que el TTL se respeta y
que el borrado funciona. Además ejercita el **contador de ventana deslizante**
real del rate limit, que es el uso de verdad que le da el backend.

Nunca imprime la URL ni la contraseña.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

CLAVE = "laria:check"


def _host_seguro(url: str) -> str:
    """Esquema y host, sin usuario ni contraseña."""
    try:
        partes = urlsplit(url)
        tls = "con TLS" if partes.scheme == "rediss" else "SIN TLS"
        return f"{partes.scheme}://{partes.hostname}:{partes.port or 6379} ({tls})"
    except ValueError:
        return "(url ilegible)"


async def _comprobar(url: str) -> int:
    try:
        import redis.asyncio as aioredis
    except ImportError:
        print(
            "Falta el paquete `redis`. Instálalo con:\n"
            "    pip install -r requirements.txt",
            file=sys.stderr,
        )
        return 2

    print(f"Conectando a {_host_seguro(url)}")
    cliente = aioredis.from_url(url, socket_connect_timeout=10, socket_timeout=10)
    try:
        inicio = time.monotonic()
        await cliente.ping()
        latencia = (time.monotonic() - inicio) * 1000
        print(f"  ✓ ping ok · {latencia:.0f} ms de ida y vuelta")
        if latencia > 300:
            print(
                "    ⚠ más de 300 ms: la región de Upstash está lejos de Render. "
                "Cada request de auth y de chat paga esto."
            )

        await cliente.set(CLAVE, "1", ex=5)
        valor = await cliente.get(CLAVE)
        if valor not in (b"1", "1"):
            print(f"  ✗ lo leído no es lo escrito: {valor!r}", file=sys.stderr)
            return 1
        print("  ✓ escritura y lectura ok")

        ttl = await cliente.ttl(CLAVE)
        if not 0 < ttl <= 5:
            print(f"  ✗ el TTL no se respeta (ttl={ttl})", file=sys.stderr)
            return 1
        print(f"  ✓ expiración ok · ttl={ttl}s")

        await cliente.delete(CLAVE)
        if await cliente.exists(CLAVE):
            print("  ✗ la clave sigue ahí tras borrarla", file=sys.stderr)
            return 1
        print("  ✓ borrado ok")

        if not await _comprobar_rate_limit(cliente):
            return 1

        info = await cliente.info("server")
        version = info.get("redis_version", "?")
        print(f"\n  Redis {version} listo para el backend.")
        print(
            "  Variables en Render: RATE_LIMIT_BACKEND=redis · CACHE_BACKEND=redis · REDIS_URL"
        )
        return 0
    except Exception as exc:  # noqa: BLE001 — el diagnóstico es el propósito
        print(f"\n  ✗ no se pudo usar la conexión: {type(exc).__name__}", file=sys.stderr)
        print(f"    {str(exc)[:300]}", file=sys.stderr)
        print(
            "\n  Sospechas habituales:\n"
            "    · la URL de Upstash es `rediss://` (con dos eses): con `redis://` falla el TLS\n"
            "    · copiaste la REST URL (https://…upstash.io) en vez de la de Redis\n"
            "    · la contraseña lleva caracteres sin escapar en la URL\n"
            "    · la base está pausada o se agotó la cuota del plan free",
            file=sys.stderr,
        )
        return 1
    finally:
        await cliente.aclose()


class _FallbackQueGrita:
    """Sustituye al contador local para que una degradación no pase inadvertida.

    `RedisSlidingWindow` degrada a memoria ante cualquier fallo de red —bien
    para producción, porque un limitador caído no debe tumbar el borde, y fatal
    para una comprobación: el contador respondería igual con Redis roto.
    """

    async def allow(self, key: str, limit: int, window_seconds: float) -> bool:
        raise RuntimeError("el contador degradó a memoria: Redis no respondió")


async def _comprobar_rate_limit(cliente) -> bool:
    """El uso real: la ventana deslizante que protege auth, ask y quiz.

    Un `ping` correcto no prueba que el pipeline de `zadd`/`zremrangebyscore`
    funcione, y es lo que el backend ejecuta en **cada** request.
    """
    from uuid import uuid4

    from src.infrastructure.rate_limit import RedisSlidingWindow

    contador = RedisSlidingWindow(cliente, fallback=_FallbackQueGrita())
    clave = f"check:{uuid4().hex[:8]}"
    try:
        permitidas = sum(
            1 for _ in range(5) if await contador.allow(clave, limit=3, window_seconds=60)
        )
    except RuntimeError as exc:
        print(f"  ✗ {exc}", file=sys.stderr)
        return False
    finally:
        await cliente.delete(f"rl:{clave}")

    if permitidas != 3:
        print(
            f"  ✗ el rate limit dejó pasar {permitidas} de 5 con límite 3",
            file=sys.stderr,
        )
        return False
    print("  ✓ ventana deslizante del rate limit ok (3 de 5 permitidas)")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--from-settings",
        action="store_true",
        help="usa REDIS_URL de la configuración del backend (.env)",
    )
    args = parser.parse_args()

    if args.from_settings:
        from src.infrastructure.config import settings

        url = settings.REDIS_URL
    else:
        url = os.environ.get("REDIS_URL", "")

    if not url:
        print("Falta la URL. Exporta REDIS_URL o usa --from-settings.", file=sys.stderr)
        return 2
    return asyncio.run(_comprobar(url))


if __name__ == "__main__":
    raise SystemExit(main())
