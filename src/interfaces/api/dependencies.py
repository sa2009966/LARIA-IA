"""Proveedores de dependencias FastAPI: conectan los adaptadores a los servicios."""
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from src.application.services.analyze_document_service import AnalyzeDocumentService
from src.application.services.document_service import DocumentService
from src.application.services.user_service import UserService
from src.domain.ports.ia_analyst import IAAnalyst
from src.domain.ports.repositories import UserRepository, DocumentRepository
from src.infrastructure.config import settings
from src.infrastructure.kimi.kimi_ia_analyst import KimiIAAnalyst
from src.infrastructure.openai.openai_ia_analyst import OpenAIAnalyst
from src.infrastructure.persistence import (
    InMemoryUserRepository,
    InMemoryDocumentRepository,
    InMemoryEventBus,
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


def _create_user_repo() -> UserRepository:
    if settings.DB_PROVIDER == "mongodb":
        from src.infrastructure.mongodb import MongoDBUserRepository
        return MongoDBUserRepository()
    return InMemoryUserRepository()


def _create_document_repo() -> DocumentRepository:
    if settings.DB_PROVIDER == "mongodb":
        from src.infrastructure.mongodb import MongoDBDocumentRepository
        return MongoDBDocumentRepository()
    return InMemoryDocumentRepository()


def _create_ia_analyst() -> IAAnalyst:
    provider = settings.IA_PROVIDER.lower()
    if provider == "openai":
        return OpenAIAnalyst()
    return KimiIAAnalyst()


_user_repo = _create_user_repo()
_doc_repo = _create_document_repo()
_ia_analyst = _create_ia_analyst()
_event_bus = InMemoryEventBus()


def get_user_service() -> UserService:
    return UserService(_user_repo, event_bus=_event_bus)


def get_document_service() -> DocumentService:
    return DocumentService(_doc_repo, event_bus=_event_bus)


def get_analyze_service() -> AnalyzeDocumentService:
    return AnalyzeDocumentService(_doc_repo, _ia_analyst, event_bus=_event_bus)


def get_current_user_id(token: Annotated[str, Depends(oauth2_scheme)]) -> str:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudo validar las credenciales.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise credentials_error
        return user_id
    except JWTError:
        raise credentials_error