from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class User:
    """Entidad pura de dominio. Sin dependencias externas."""
    id: Optional[int]
    username: str
    email: str
    hashed_password: str
    role: str = "student"
    is_active: bool = True
    created_at: datetime = field(default_factory=_utc_now)

    def is_admin(self) -> bool:
        return self.role == "admin"

    def deactivate(self) -> None:
        self.is_active = False
