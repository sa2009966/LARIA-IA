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
    CORS_ORIGINS: Annotated[list[str], NoDecode] = [
        "http://localhost:3000",
        "http://localhost:4321",
    ]

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
    # Selección de servidor y conexión. 3 s van bien en local; en Atlas conviene
    # subirlo (SRV + TLS + tier compartido en frío).
    MONGODB_TIMEOUT_MS: int = 3_000

    # Upload de materiales (multipart / JSON). 200 MiB por defecto.
    DOCUMENT_MAX_UPLOAD_BYTES: int = 26_214_400  # 25 MiB
    # Dónde vive el archivo original (el texto extraído siempre va al blob de
    # contenido). `blob` = donde el texto (GridFS/memoria); `r2` = Cloudflare R2.
    ORIGINAL_STORAGE: str = "blob"  # blob | r2
    R2_ENDPOINT_URL: str = ""  # https://<account_id>.r2.cloudflarestorage.com
    R2_BUCKET: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_PREFIX: str = "documents/"

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

    # Motor adaptativo (ADR-004). Son hipótesis nombradas, no constantes:
    # se calibran con datos de outcome, no se tocan a ojo.
    ADAPT_SHADOW_MODE: bool = True  # computa señales sin inyectarlas al prompt
    ADAPT_BAND_LOW: float = 0.34
    ADAPT_BAND_HIGH: float = 0.67
    ADAPT_CUT_ABANDONMENT: float = 0.55
    ADAPT_CUT_ATTENTION_SPAN: float = 0.6
    ADAPT_CUT_PREFERENCE: float = 0.4
    ADAPT_EWMA_ALPHA: float = 0.3
    ADAPT_LONG_EXPLANATION_CHARS: int = 900
    ADAPT_SESSION_GAP_MINUTES: int = 20
    ADAPT_MIN_SAMPLES: int = 5
    LOG_LEVEL: str = "INFO"  # DEBUG | INFO | WARNING | ERROR
    LOG_FORMAT: str = "text"  # text | json


def _is_wildcard_cors_origin(origin: str) -> bool:
    token = origin.strip().rstrip("/")
    return token in {"*", "null"} or token.endswith("*")


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
    """Fail-fast de producción: Mongo, outbox, docs cerrados."""
    env = (s.APP_ENV or "development").lower().strip()
    if env not in {"development", "production"}:
        raise RuntimeError("APP_ENV debe ser 'development' o 'production'.")
    almacen = (s.ORIGINAL_STORAGE or "blob").lower().strip()
    if almacen not in {"blob", "r2"}:
        raise RuntimeError("ORIGINAL_STORAGE debe ser 'blob' o 'r2'.")
    if almacen == "r2":
        # Mejor no arrancar que arrancar y perder los archivos de los alumnos
        # en el primer upload por una variable a medias.
        faltan = [
            nombre
            for nombre, valor in (
                ("R2_ENDPOINT_URL", s.R2_ENDPOINT_URL),
                ("R2_BUCKET", s.R2_BUCKET),
                ("R2_ACCESS_KEY_ID", s.R2_ACCESS_KEY_ID),
                ("R2_SECRET_ACCESS_KEY", s.R2_SECRET_ACCESS_KEY),
            )
            if not (valor or "").strip()
        ]
        if faltan:
            raise RuntimeError(
                "ORIGINAL_STORAGE=r2 exige " + ", ".join(faltan) + "."
            )
    if env == "production":
        if s.DB_PROVIDER != "mongodb":
            raise RuntimeError(
                "APP_ENV=production exige DB_PROVIDER=mongodb (memory no es multi-réplica)."
            )
        if not (s.MONGODB_URL or "").strip():
            raise RuntimeError("APP_ENV=production exige MONGODB_URL no vacío.")
        if s.ENABLE_DOCS:
            raise RuntimeError(
                "APP_ENV=production exige ENABLE_DOCS=false (Swagger no en producción)."
            )
        backend = (s.RATE_LIMIT_BACKEND or "memory").lower().strip()
        if backend not in {"memory", "redis"}:
            raise RuntimeError("RATE_LIMIT_BACKEND debe ser 'memory' o 'redis'.")
        bus = (s.EVENT_BUS_BACKEND or "memory").lower().strip()
        if bus not in {"memory", "outbox"}:
            raise RuntimeError("EVENT_BUS_BACKEND debe ser 'memory' o 'outbox'.")
        if bus != "outbox":
            raise RuntimeError(
                "APP_ENV=production con DB_PROVIDER=mongodb exige EVENT_BUS_BACKEND=outbox "
                "(durabilidad de evidencia pedagógica entre réplicas/reinicios)."
            )
        if backend != "redis":
            raise RuntimeError(
                "APP_ENV=production exige RATE_LIMIT_BACKEND=redis (rate limit compartido)."
            )
        cache = (s.CACHE_BACKEND or "memory").lower().strip()
        if cache not in {"memory", "redis"}:
            raise RuntimeError("CACHE_BACKEND debe ser 'memory' o 'redis'.")
        if cache != "redis":
            raise RuntimeError("APP_ENV=production exige CACHE_BACKEND=redis.")
        if not (s.REDIS_URL or "").strip():
            raise RuntimeError("APP_ENV=production exige REDIS_URL no vacío.")
        if not s.RATE_LIMIT_ENABLED:
            raise RuntimeError("APP_ENV=production exige RATE_LIMIT_ENABLED=true.")
        origins = [str(o).strip() for o in (s.CORS_ORIGINS or []) if str(o).strip()]
        if not origins:
            raise RuntimeError(
                "APP_ENV=production exige CORS_ORIGINS no vacío (orígenes del front real)."
            )
        if any(_is_wildcard_cors_origin(o) for o in origins):
            raise RuntimeError(
                "APP_ENV=production no admite CORS_ORIGINS comodín (*)."
            )


settings = Settings()
