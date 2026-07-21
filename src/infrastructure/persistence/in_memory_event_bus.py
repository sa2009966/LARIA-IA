from typing import Callable, Any

from src.domain.events.domain_events import DomainEvent
from src.domain.ports.event_bus import EventBus


class InMemoryEventBus(EventBus):

    def __init__(self) -> None:
        self._subscribers: dict[type, list[Callable[[DomainEvent], Any]]] = {}

    async def publish(self, event: DomainEvent) -> None:
        handlers = self._subscribers.get(type(event), [])
        for handler in handlers:
            result = handler(event)
            if hasattr(result, '__await__'):
                await result

    async def subscribe(self, event_type: type, handler: Callable[[DomainEvent], Any]) -> None:
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)