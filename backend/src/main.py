from contextlib import asynccontextmanager
import asyncio
import logging
import uuid

from fastapi import FastAPI, Request, status
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.infrastructure.config import (
    settings,
    validate_ia_settings,
    validate_runtime_settings,
    validate_security_settings,
)
from src.infrastructure.logging_setup import configure_logging
from src.infrastructure.rate_limit import RateLimitMiddleware
from src.infrastructure.request_logging import RequestLoggingMiddleware
from src.interfaces.api.routers import auth, chats, documents, learning, quizzes, users
from src.interfaces.schemas.http_errors import HTTPErrorBody

configure_logging(level=settings.LOG_LEVEL, fmt=settings.LOG_FORMAT)
validate_security_settings(settings)
validate_ia_settings(settings)
validate_runtime_settings(settings)

_logger = logging.getLogger("laria.http")
_INTERNAL_ERROR_DETAIL = "Error interno del servidor."


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
    from src.interfaces.api.dependencies import (
        get_attempt_repo,
        get_event_bus,
        get_interaction_repo,
        get_metrics,
        get_profile_repo,
        get_quiz_repo,
    )

    projector = LearningEvidenceProjector(
        get_interaction_repo(),
        get_event_bus(),
        profile_repository=get_profile_repo(),
        quiz_repository=get_quiz_repo(),
        attempt_repository=get_attempt_repo(),
        metrics=get_metrics() if settings.METRICS_ENABLED else None,
    )
    await projector.register()


async def _warm_embodiment_stubs() -> None:
    """Carga stubs de embodiment si el flag está activo; no afecta pedagogía."""
    if not settings.EMBODIMENT_ENABLED:
        return
    from src.interfaces.api.dependencies import (
        get_affect_policy,
        get_presence,
        get_speech_to_text,
        get_text_to_speech,
    )

    get_speech_to_text()
    get_text_to_speech()
    get_presence()
    get_affect_policy()
    from src.interfaces.api.dependencies import get_device_command, get_sensor_input

    get_device_command()
    get_sensor_input()


async def _ensure_mongo_indexes() -> None:
    if settings.DB_PROVIDER != "mongodb":
        return
    from src.infrastructure.mongodb.indexes import ensure_all_indexes

    await ensure_all_indexes()


async def _outbox_worker_loop(stop: asyncio.Event) -> None:
    import logging

    from src.infrastructure.mongodb.outbox_event_bus import MongoOutboxEventBus
    from src.interfaces.api.dependencies import get_event_bus, get_metrics

    logger = logging.getLogger("laria.outbox")
    bus = get_event_bus()
    if not isinstance(bus, MongoOutboxEventBus):
        return
    metrics = get_metrics() if settings.METRICS_ENABLED else None
    while not stop.is_set():
        try:
            await bus.process_pending(limit=25)
        except Exception:
            logger.exception("outbox_worker_loop_error")
            if metrics:
                metrics.incr("outbox_failed", reason="worker_loop")
        try:
            await asyncio.wait_for(stop.wait(), timeout=1.0)
        except asyncio.TimeoutError:
            continue


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _ensure_mongo_indexes()
    await _bootstrap_admin()
    await _register_learning_projector()
    await _warm_embodiment_stubs()
    stop = asyncio.Event()
    worker: asyncio.Task | None = None
    if (
        settings.DB_PROVIDER == "mongodb"
        and (settings.EVENT_BUS_BACKEND or "").lower().strip() == "outbox"
    ):
        worker = asyncio.create_task(_outbox_worker_loop(stop))
    yield
    stop.set()
    if worker is not None:
        worker.cancel()
        try:
            await worker
        except asyncio.CancelledError:
            pass
    from src.interfaces.api.dependencies import get_ia_analyst

    analyst = get_ia_analyst()
    if hasattr(analyst, "aclose"):
        await analyst.aclose()
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
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """500 controlado para Exception genérica. No convierte HTTPException/422 en 500.

    Starlette registra el handler de `Exception` en ServerErrorMiddleware (fuera de
    RequestLoggingMiddleware); por eso fijamos X-Request-Id aquí si falta.
    """
    if isinstance(exc, StarletteHTTPException):
        return await http_exception_handler(request, exc)
    if isinstance(exc, RequestValidationError):
        return await request_validation_exception_handler(request, exc)

    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    _logger.exception(
        "unhandled_exception method=%s path=%s request_id=%s exc_type=%s",
        request.method,
        request.url.path,
        request_id,
        type(exc).__name__,
    )
    body = HTTPErrorBody(detail=_INTERNAL_ERROR_DETAIL)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=body.model_dump(),
        headers={"X-Request-Id": request_id},
    )


PREFIX = "/api/v1"

app.include_router(auth.router, prefix=PREFIX)
app.include_router(users.router, prefix=PREFIX)
app.include_router(documents.router, prefix=PREFIX)
app.include_router(quizzes.router, prefix=PREFIX)
app.include_router(learning.router, prefix=PREFIX)
app.include_router(chats.router, prefix=PREFIX)


@app.get("/", include_in_schema=False)
def root():
    if settings.ENABLE_DOCS:
        return RedirectResponse(url="/docs")
    return JSONResponse({"service": "LARIA", "health": "/health", "version": settings.APP_VERSION})


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok", "version": settings.APP_VERSION}


@app.get("/ready", tags=["Health"])
async def readiness_check():
    """Readiness: dependencias opcionales según DB/Redis configurados. No sustituye /health."""
    checks: dict[str, str] = {"app": "ok"}
    ready = True
    if settings.DB_PROVIDER == "mongodb":
        try:
            from src.infrastructure.mongodb.database import get_database

            db = await get_database()
            await db.command("ping")
            checks["mongodb"] = "ok"
        except Exception as exc:  # noqa: BLE001
            checks["mongodb"] = f"error:{type(exc).__name__}"
            ready = False
    else:
        checks["mongodb"] = "skipped"
    redis_needed = (
        (settings.RATE_LIMIT_BACKEND or "").lower() == "redis"
        or (settings.CACHE_BACKEND or "").lower() == "redis"
    )
    if redis_needed:
        try:
            import redis

            client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
            client.ping()
            checks["redis"] = "ok"
        except Exception as exc:  # noqa: BLE001
            checks["redis"] = f"error:{type(exc).__name__}"
            ready = False
    else:
        checks["redis"] = "skipped"
    status = "ready" if ready else "degraded"
    code = 200 if ready else 503
    return JSONResponse(
        {"status": status, "version": settings.APP_VERSION, "checks": checks},
        status_code=code,
    )


@app.get(
    "/metrics",
    tags=["Health"],
    summary="Métricas Prometheus",
    description=(
        "Texto Prometheus (`outbox_*`, `profile_updates`, `laria_llm_latency_ms`, …). "
        "Responde **404** si `METRICS_ENABLED=false`."
    ),
    responses={
        200: {"description": "Contadores en formato Prometheus text."},
        404: {"description": "Métricas deshabilitadas (`METRICS_ENABLED=false`)."},
    },
)
def metrics_endpoint():
    if not settings.METRICS_ENABLED:
        return JSONResponse({"detail": "metrics disabled"}, status_code=404)
    from src.interfaces.api.dependencies import get_metrics
    from src.infrastructure.metrics.in_memory_metrics import InMemoryMetrics

    metrics = get_metrics()
    if isinstance(metrics, InMemoryMetrics):
        from fastapi.responses import PlainTextResponse

        return PlainTextResponse(metrics.render_prometheus(), media_type="text/plain; version=0.0.4")
    return metrics.snapshot()
