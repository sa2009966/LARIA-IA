"""Adaptadores de caché: memoria y Redis."""
from __future__ import annotations

import time
from typing import Optional

from src.domain.ports.cache_port import CachePort


class InMemoryCache(CachePort):
    def __init__(self) -> None:
        self._store: dict[str, tuple[str, float | None]] = {}

    async def get(self, key: str) -> Optional[str]:
        item = self._store.get(key)
        if item is None:
            return None
        value, expires = item
        if expires is not None and time.time() > expires:
            self._store.pop(key, None)
            return None
        return value

    async def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        expires = (time.time() + ttl_seconds) if ttl_seconds else None
        self._store[key] = (value, expires)

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)

    async def delete_prefix(self, prefix: str) -> None:
        for k in list(self._store):
            if k.startswith(prefix):
                self._store.pop(k, None)


class RedisCache(CachePort):
    def __init__(self, redis_url: str) -> None:
        self._url = redis_url
        self._client = None

    async def _get_client(self):
        if self._client is None:
            from redis.asyncio import Redis

            self._client = Redis.from_url(self._url, decode_responses=True)
        return self._client

    async def get(self, key: str) -> Optional[str]:
        client = await self._get_client()
        return await client.get(key)

    async def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        client = await self._get_client()
        if ttl_seconds:
            await client.set(key, value, ex=ttl_seconds)
        else:
            await client.set(key, value)

    async def delete(self, key: str) -> None:
        client = await self._get_client()
        await client.delete(key)

    async def delete_prefix(self, prefix: str) -> None:
        client = await self._get_client()
        async for key in client.scan_iter(match=f"{prefix}*"):
            await client.delete(key)
