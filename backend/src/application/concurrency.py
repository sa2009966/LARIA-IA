"""Reintentos acotados ante ConcurrencyError (perfil / sesión)."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TypeVar

from src.domain.exceptions import ConcurrencyError

T = TypeVar("T")

DEFAULT_RETRIES = 3


async def with_concurrency_retry(
    operation: Callable[[], Awaitable[T]],
    *,
    retries: int = DEFAULT_RETRIES,
) -> T:
    last: ConcurrencyError | None = None
    for _ in range(max(1, retries)):
        try:
            return await operation()
        except ConcurrencyError as exc:
            last = exc
    assert last is not None
    raise last
