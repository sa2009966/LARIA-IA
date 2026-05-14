from typing import Optional

from sqlalchemy.orm import Session

from src.domain.entities.user import User
from src.domain.ports.user_repository import UserRepository
from src.infrastructure.db.models import UserModel


class SQLAlchemyUserRepository(UserRepository):
    """Adaptador: implementa el puerto UserRepository usando SQLAlchemy + MySQL."""

    def __init__(self, session: Session) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Helpers de mapeo: ORM <-> Entidad de dominio
    # ------------------------------------------------------------------

    @staticmethod
    def _to_entity(model: UserModel) -> User:
        return User(
            id=model.id,
            username=model.username,
            email=model.email,
            hashed_password=model.hashed_password,
            role=model.role,
            is_active=model.is_active,
            created_at=model.created_at,
        )

    @staticmethod
    def _to_model(user: User) -> UserModel:
        return UserModel(
            id=user.id,
            username=user.username,
            email=user.email,
            hashed_password=user.hashed_password,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at,
        )

    # ------------------------------------------------------------------
    # Implementación del contrato
    # ------------------------------------------------------------------

    def find_by_id(self, user_id: int) -> Optional[User]:
        model = self._session.get(UserModel, user_id)
        return self._to_entity(model) if model else None

    def find_by_email(self, email: str) -> Optional[User]:
        model = self._session.query(UserModel).filter_by(email=email).first()
        return self._to_entity(model) if model else None

    def find_by_username(self, username: str) -> Optional[User]:
        model = self._session.query(UserModel).filter_by(username=username).first()
        return self._to_entity(model) if model else None

    def save(self, user: User) -> User:
        if user.id is None:
            model = self._to_model(user)
            self._session.add(model)
        else:
            model = self._session.get(UserModel, user.id)
            if model is None:
                raise ValueError(f"Usuario con id={user.id} no encontrado en BD.")
            model.username = user.username
            model.email = user.email
            model.hashed_password = user.hashed_password
            model.role = user.role
            model.is_active = user.is_active

        self._session.commit()
        self._session.refresh(model)
        return self._to_entity(model)

    def delete(self, user_id: int) -> None:
        model = self._session.get(UserModel, user_id)
        if model:
            self._session.delete(model)
            self._session.commit()

    def list_all(self) -> list[User]:
        models = self._session.query(UserModel).all()
        return [self._to_entity(m) for m in models]
