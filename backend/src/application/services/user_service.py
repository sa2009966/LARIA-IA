import secrets
from uuid import UUID
from typing import Optional

from src.domain.aggregates.user_aggregate import UserAggregate
from src.domain.value_objects.email import Email
from src.domain.value_objects.password import Password
from src.domain.ports.external_identity import ExternalIdentity
from src.domain.ports.repositories import UserRepository
from src.domain.ports.event_bus import EventBus
from src.application.dto.user_dto import UserDTO, RegisterUserDTO

_MSG_CONFLICTO = "Ya existe un usuario con esos datos"
_MSG_CREDENCIALES = "Credenciales invalidas"
# Hash dummy para igualar el coste de bcrypt cuando el usuario no existe (anti-timing).
_DUMMY_HASH = Password("DummyHash1x!!").hash()


def _proveedor(user: UserAggregate) -> str:
    if user.clerk_user_id:
        return "clerk"
    if user.google_sub:
        return "google"
    return "password"


class UserService:
    def __init__(self, user_repository: UserRepository, event_bus: Optional[EventBus] = None) -> None:
        self._user_repo = user_repository
        self._event_bus = event_bus

    async def register(self, dto: RegisterUserDTO) -> UserDTO:
        existing = await self._user_repo.find_by_email(Email(dto.email))
        if existing is not None:
            raise ValueError(_MSG_CONFLICTO)
        existing = await self._user_repo.find_by_username(dto.username)
        if existing is not None:
            raise ValueError(_MSG_CONFLICTO)

        user = UserAggregate.register(dto.username, dto.email, dto.password)
        await self._user_repo.save(user)

        if self._event_bus:
            for event in user.events:
                await self._event_bus.publish(event)
        user.clear_events()

        return self._to_dto(user)

    async def login_with_external(self, identity: ExternalIdentity) -> UserDTO:
        """Entra con una identidad verificada (Google). Crea la cuenta si no existe (ADR-025).

        El correo es la identidad: Google garantiza que es de quien inicia sesión.
        Si ya hay una cuenta con ese correo, se vincula (ver `link_google`).
        """
        user = await self._user_repo.find_by_email(Email(identity.email))
        if user is not None:
            if not user.is_active:
                raise ValueError("Usuario inactivo")
            if user.google_sub != identity.subject or not user.email_verified:
                user.link_google(identity.subject)
                await self._user_repo.save(user)
            return self._to_dto(user)

        user = UserAggregate.register_verified(
            await self._username_libre(identity), identity.email, identity.subject
        )
        await self._user_repo.save(user)
        if self._event_bus:
            for event in user.events:
                await self._event_bus.publish(event)
        user.clear_events()
        return self._to_dto(user)

    async def resolve_clerk_user(self, clerk_user_id: str, clerk_client) -> UserAggregate:
        """El usuario nuestro de una sesión de Clerk; lo vincula o lo crea la primera vez (ADR-027).

        Solo la primera vez se consulta a Clerk (correo primario y si está
        verificado). Después basta `clerk_user_id`: una búsqueda por índice.
        """
        user = await self._user_repo.find_by_clerk_id(clerk_user_id)
        if user is not None:
            return user
        datos = await clerk_client.get_user(clerk_user_id)
        if not datos.email or not datos.email_verified:
            # Sin correo verificado no se enlaza con nada: sería la puerta del
            # secuestro por pre-registro que el enlace por correo evita.
            raise PermissionError("Verifica tu correo en Clerk para entrar.")
        user = await self._user_repo.find_by_email(Email(datos.email))
        if user is None:
            identidad = ExternalIdentity(subject=clerk_user_id, email=datos.email, name=datos.username)
            user = UserAggregate.register_from_clerk(
                await self._username_libre(identidad), datos.email, clerk_user_id
            )
            nuevo = True
        else:
            user.link_clerk(clerk_user_id)
            nuevo = False
        try:
            await self._user_repo.save(user)
        except Exception:
            # Dos primeras peticiones a la vez: la otra ya lo creó o vinculó
            # (índices únicos de correo y clerk_user_id). Se usa ese.
            existente = await self._user_repo.find_by_clerk_id(clerk_user_id)
            if existente is None:
                raise
            return existente
        if nuevo and self._event_bus:
            for event in user.events:
                await self._event_bus.publish(event)
        user.clear_events()
        return user

    async def _username_libre(self, identity: ExternalIdentity) -> str:
        """Nombre visible a partir del nombre de Google o del correo, sin chocar."""
        base = (identity.name or identity.email.split("@")[0]).strip()[:48] or "estudiante"
        if len(base) < 2:
            base = f"{base}_estudiante"
        candidato = base
        for _ in range(20):
            if await self._user_repo.find_by_username(candidato) is None:
                return candidato
            candidato = f"{base}_{secrets.token_hex(2)}"
        return f"{base}_{secrets.token_hex(4)}"

    async def authenticate(self, email: str, plain_password: str) -> UserDTO:
        user = await self._user_repo.find_by_email(Email(email))
        if user is None:
            Password.verify(plain_password, _DUMMY_HASH)
            raise ValueError(_MSG_CREDENCIALES)
        if not Password.verify(plain_password, user.hashed_password):
            raise ValueError(_MSG_CREDENCIALES)
        if not user.is_active:
            raise ValueError("Usuario inactivo")
        return self._to_dto(user)

    async def get_by_id(self, user_id: UUID) -> UserDTO:
        user = await self._user_repo.find_by_id(user_id)
        if user is None:
            raise ValueError(f"Usuario con id={user_id} no encontrado")
        return self._to_dto(user)

    async def list_users(self) -> list[UserDTO]:
        users = await self._user_repo.list_all()
        return [self._to_dto(u) for u in users]

    async def deactivate_user(self, user_id: UUID) -> None:
        user = await self._user_repo.find_by_id(user_id)
        if user is None:
            raise ValueError(f"Usuario con id={user_id} no encontrado")
        user.deactivate()
        await self._user_repo.save(user)
        if self._event_bus:
            for event in user.events:
                await self._event_bus.publish(event)
        user.clear_events()

    def _to_dto(self, user: UserAggregate) -> UserDTO:
        return UserDTO(
            id=user.id,
            username=user.username,
            email=user.email.value,
            role=user.role.value,
            is_active=user.is_active,
            created_at=user.created_at,
            email_verified=user.email_verified,
            has_password=user.has_password(),
            auth_provider=_proveedor(user),
        )
