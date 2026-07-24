"""Puerto de caché (Redis u otro). Sin lógica pedagógica."""
from abc import ABC, abstractmethod
from typing import Optional


class CachePort(ABC):
    @abstractmethod
    async def get(self, key: str) -> Optional[str]:
        ...

    @abstractmethod
    async def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        ...

    @abstractmethod
    async def delete(self, key: str) -> None:
        ...

    @abstractmethod
    async def delete_prefix(self, prefix: str) -> None:
        ...
