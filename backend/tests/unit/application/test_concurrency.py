"""Tests de reintentos ante ConcurrencyError."""
import pytest

from src.application.concurrency import with_concurrency_retry
from src.domain.exceptions import ConcurrencyError


@pytest.mark.asyncio
async def test_with_concurrency_retry_happy_path():
    calls = 0

    async def operation():
        nonlocal calls
        calls += 1
        return "ok"

    result = await with_concurrency_retry(operation)
    assert result == "ok"
    assert calls == 1


@pytest.mark.asyncio
async def test_with_concurrency_retry_recovers_after_one_failure():
    calls = 0

    async def operation():
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ConcurrencyError("stale version")
        return "ok"

    result = await with_concurrency_retry(operation, retries=3)
    assert result == "ok"
    assert calls == 2


@pytest.mark.asyncio
async def test_with_concurrency_retry_raises_after_exhaustion():
    async def operation():
        raise ConcurrencyError("stale version")

    with pytest.raises(ConcurrencyError, match="stale version"):
        await with_concurrency_retry(operation, retries=2)
