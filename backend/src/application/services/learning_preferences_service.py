"""Preferencias que el estudiante declara él mismo (ADR-022)."""
from __future__ import annotations

from uuid import UUID

from src.domain.events.domain_events import ExplanationStyleChosenEvent
from src.domain.ports.event_bus import EventBus
from src.domain.ports.repositories import StudentProfileRepository
from src.domain.services.cognitive_style import CognitiveStyle


class LearningPreferencesService:
    def __init__(
        self, event_bus: EventBus, profile_repository: StudentProfileRepository | None = None
    ) -> None:
        self._bus = event_bus
        self._profiles = profile_repository

    async def explanation_style(self, student_id: UUID) -> str | None:
        if self._profiles is None:
            return None
        perfil = await self._profiles.find_by_student(student_id)
        return (perfil.explanation_style_choice or None) if perfil else None

    async def choose_explanation_style(self, student_id: UUID, style: str | None) -> str | None:
        """Publica la elección; la guarda el projector (invariante 1).

        Devuelve lo elegido y no lo releído: con el outbox el perfil se escribe
        un instante después, y releer devolvería el valor anterior.
        """
        if style is not None:
            style = CognitiveStyle(style).value  # ValueError si no es un estilo
        await self._bus.publish(
            ExplanationStyleChosenEvent(aggregate_id=student_id, student_id=student_id, style=style)
        )
        return style
