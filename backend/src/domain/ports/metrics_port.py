"""Puerto de métricas del sistema (pedagógicas y operativas)."""
from abc import ABC, abstractmethod


class MetricsPort(ABC):
    @abstractmethod
    def incr(self, name: str, value: float = 1.0, **labels: str) -> None:
        ...

    @abstractmethod
    def observe(self, name: str, value: float, **labels: str) -> None:
        ...

    @abstractmethod
    def gauge(self, name: str, value: float, **labels: str) -> None:
        ...

    @abstractmethod
    def snapshot(self) -> dict:
        """Vista agregada para /metrics o depuración."""
        ...
