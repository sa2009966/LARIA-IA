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


@pytest.mark.asyncio
async def test_los_reintentos_esperan_entre_intentos(monkeypatch):
    """Sin backoff, los escritores rivales vuelven a chocar en el mismo instante."""
    esperas: list[float] = []

    async def fake_sleep(segundos: float) -> None:
        esperas.append(segundos)

    monkeypatch.setattr("src.application.concurrency.asyncio.sleep", fake_sleep)
    intentos = 0

    async def operation():
        nonlocal intentos
        intentos += 1
        if intentos < 3:
            raise ConcurrencyError("stale version")
        return "ok"

    assert await with_concurrency_retry(operation, retries=3) == "ok"
    assert len(esperas) == 2  # una espera por reintento, no tras el último
    assert all(e > 0 for e in esperas)
    assert all(e <= 0.5 for e in esperas)  # acotado: no alarga el turno


@pytest.mark.asyncio
async def test_sin_conflicto_no_hay_espera(monkeypatch):
    llamadas: list[float] = []
    monkeypatch.setattr(
        "src.application.concurrency.asyncio.sleep",
        lambda s: llamadas.append(s),
    )

    async def operation():
        return "ok"

    assert await with_concurrency_retry(operation) == "ok"
    assert llamadas == []
