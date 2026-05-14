from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from src.infrastructure.config import settings


engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Clase base para todos los modelos ORM de SQLAlchemy."""
    pass


def get_db_session():
    """Generador de sesión para inyección de dependencias en FastAPI."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
