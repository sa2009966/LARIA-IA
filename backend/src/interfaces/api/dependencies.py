"""Proveedores de dependencias FastAPI: conectan los adaptadores a los servicios."""
from functools import lru_cache
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from src.application.services.analyze_document_service import AnalyzeDocumentService
from src.application.services.document_service import DocumentService
from src.application.services.learning_query_service import LearningQueryService
from src.application.services.llm_gate import LlmGate
from src.application.services.quiz_service import QuizService
from src.application.services.user_service import UserService
from src.domain.aggregates.user_aggregate import UserAggregate
from src.domain.ports.cache_port import CachePort
from src.domain.ports.embodiment import (
    DeviceCommandPort,
    PresencePort,
    SensorInputPort,
    SpeechToTextPort,
    TextToSpeechPort,
)
from src.domain.ports.event_bus import EventBus
from src.domain.ports.ia_analyst import IAAnalyst
from src.domain.ports.metrics_port import MetricsPort
from src.domain.ports.document_blob_store import DocumentBlobStore
from src.domain.ports.repositories import (
    ChatRepository,
    DocumentRepository,
    QuizAttemptRepository,
    QuizRepository,
    StudentProfileRepository,
    TutorInteractionRepository,
    TutorSessionRepository,
    UserRepository,
)
from src.domain.services.affect_policy import AffectPolicy
from src.domain.services.model_router import ModelRouter
from src.domain.services.pedagogical_engine import PedagogicalEngine
from src.domain.services.recommendation_engine import RecommendationEngine
from src.infrastructure.config import JWT_ALGORITHM, settings
from src.infrastructure.embodiment.stubs import (
    LogOnlyPresence,
    NullDeviceCommand,
    NullSensorInput,
    NullSpeechToText,
    NullTextToSpeech,
)
from src.infrastructure.openai.openai_ia_analyst import OpenAIAnalyst
from src.infrastructure.persistence import (
    InMemoryChatRepository,
    InMemoryDocumentRepository,
    InMemoryEventBus,
    InMemoryQuizAttemptRepository,
    InMemoryQuizRepository,
    InMemoryStudentProfileRepository,
    InMemoryTutorInteractionRepository,
    InMemoryTutorSessionRepository,
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
def get_document_blob_store() -> DocumentBlobStore:
    if settings.DB_PROVIDER == "mongodb":
        from src.infrastructure.mongodb.gridfs_document_blob_store import (
            GridFSDocumentBlobStore,
        )

        return GridFSDocumentBlobStore()
    from src.infrastructure.persistence.in_memory_document_blob_store import (
        InMemoryDocumentBlobStore,
    )

    return InMemoryDocumentBlobStore()


@lru_cache(maxsize=1)
def get_document_repo() -> DocumentRepository:
    blob_store = get_document_blob_store()
    if settings.DB_PROVIDER == "mongodb":
        from src.infrastructure.mongodb import MongoDBDocumentRepository

        return MongoDBDocumentRepository(blob_store=blob_store)
    return InMemoryDocumentRepository(blob_store=blob_store)


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
def get_session_repo() -> TutorSessionRepository:
    if settings.DB_PROVIDER == "mongodb":
        from src.infrastructure.mongodb import MongoDBTutorSessionRepository
        return MongoDBTutorSessionRepository()
    return InMemoryTutorSessionRepository()


@lru_cache(maxsize=1)
def get_chat_repo() -> ChatRepository:
    if settings.DB_PROVIDER == "mongodb":
        from src.infrastructure.mongodb import MongoDBChatRepository
        return MongoDBChatRepository()
    return InMemoryChatRepository()


def get_chat_tutor_service() -> "ChatTutorService":
    from src.application.services.chat_tutor_service import ChatTutorService

    return ChatTutorService(
        analyze_service=get_analyze_service(),
        llm_gate=get_llm_gate(),
        document_repository=get_document_repo(),
        profile_repository=get_profile_repo(),
    )


@lru_cache(maxsize=1)
def get_metrics() -> MetricsPort:
    from src.infrastructure.metrics.in_memory_metrics import InMemoryMetrics

    return InMemoryMetrics()


@lru_cache(maxsize=1)
def get_ia_analyst() -> IAAnalyst:
    return OpenAIAnalyst(metrics=get_metrics())


@lru_cache(maxsize=1)
def get_cache() -> CachePort:
    backend = (settings.CACHE_BACKEND or "memory").lower().strip()
    if backend == "redis":
        from src.infrastructure.cache.cache_adapters import RedisCache

        return RedisCache(settings.REDIS_URL)
    from src.infrastructure.cache.cache_adapters import InMemoryCache

    return InMemoryCache()


@lru_cache(maxsize=1)
def get_model_router() -> ModelRouter:
    default = settings.OPENAI_MODEL_DEFAULT or settings.OPENAI_MODEL
    strong = settings.OPENAI_MODEL_STRONG or "gpt-4o"
    return ModelRouter(default_model=default, strong_model=strong)


@lru_cache(maxsize=1)
def get_llm_gate() -> LlmGate:
    return LlmGate(
        ia_analyst=get_ia_analyst(),
        cache=get_cache(),
        model_router=get_model_router(),
        metrics=get_metrics(),
        quiz_repository=get_quiz_repo(),
    )


@lru_cache(maxsize=1)
def get_event_bus() -> EventBus:
    backend = (settings.EVENT_BUS_BACKEND or "memory").lower().strip()
    if backend == "outbox" and settings.DB_PROVIDER == "mongodb":
        from src.infrastructure.mongodb.outbox_event_bus import MongoOutboxEventBus

        return MongoOutboxEventBus(
            metrics=get_metrics() if settings.METRICS_ENABLED else None,
        )
    return InMemoryEventBus()


@lru_cache(maxsize=1)
def get_pedagogical_engine() -> PedagogicalEngine:
    return PedagogicalEngine()


@lru_cache(maxsize=1)
def get_speech_to_text() -> SpeechToTextPort:
    metrics = get_metrics() if settings.METRICS_ENABLED else None
    return NullSpeechToText(metrics=metrics)


@lru_cache(maxsize=1)
def get_text_to_speech() -> TextToSpeechPort:
    metrics = get_metrics() if settings.METRICS_ENABLED else None
    return NullTextToSpeech(metrics=metrics)


@lru_cache(maxsize=1)
def get_presence() -> PresencePort:
    metrics = get_metrics() if settings.METRICS_ENABLED else None
    return LogOnlyPresence(metrics=metrics)


@lru_cache(maxsize=1)
def get_device_command() -> DeviceCommandPort:
    metrics = get_metrics() if settings.METRICS_ENABLED else None
    return NullDeviceCommand(metrics=metrics)


@lru_cache(maxsize=1)
def get_sensor_input() -> SensorInputPort:
    metrics = get_metrics() if settings.METRICS_ENABLED else None
    return NullSensorInput(metrics=metrics)


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
        session_repository=get_session_repo(),
        blob_store=get_document_blob_store(),
        max_upload_bytes=settings.DOCUMENT_MAX_UPLOAD_BYTES,
    )


def get_analyze_service() -> AnalyzeDocumentService:
    return AnalyzeDocumentService(
        document_repository=get_document_repo(),
        ia_analyst=get_ia_analyst(),
        event_bus=get_event_bus(),
        interaction_repository=get_interaction_repo(),
        profile_repository=get_profile_repo(),
        pedagogical_engine=get_pedagogical_engine(),
        session_repository=get_session_repo(),
        llm_gate=get_llm_gate(),
        metrics=get_metrics() if settings.METRICS_ENABLED else None,
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
        session_repository=get_session_repo(),
        llm_gate=get_llm_gate(),
    )


def get_learning_query_service() -> LearningQueryService:
    return LearningQueryService(
        attempt_repository=get_attempt_repo(),
        interaction_repository=get_interaction_repo(),
        profile_repository=get_profile_repo(),
        recommendation_engine=RecommendationEngine(),
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
