from pydantic_settings import BaseSettings, SettingsConfigDict

# Valores que jamás deben usarse como SECRET_KEY en ejecución real.
_INSECURE_SECRET_KEYS = {"", "cambia-esto-en-produccion", "changeme", "secret"}

# Algoritmo JWT fijo (no configurable por entorno).
JWT_ALGORITHM = "HS256"


class Settings(BaseSettings):
    """Configuración central cargada desde variables de entorno / .env"""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Proveedor de IA: solo "openai" (legacy "kimi" rechazado al arrancar)
    IA_PROVIDER: str = "openai"

    # OpenAI API
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"

    # Seguridad JWT
    SECRET_KEY: str = ""
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # CORS: orígenes permitidos del frontend (JSON array en la variable de entorno)
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    # Admin inicial opcional (se crea al arrancar si ambos están definidos)
    ADMIN_USERNAME: str = "admin"
    ADMIN_EMAIL: str = ""
    ADMIN_PASSWORD: str = ""

    # Base de datos: "memory" o "mongodb"
    DB_PROVIDER: str = "memory"

    # MongoDB
    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "laria_db"

    # Aplicación
    APP_TITLE: str = "LARIA – Sistema Inteligente de Asistencia Educativa"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    ENABLE_DOCS: bool = False
    RATE_LIMIT_ENABLED: bool = True
    EMBODIMENT_ENABLED: bool = False


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


settings = Settings()
