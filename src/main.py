from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse

from src.infrastructure.config import settings, validate_ia_settings, validate_security_settings
from src.infrastructure.rate_limit import RateLimitMiddleware
from src.interfaces.api.routers import auth, documents, learning, quizzes, users

validate_security_settings(settings)
validate_ia_settings(settings)


async def _bootstrap_admin() -> None:
    """Crea el usuario administrador inicial si ADMIN_EMAIL y ADMIN_PASSWORD están definidos."""
    if not settings.ADMIN_EMAIL or not settings.ADMIN_PASSWORD:
        return

    from src.domain.aggregates.user_aggregate import UserAggregate, UserRole
    from src.domain.value_objects.email import Email
    from src.interfaces.api.dependencies import get_user_repo

    repo = get_user_repo()
    existing = await repo.find_by_email(Email(settings.ADMIN_EMAIL))
    if existing is not None:
        return

    try:
        admin = UserAggregate.register(settings.ADMIN_USERNAME, settings.ADMIN_EMAIL, settings.ADMIN_PASSWORD)
    except ValueError as exc:
        raise RuntimeError(f"No se pudo crear el admin inicial (revisa ADMIN_EMAIL/ADMIN_PASSWORD): {exc}") from exc
    admin.change_role(UserRole.ADMIN)
    admin.clear_events()
    await repo.save(admin)


async def _register_learning_projector() -> None:
    from src.application.services.learning_evidence_projector import LearningEvidenceProjector
    from src.interfaces.api.dependencies import get_event_bus, get_interaction_repo

    projector = LearningEvidenceProjector(get_interaction_repo(), get_event_bus())
    await projector.register()


async def _ensure_mongo_indexes() -> None:
    if settings.DB_PROVIDER != "mongodb":
        return
    from src.infrastructure.mongodb.user_repository import MongoDBUserRepository

    await MongoDBUserRepository().ensure_indexes()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _ensure_mongo_indexes()
    await _bootstrap_admin()
    await _register_learning_projector()
    yield
    if settings.DB_PROVIDER == "mongodb":
        from src.infrastructure.mongodb.database import close_database
        await close_database()


_docs = "/docs" if settings.ENABLE_DOCS else None
_redoc = "/redoc" if settings.ENABLE_DOCS else None
_openapi = "/openapi.json" if settings.ENABLE_DOCS else None

app = FastAPI(
    title=settings.APP_TITLE,
    version=settings.APP_VERSION,
    # Nunca exponer tracebacks de FastAPI debug al cliente.
    debug=False,
    docs_url=_docs,
    redoc_url=_redoc,
    openapi_url=_openapi,
    lifespan=lifespan,
)

app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PREFIX = "/api/v1"

app.include_router(auth.router, prefix=PREFIX)
app.include_router(users.router, prefix=PREFIX)
app.include_router(documents.router, prefix=PREFIX)
app.include_router(quizzes.router, prefix=PREFIX)
app.include_router(learning.router, prefix=PREFIX)


@app.get("/", include_in_schema=False)
def root():
    if settings.ENABLE_DOCS:
        return RedirectResponse(url="/docs")
    return JSONResponse({"service": "LARIA", "health": "/health", "version": settings.APP_VERSION})


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok", "version": settings.APP_VERSION}
