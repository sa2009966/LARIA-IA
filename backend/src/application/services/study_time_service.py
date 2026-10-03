"""Metas de estudio y tiempo estudiado (ADR-033)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from src.domain.aggregates.study_time import (
    DAILY_GOAL_MINUTES,
    SESSION_MINUTES,
    StudyDay,
    credit_for,
    streak_days,
)
from src.domain.events.domain_events import StudyGoalsChosenEvent
from src.domain.ports.event_bus import EventBus
from src.domain.ports.repositories import StudentProfileRepository, StudyTimeRepository


def zona(nombre: str | None) -> ZoneInfo:
    """La zona horaria del estudiante; UTC si no llega o no existe."""
    try:
        return ZoneInfo((nombre or "UTC").strip() or "UTC")
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


@dataclass(frozen=True)
class StudySummary:
    today_minutes: int
    daily_goal_minutes: int | None
    session_minutes: int | None
    goal_met_today: bool
    streak_days: int
    last_7_days: list[tuple[date, int]]


class StudyTimeService:
    def __init__(
        self,
        repository: StudyTimeRepository,
        event_bus: EventBus,
        profile_repository: StudentProfileRepository,
    ) -> None:
        self._repo = repository
        self._bus = event_bus
        self._profiles = profile_repository

    async def goals(self, student_id: UUID) -> tuple[int | None, int | None]:
        p = await self._profiles.find_by_student(student_id)
        if p is None:
            return None, None
        return (p.session_minutes or None, p.daily_goal_minutes or None)

    async def choose_goals(
        self, student_id: UUID, session_minutes: int | None, daily_goal_minutes: int | None
    ) -> tuple[int | None, int | None]:
        if session_minutes is not None and session_minutes not in SESSION_MINUTES:
            raise ValueError(f"La duración de sesión debe ser una de {SESSION_MINUTES} o null.")
        if daily_goal_minutes is not None and daily_goal_minutes not in DAILY_GOAL_MINUTES:
            raise ValueError(f"El objetivo diario debe ser uno de {DAILY_GOAL_MINUTES} o null.")
        await self._bus.publish(
            StudyGoalsChosenEvent(
                aggregate_id=student_id,
                student_id=student_id,
                session_minutes=session_minutes,
                daily_goal_minutes=daily_goal_minutes,
            )
        )
        return session_minutes, daily_goal_minutes

    async def record(self, student_id: UUID, seconds: int, tz: str | None, now: datetime | None = None) -> StudySummary:
        """Suma un aviso de actividad, acotado por `credit_for`."""
        ahora = now or datetime.now(timezone.utc)
        hoy = ahora.astimezone(zona(tz)).date()
        dia = await self._repo.get_day(student_id, hoy) or StudyDay(student_id=student_id, day=hoy)
        ultimo = dia.last_ping_at
        if ultimo is None:
            ayer = await self._repo.get_day(student_id, hoy - timedelta(days=1))
            ultimo = ayer.last_ping_at if ayer else None
        if ultimo is not None and ultimo.tzinfo is None:  # Mongo devuelve sin zona
            ultimo = ultimo.replace(tzinfo=timezone.utc)
        dia.seconds += credit_for(seconds, ahora, ultimo)
        dia.last_ping_at = ahora
        await self._repo.save_day(dia)
        return await self.summary(student_id, tz, now=ahora)

    async def summary(self, student_id: UUID, tz: str | None, now: datetime | None = None) -> StudySummary:
        ahora = now or datetime.now(timezone.utc)
        hoy = ahora.astimezone(zona(tz)).date()
        dias = await self._repo.days_since(student_id, hoy - timedelta(days=60))
        por_dia = {d.day: d.minutes for d in dias}
        sesion, objetivo = await self.goals(student_id)
        hoy_min = por_dia.get(hoy, 0)
        return StudySummary(
            today_minutes=hoy_min,
            daily_goal_minutes=objetivo,
            session_minutes=sesion,
            goal_met_today=bool(objetivo) and hoy_min >= objetivo,
            streak_days=streak_days(por_dia, hoy, objetivo),
            last_7_days=[(hoy - timedelta(days=i), por_dia.get(hoy - timedelta(days=i), 0)) for i in range(6, -1, -1)],
        )
