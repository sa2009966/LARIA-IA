from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from src.domain.value_objects.email import Email
from src.domain.value_objects.password import Password as PasswordVO
from src.domain.events.domain_events import (
    UserRegisteredEvent, UserDeactivatedEvent, DomainEvent,
)


class UserRole(Enum):
    STUDENT = "student"
    TEACHER = "teacher"
    ADMIN = "admin"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class UserAggregate:
    id: UUID = field(default_factory=uuid4)
    username: str = ""
    email: Email = field(default_factory=lambda: Email("empty@placeholder.com"))
    hashed_password: str = ""
    role: UserRole = UserRole.STUDENT
    is_active: bool = True
    created_at: datetime = field(default_factory=_utc_now)
    events: list[DomainEvent] = field(default_factory=list)

    @staticmethod
    def register(username: str, email: str, raw_password: str) -> "UserAggregate":
        pw = PasswordVO(raw_password)
        if pw.is_weak():
            raise ValueError(
                "La contraseña es demasiado débil: mínimo 12 caracteres, "
                "mayúsculas, minúsculas y al menos un dígito."
            )
        user = UserAggregate(
            username=username,
            email=Email(email),
            hashed_password=pw.hash(),
            role=UserRole.STUDENT,
            is_active=True,
        )
        user.events.append(
            UserRegisteredEvent(aggregate_id=user.id, email=email)
        )
        return user

    def deactivate(self) -> None:
        if not self.is_active:
            raise ValueError("User is already deactivated")
        self.is_active = False
        self.events.append(
            UserDeactivatedEvent(aggregate_id=self.id)
        )

    def activate(self) -> None:
        if self.is_active:
            raise ValueError("User is already active")
        self.is_active = True

    def change_role(self, new_role: UserRole) -> None:
        if not isinstance(new_role, UserRole):
            raise ValueError("Invalid role")
        self.role = new_role

    def clear_events(self) -> None:
        self.events.clear()

    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN

    def is_teacher(self) -> bool:
        return self.role == UserRole.TEACHER
