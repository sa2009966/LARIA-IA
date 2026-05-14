from passlib.context import CryptContext

from src.domain.entities.user import User
from src.domain.ports.user_repository import UserRepository

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class UserService:
    """Caso de uso: gestión del ciclo de vida de usuarios.

    Solo interactúa con el puerto UserRepository; no conoce SQLAlchemy.
    """

    def __init__(self, user_repository: UserRepository) -> None:
        self._user_repo = user_repository

    def register(self, username: str, email: str, plain_password: str, role: str = "student") -> User:
        if self._user_repo.find_by_email(email) is not None:
            raise ValueError(f"Ya existe un usuario con email={email}.")
        if self._user_repo.find_by_username(username) is not None:
            raise ValueError(f"Ya existe un usuario con username={username}.")

        hashed = _pwd_context.hash(plain_password)
        new_user = User(
            id=None,
            username=username,
            email=email,
            hashed_password=hashed,
            role=role,
        )
        return self._user_repo.save(new_user)

    def authenticate(self, email: str, plain_password: str) -> User:
        user = self._user_repo.find_by_email(email)
        if user is None or not _pwd_context.verify(plain_password, user.hashed_password):
            raise ValueError("Credenciales inválidas.")
        if not user.is_active:
            raise ValueError("Usuario inactivo.")
        return user

    def get_by_id(self, user_id: int) -> User:
        user = self._user_repo.find_by_id(user_id)
        if user is None:
            raise ValueError(f"Usuario con id={user_id} no encontrado.")
        return user

    def list_users(self) -> list[User]:
        return self._user_repo.list_all()

    def deactivate_user(self, user_id: int) -> User:
        user = self.get_by_id(user_id)
        user.deactivate()
        return self._user_repo.save(user)
