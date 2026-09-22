"""Reintentos acotados ante ConcurrencyError (perfil / sesión)."""
from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable
from typing import TypeVar

from src.domain.exceptions import ConcurrencyError

T = TypeVar("T")

DEFAULT_RETRIES = 3
#: Espera antes del primer reintento. Se dobla en cada intento y lleva jitter:
#: tres reintentos inmediatos contra un conflicto de versión son tres colisiones
#: más, porque los escritores rivales vuelven a chocar en el mismo instante.
DEFAULT_BACKOFF_SECONDS = 0.02
#: Techo por espera, para que un perfil muy disputado no alargue el turno.
MAX_BACKOFF_SECONDS = 0.5


async def with_concurrency_retry(
    operation: Callable[[], Awaitable[T]],
    *,
    retries: int = DEFAULT_RETRIES,
    backoff_seconds: float = DEFAULT_BACKOFF_SECONDS,
) -> T:
    last: ConcurrencyError | None = None
    intentos = max(1, retries)
    for intento in range(intentos):
        try:
            return await operation()
        except ConcurrencyError as exc:
            last = exc
            if intento == intentos - 1:
                break
            await asyncio.sleep(_espera(intento, backoff_seconds))
    assert last is not None
    raise last


def _espera(intento: int, base: float) -> float:
    """Backoff exponencial con jitter completo, acotado."""
    if base <= 0:
        return 0.0
    tope = min(MAX_BACKOFF_SECONDS, base * (2**intento))
    return random.uniform(0.0, tope)
