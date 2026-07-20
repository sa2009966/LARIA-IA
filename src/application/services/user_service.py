from uuid import UUID
from typing import Optional

from src.domain.aggregates.user_aggregate import UserAggregate
from src.domain.value_objects.email import Email
from src.domain.value_objects.password import Password
from src.domain.ports.repositories import UserRepository
from src.domain.ports.event_bus import EventBus
from src.application.dto.user_dto import UserDTO, RegisterUserDTO


class UserService:
    def __init__(self, user_repository: UserRepository, event_bus: Optional[EventBus] = None) -> None:
        self._user_repo = user_repository
        self._event_bus = event_bus

    async def register(self, dto: RegisterUserDTO) -> UserDTO:
        existing = await self._user_repo.find_by_email(Email(dto.email))
        if existing is not None:
            raise ValueError(f"Ya existe un usuario con email={dto.email}")
        existing = await self._user_repo.find_by_username(dto.username)
        if existing is not None:
            raise ValueError(f"Ya existe un usuario con username={dto.username}")

        user = UserAggregate.register(dto.username, dto.email, dto.password)
        await self._user_repo.save(user)

        if self._event_bus:
            for event in user.events:
                await self._event_bus.publish(event)
        user.clear_events()

        return self._to_dto(user)

    async def authenticate(self, email: str, plain_password: str) -> UserDTO:
        user = await self._user_repo.find_by_email(Email(email))
        if user is None:
            raise ValueError("Credenciales invalidas")
        if not Password.verify(plain_password, user.hashed_password):
            raise ValueError("Credenciales invalidas")
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
        )
