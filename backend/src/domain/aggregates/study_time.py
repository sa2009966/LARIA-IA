"""Tiempo estudiado por día (ADR-033). Actividad, no evidencia: no va en el perfil.

El cliente avisa cada minuto mientras la clase está visible y hay actividad; el
servidor decide cuánto cuenta. Así vale entre dispositivos y no se infla.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from uuid import UUID

#: Lo máximo que suma un aviso: el cliente avisa cada minuto.
MAX_CREDIT_SECONDS = 60
#: Margen sobre el tiempo real transcurrido (latencia de red, relojes).
ELAPSED_TOLERANCE_SECONDS = 5


@dataclass
class StudyDay:
    student_id: UUID
    day: date
    seconds: int = 0
    last_ping_at: datetime | None = None

    @property
    def minutes(self) -> int:
        return self.seconds // 60


def credit_for(reported_seconds: int, now: datetime, last_ping_at: datetime | None) -> int:
    """Cuánto cuenta un aviso: ni más de 60 s, ni más del tiempo real desde el anterior.

    Con dos pestañas abiertas avisando cada una cada minuto, el tiempo real entre
    avisos es menor y no se cuenta doble.
    """
    pedido = max(0, min(int(reported_seconds), MAX_CREDIT_SECONDS))
    if last_ping_at is None:
        return pedido
    real = (now - last_ping_at).total_seconds() + ELAPSED_TOLERANCE_SECONDS
    return max(0, min(pedido, int(real)))


def streak_days(minutes_by_day: dict[date, int], today: date, goal_minutes: int | None) -> int:
    """Días seguidos cumpliendo el objetivo (o estudiando algo, sin objetivo).

    Hoy cuenta si ya se cumplió; si todavía no, la racha de ayer sigue viva.
    """
    umbral = goal_minutes or 1
    dia = today if minutes_by_day.get(today, 0) >= umbral else today - timedelta(days=1)
    racha = 0
    while minutes_by_day.get(dia, 0) >= umbral:
        racha += 1
        dia -= timedelta(days=1)
    return racha


SESSION_MINUTES = (10, 20, 30, 45)
DAILY_GOAL_MINUTES = (10, 15, 30, 45, 60)
