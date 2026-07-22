"""Proveedores de dependencias FastAPI: conectan los adaptadores a los servicios."""
from functools import lru_cache
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from src.application.services.analyze_document_service import AnalyzeDocumentService
from src.application.services.document_service import DocumentService
from src.application.services.quiz_service import QuizService
from src.application.services.user_service import UserService
from src.domain.aggregates.user_aggregate import UserAggregate
from src.domain.ports.embodiment import PresencePort, SpeechToTextPort, TextToSpeechPort
from src.domain.ports.event_bus import EventBus
from src.domain.ports.ia_analyst import IAAnalyst
from src.domain.ports.repositories import (
    DocumentRepository,
    QuizAttemptRepository,
    QuizRepository,
    StudentProfileRepository,
    TutorInteractionRepository,
    UserRepository,
)
from src.domain.services.affect_policy import AffectPolicy
from src.domain.services.pedagogical_engine import PedagogicalEngine
from src.infrastructure.config import JWT_ALGORITHM, settings
from src.infrastructure.embodiment.stubs import (
    LogOnlyPresence,
    NullSpeechToText,
    NullTextToSpeech,
)
from src.infrastructure.openai.openai_ia_analyst import OpenAIAnalyst
from src.infrastructure.persistence import (
    InMemoryDocumentRepository,
    InMemoryEventBus,
    InMemoryQuizAttemptRepository,
    InMemoryQuizRepository,
    InMemoryStudentProfileRepository,
    InMemoryTutorInteractionRepository,
    InMemoryUserRepository,
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


@lru_cache(maxsize=1)
def get_user_repo() -> UserRepository:
    if settings.DB_PROVIDER == "mongodb":
        from src.infrastructure.mongodb import MongoDBUserRepository
        return MongoDBUserRepository()
    return InMemoryUserRepository()


@lru_cache(maxsize=1)
def get_document_repo() -> DocumentRepository:
    if settings.DB_PROVIDER == "mongodb":
        from src.infrastructure.mongodb import MongoDBDocumentRepository
        return MongoDBDocumentRepository()
    return InMemoryDocumentRepository()


@lru_cache(maxsize=1)
def get_quiz_repo() -> QuizRepository:
    if settings.DB_PROVIDER == "mongodb":
        from src.infrastructure.mongodb import MongoDBQuizRepository
        return MongoDBQuizRepository()
    return InMemoryQuizRepository()


@lru_cache(maxsize=1)
def get_attempt_repo() -> QuizAttemptRepository:
    if settings.DB_PROVIDER == "mongodb":
        from src.infrastructure.mongodb import MongoDBQuizAttemptRepository
        return MongoDBQuizAttemptRepository()
    return InMemoryQuizAttemptRepository()


@lru_cache(maxsize=1)
def get_interaction_repo() -> TutorInteractionRepository:
    if settings.DB_PROVIDER == "mongodb":
        from src.infrastructure.mongodb import MongoDBTutorInteractionRepository
        return MongoDBTutorInteractionRepository()
    return InMemoryTutorInteractionRepository()


@lru_cache(maxsize=1)
def get_profile_repo() -> StudentProfileRepository:
    if settings.DB_PROVIDER == "mongodb":
        from src.infrastructure.mongodb import MongoDBStudentProfileRepository
        return MongoDBStudentProfileRepository()
    return InMemoryStudentProfileRepository()


@lru_cache(maxsize=1)
def get_ia_analyst() -> IAAnalyst:
    return OpenAIAnalyst()


@lru_cache(maxsize=1)
def get_event_bus() -> EventBus:
    return InMemoryEventBus()


@lru_cache(maxsize=1)
def get_pedagogical_engine() -> PedagogicalEngine:
    return PedagogicalEngine()


@lru_cache(maxsize=1)
def get_speech_to_text() -> SpeechToTextPort:
    return NullSpeechToText()


@lru_cache(maxsize=1)
def get_text_to_speech() -> TextToSpeechPort:
    return NullTextToSpeech()


@lru_cache(maxsize=1)
def get_presence() -> PresencePort:
    return LogOnlyPresence()


@lru_cache(maxsize=1)
def get_affect_policy() -> AffectPolicy:
    return AffectPolicy()


def get_user_service() -> UserService:
    return UserService(get_user_repo(), event_bus=get_event_bus())


def get_document_service() -> DocumentService:
    return DocumentService(
        document_repository=get_document_repo(),
        event_bus=get_event_bus(),
        quiz_repository=get_quiz_repo(),
        attempt_repository=get_attempt_repo(),
        interaction_repository=get_interaction_repo(),
        profile_repository=get_profile_repo(),
    )


def get_analyze_service() -> AnalyzeDocumentService:
    return AnalyzeDocumentService(
        document_repository=get_document_repo(),
        ia_analyst=get_ia_analyst(),
        event_bus=get_event_bus(),
        interaction_repository=get_interaction_repo(),
        profile_repository=get_profile_repo(),
        pedagogical_engine=get_pedagogical_engine(),
    )


def get_quiz_service() -> QuizService:
    return QuizService(
        document_repository=get_document_repo(),
        quiz_repository=get_quiz_repo(),
        attempt_repository=get_attempt_repo(),
        interaction_repository=get_interaction_repo(),
        ia_analyst=get_ia_analyst(),
        event_bus=get_event_bus(),
        profile_repository=get_profile_repo(),
        pedagogical_engine=get_pedagogical_engine(),
    )


_CREDENTIALS_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="No se pudo validar las credenciales.",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> UserAggregate:
    """Decodifica el JWT, carga el usuario y verifica que siga activo."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[JWT_ALGORITHM])
        subject: str | None = payload.get("sub")
        if subject is None:
            raise _CREDENTIALS_ERROR
        user_id = UUID(subject)
    except (jwt.InvalidTokenError, ValueError):
        raise _CREDENTIALS_ERROR

    user = await get_user_repo().find_by_id(user_id)
    if user is None:
        raise _CREDENTIALS_ERROR
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario inactivo.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def get_current_user_id(user: Annotated[UserAggregate, Depends(get_current_user)]) -> str:
    return str(user.id)


async def require_admin(user: Annotated[UserAggregate, Depends(get_current_user)]) -> UserAggregate:
    if not user.is_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere rol de administrador.",
        )
    return user
