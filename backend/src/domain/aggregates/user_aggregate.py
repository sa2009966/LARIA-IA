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
    """Solo dos roles de producto: estudiante y administrador."""

    STUDENT = "student"
    ADMIN = "admin"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


#: Marca de "sin contraseña" (cuentas de Google). No es un hash bcrypt válido, así
#: que `Password.verify` siempre da False y el login por contraseña no entra.
UNUSABLE_PASSWORD = "!sin-contrasena"


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
    #: Un proveedor de identidad (Google) garantizó que el correo es de esta persona.
    email_verified: bool = False
    #: Identificador estable de la cuenta de Google vinculada (claim `sub`).
    google_sub: str | None = None

    def has_password(self) -> bool:
        return not self.hashed_password.startswith(UNUSABLE_PASSWORD)

    @staticmethod
    def register_verified(username: str, email: str, google_sub: str) -> "UserAggregate":
        """Cuenta creada con Google: correo verificado y sin contraseña propia."""
        user = UserAggregate(
            username=username,
            email=Email(email),
            hashed_password=UNUSABLE_PASSWORD,
            role=UserRole.STUDENT,
            is_active=True,
            email_verified=True,
            google_sub=google_sub,
        )
        user.events.append(UserRegisteredEvent(aggregate_id=user.id, email=email))
        return user

    def link_google(self, google_sub: str) -> None:
        """Vincula Google a una cuenta existente con el mismo correo.

        Si el correo NUNCA se había verificado, la contraseña anterior se anula.
        Sin esto, alguien podía registrar "victima@gmail.com" con una contraseña
        suya, esperar a que la víctima entrara con Google y compartir la cuenta
        (secuestro por pre-registro). Quien tiene el correo entra con Google.
        """
        if not self.email_verified:
            self.hashed_password = UNUSABLE_PASSWORD
        self.email_verified = True
        self.google_sub = google_sub

    @staticmethod
    def register(username: str, email: str, raw_password: str) -> "UserAggregate":
        pw = PasswordVO(raw_password)
        if pw.is_weak():
            raise ValueError(
                f"La contraseña es demasiado débil: mínimo {PasswordVO.MIN_LENGTH} "
                "caracteres, mayúsculas, minúsculas y al menos un dígito."
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
