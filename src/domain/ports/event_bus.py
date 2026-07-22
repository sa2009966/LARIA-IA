from abc import ABC, abstractmethod
from typing import Callable, Any

from src.domain.events.domain_events import DomainEvent


class EventBus(ABC):
    @abstractmethod
    async def publish(self, event: DomainEvent) -> None:
        ...

    @abstractmethod
    async def subscribe(self, event_type: type, handler: Callable[[DomainEvent], Any]) -> None:
        ...
