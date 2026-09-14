from typing import Optional
from uuid import UUID

from src.domain.aggregates.user_aggregate import UserAggregate
from src.domain.ports.repositories import UserRepository
from src.domain.value_objects.email import Email


class InMemoryUserRepository(UserRepository):

    def __init__(self) -> None:
        self._users: dict[UUID, UserAggregate] = {}

    async def find_by_id(self, user_id: UUID) -> Optional[UserAggregate]:
        return self._users.get(user_id)

    async def find_by_email(self, email: Email) -> Optional[UserAggregate]:
        for user in self._users.values():
            if user.email == email:
                return user
        return None

    async def find_by_username(self, username: str) -> Optional[UserAggregate]:
        for user in self._users.values():
            if user.username == username:
                return user
        return None

    async def save(self, user: UserAggregate) -> None:
        self._users[user.id] = user

    async def delete(self, user_id: UUID) -> None:
        self._users.pop(user_id, None)

    async def list_all(self) -> list[UserAggregate]:
        return list(self._users.values())