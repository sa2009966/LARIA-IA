"""Punto de entrada de LARIA.

Responsabilidades:
- Crear la aplicación FastAPI.
- Registrar los routers (Interfaces).
- Ejecutar las migraciones / creación de tablas al arrancar.
- La Inyección de Dependencias real ocurre en interfaces/api/dependencies.py,
  que conecta cada adaptador (Infrastructure) con su puerto (Domain).
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.infrastructure.config import settings
from src.infrastructure.db.database import Base, engine
from src.interfaces.api.routers import auth, documents, users


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Al arrancar: crea las tablas si no existen (desarrollo).
    # En producción reemplazar con Alembic migrations.
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title=settings.APP_TITLE,
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Registro de routers ────────────────────────────────────────────────────
PREFIX = "/api/v1"

app.include_router(auth.router, prefix=PREFIX)
app.include_router(users.router, prefix=PREFIX)
app.include_router(documents.router, prefix=PREFIX)


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok", "version": settings.APP_VERSION}
