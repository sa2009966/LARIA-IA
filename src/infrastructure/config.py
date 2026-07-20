from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración central cargada desde variables de entorno / .env"""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Proveedor de IA: "kimi" o "openai"
    IA_PROVIDER: str = "kimi"

    # Kimi / Moonshot API
    KIMI_API_KEY: str = "KIMI_API_KEY"

    # OpenAI API
    OPENAI_API_KEY: str = "OPENAI_API_KEY"
    OPENAI_MODEL: str = "gpt-4o-mini"

    # Seguridad JWT
    SECRET_KEY: str = "cambia-esto-en-produccion"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Base de datos: "memory" o "mongodb"
    DB_PROVIDER: str = "memory"

    # MongoDB
    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "laria_db"

    # Aplicación
    APP_TITLE: str = "LARIA – Sistema Inteligente de Asistencia Educativa"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False


settings = Settings()
