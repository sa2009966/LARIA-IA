from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración central cargada desde variables de entorno / .env"""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Base de datos
    DATABASE_URL: str = "mysql+pymysql://user:password@localhost:3306/laria_db"

    # Kimi / Moonshot API
    KIMI_API_KEY: str = "KIMI_API_KEY"

    # Seguridad JWT
    SECRET_KEY: str = "cambia-esto-en-produccion"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Aplicación
    APP_TITLE: str = "LARIA – Sistema Inteligente de Asistencia Educativa"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False


settings = Settings()
