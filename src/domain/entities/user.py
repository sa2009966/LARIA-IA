from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class User:
    """Entidad pura de dominio. Sin dependencias externas."""
    id: Optional[int]
    username: str
    email: str
    hashed_password: str
    role: str = "student"
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)

    def is_admin(self) -> bool:
        return self.role == "admin"

    def deactivate(self) -> None:
        self.is_active = False
