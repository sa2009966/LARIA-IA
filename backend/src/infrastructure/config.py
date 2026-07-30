from typing import Annotated, Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# Valores que jamás deben usarse como SECRET_KEY en ejecución real.
_INSECURE_SECRET_KEYS = {"", "cambia-esto-en-produccion", "changeme", "secret"}

# Algoritmo JWT fijo (no configurable por entorno).
JWT_ALGORITHM = "HS256"


def _parse_cors_origins(value: Any) -> list[str]:
    """Acepta JSON array o lista CSV (Render a veces rompe las comillas del JSON)."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip().rstrip("/") for v in value if str(v).strip()]
    text = str(value).strip()
    if not text:
        return []
    if text.startswith("["):
        import json

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            # Fallback: quitar corchetes/comillas rotas y tratar como CSV
            text = text.strip("[]")
        else:
            if isinstance(parsed, list):
                return [str(v).strip().rstrip("/") for v in parsed if str(v).strip()]
            text = str(parsed)
    parts = [p.strip().strip('"').strip("'").rstrip("/") for p in text.split(",")]
    return [p for p in parts if p]


class Settings(BaseSettings):
    """Configuración central cargada desde variables de entorno / .env"""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Proveedor de IA: solo "openai" (legacy "kimi" rechazado al arrancar)
    IA_PROVIDER: str = "openai"

    # OpenAI API
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_MODEL_DEFAULT: str = "gpt-4o-mini"
    OPENAI_MODEL_STRONG: str = "gpt-4o"

    # Seguridad JWT
    SECRET_KEY: str = ""
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # CORS: JSON array o CSV. NoDecode evita que pydantic-settings falle antes del validador.
    CORS_ORIGINS: Annotated[list[str], NoDecode] = ["http://localhost:3000"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _coerce_cors_origins(cls, value: Any) -> list[str]:
        return _parse_cors_origins(value)

    # Admin inicial opcional (se crea al arrancar si ambos están definidos)
    ADMIN_USERNAME: str = "admin"
    ADMIN_EMAIL: str = ""
    ADMIN_PASSWORD: str = ""

    # Base de datos: "memory" o "mongodb"
    DB_PROVIDER: str = "memory"

    # MongoDB
    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "laria_db"

    # Upload de materiales (multipart / JSON). 200 MiB por defecto.
    DOCUMENT_MAX_UPLOAD_BYTES: int = 209_715_200

    # Redis (rate limit horizontal + caché inteligente)
    REDIS_URL: str = "redis://localhost:6379/0"
    RATE_LIMIT_BACKEND: str = "memory"  # memory | redis
    CACHE_BACKEND: str = "memory"  # memory | redis
    TRUSTED_PROXIES: str = ""  # CSV de IPs/CIDR que pueden fijar X-Forwarded-For

    # Aplicación
    APP_ENV: str = "development"  # development | production
    APP_TITLE: str = "LARIA – Sistema Inteligente de Asistencia Educativa"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    ENABLE_DOCS: bool = False
    RATE_LIMIT_ENABLED: bool = True
    EMBODIMENT_ENABLED: bool = False
    EVENT_BUS_BACKEND: str = "memory"  # memory | outbox
    METRICS_ENABLED: bool = True
    FORGETTING_HALF_LIFE_DAYS: float = 14.0
    LOG_LEVEL: str = "INFO"  # DEBUG | INFO | WARNING | ERROR
    LOG_FORMAT: str = "text"  # text | json


def validate_security_settings(s: "Settings") -> None:
    """Impide arrancar la API con una SECRET_KEY vacía o conocida.

    Genera una clave segura con: openssl rand -hex 32
    """
    if s.SECRET_KEY in _INSECURE_SECRET_KEYS or len(s.SECRET_KEY) < 32:
        raise RuntimeError(
            "SECRET_KEY insegura o ausente: define una clave de al menos 32 caracteres "
            "en la variable de entorno SECRET_KEY (p. ej. `openssl rand -hex 32`)."
        )


def validate_ia_settings(s: "Settings") -> None:
    """Exige proveedor OpenAI y API key."""
    provider = s.IA_PROVIDER.lower().strip()
    if provider != "openai":
        raise RuntimeError(
            f"IA_PROVIDER='{s.IA_PROVIDER}' no soportado. LARIA solo usa OpenAI "
            "(define IA_PROVIDER=openai)."
        )
    if not s.OPENAI_API_KEY or not s.OPENAI_API_KEY.strip():
        raise RuntimeError(
            "OPENAI_API_KEY ausente: define la clave de OpenAI en el entorno."
        )


def validate_runtime_settings(s: "Settings") -> None:
    """Fail-fast de producción: Mongo obligatorio y URL definida."""
    env = (s.APP_ENV or "development").lower().strip()
    if env not in {"development", "production"}:
        raise RuntimeError("APP_ENV debe ser 'development' o 'production'.")
    if env == "production":
        if s.DB_PROVIDER != "mongodb":
            raise RuntimeError(
                "APP_ENV=production exige DB_PROVIDER=mongodb (memory no es multi-réplica)."
            )
        if not (s.MONGODB_URL or "").strip():
            raise RuntimeError("APP_ENV=production exige MONGODB_URL no vacío.")
        backend = (s.RATE_LIMIT_BACKEND or "memory").lower().strip()
        if backend not in {"memory", "redis"}:
            raise RuntimeError("RATE_LIMIT_BACKEND debe ser 'memory' o 'redis'.")
        bus = (s.EVENT_BUS_BACKEND or "memory").lower().strip()
        if bus not in {"memory", "outbox"}:
            raise RuntimeError("EVENT_BUS_BACKEND debe ser 'memory' o 'outbox'.")


settings = Settings()
