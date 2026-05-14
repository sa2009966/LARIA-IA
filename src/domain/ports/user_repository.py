from abc import ABC, abstractmethod
from typing import Optional

from src.domain.entities.user import User


class UserRepository(ABC):
    """Puerto de salida: contrato para la persistencia de usuarios.

    La infraestructura implementa este contrato; el dominio solo lo conoce.
    """

    @abstractmethod
    def find_by_id(self, user_id: int) -> Optional[User]:
        ...

    @abstractmethod
    def find_by_email(self, email: str) -> Optional[User]:
        ...

    @abstractmethod
    def find_by_username(self, username: str) -> Optional[User]:
        ...

    @abstractmethod
    def save(self, user: User) -> User:
        ...

    @abstractmethod
    def delete(self, user_id: int) -> None:
        ...

    @abstractmethod
    def list_all(self) -> list[User]:
        ...
