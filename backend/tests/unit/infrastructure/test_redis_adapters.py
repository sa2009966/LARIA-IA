"""Cobertura RedisCache y RedisSlidingWindow con cliente mock."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.infrastructure.cache.cache_adapters import InMemoryCache, RedisCache
from src.infrastructure.rate_limit import RedisSlidingWindow, build_rate_limit_counter


@pytest.mark.asyncio
async def test_in_memory_delete():
    cache = InMemoryCache()
    await cache.set("gone", "v")
    await cache.delete("gone")
    assert await cache.get("gone") is None


@pytest.mark.asyncio
async def test_in_memory_cache_ttl_expiry(monkeypatch):
    cache = InMemoryCache()
    now = 1000.0
    monkeypatch.setattr("src.infrastructure.cache.cache_adapters.time.time", lambda: now)
    await cache.set("k", "v", ttl_seconds=10)
    assert await cache.get("k") == "v"
    monkeypatch.setattr("src.infrastructure.cache.cache_adapters.time.time", lambda: now + 11)
    assert await cache.get("k") is None


@pytest.mark.asyncio
async def test_in_memory_delete_prefix():
    cache = InMemoryCache()
    await cache.set("quiz:1:a", "x")
    await cache.set("quiz:1:b", "y")
    await cache.set("other", "z")
    await cache.delete_prefix("quiz:1:")
    assert await cache.get("quiz:1:a") is None
    assert await cache.get("other") == "z"


@pytest.mark.asyncio
async def test_redis_cache_operations():
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value="cached")
    mock_redis.set = AsyncMock()
    mock_redis.delete = AsyncMock()

    async def _scan_iter(match=None):
        for key in ("quiz:abc:1", "quiz:abc:2"):
            yield key

    mock_redis.scan_iter = _scan_iter

    cache = RedisCache("redis://localhost:6379/0")
    cache._client = mock_redis

    assert await cache.get("k") == "cached"
    await cache.set("k", "v", ttl_seconds=60)
    mock_redis.set.assert_awaited_with("k", "v", ex=60)

    await cache.set("k2", "v2")
    mock_redis.set.assert_awaited_with("k2", "v2")

    await cache.delete("k")
    await cache.delete_prefix("quiz:abc:")
    assert mock_redis.delete.await_count >= 3


@pytest.mark.asyncio
async def test_redis_cache_lazy_client(monkeypatch):
    mock_instance = AsyncMock()
    mock_from_url = MagicMock(return_value=mock_instance)
    monkeypatch.setattr(
        "redis.asyncio.Redis.from_url",
        mock_from_url,
    )
    cache = RedisCache("redis://localhost:6379/0")
    client = await cache._get_client()
    assert client is mock_instance
    mock_from_url.assert_called_once_with("redis://localhost:6379/0", decode_responses=True)


def test_redis_sliding_window_allows_under_limit():
    mock_redis = MagicMock()
    mock_pipe = MagicMock()
    mock_redis.pipeline.return_value = mock_pipe
    mock_pipe.zremrangebyscore = MagicMock()
    mock_pipe.zcard = MagicMock()
    mock_pipe.zadd = MagicMock()
    mock_pipe.expire = MagicMock()
    mock_pipe.execute.return_value = [None, 1, None, None]

    counter = RedisSlidingWindow(mock_redis)
    assert counter.allow("ip:route", limit=3, window_seconds=60.0) is True


def test_redis_sliding_window_blocks_at_limit():
    mock_redis = MagicMock()
    mock_pipe = MagicMock()
    mock_redis.pipeline.return_value = mock_pipe
    mock_pipe.execute.return_value = [None, 3, None, None]

    counter = RedisSlidingWindow(mock_redis)
    assert counter.allow("ip:route", limit=3, window_seconds=60.0) is False


def test_build_rate_limit_counter_redis(monkeypatch):
    from src.infrastructure.config import settings

    mock_client = MagicMock()
    mock_client.ping.return_value = True
    mock_redis_mod = MagicMock()
    mock_redis_mod.Redis.from_url.return_value = mock_client
    monkeypatch.setattr(settings, "RATE_LIMIT_BACKEND", "redis")
    monkeypatch.setattr(settings, "REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setitem(__import__("sys").modules, "redis", mock_redis_mod)

    counter = build_rate_limit_counter()
    assert isinstance(counter, RedisSlidingWindow)


def test_build_rate_limit_counter_memory(monkeypatch):
    from src.infrastructure.config import settings
    from src.infrastructure.rate_limit import SlidingWindowCounter

    monkeypatch.setattr(settings, "RATE_LIMIT_BACKEND", "memory")
    assert isinstance(build_rate_limit_counter(), SlidingWindowCounter)
