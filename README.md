# LARIA-IA (Backend)

Tutor inteligente adaptativo. Backend **FastAPI** con **DDD / Clean Architecture**, persistencia **MongoDB** (o memoria en desarrollo), proveedor de IA **OpenAI** (`gpt-4o-mini` por defecto) y autenticación **JWT** con roles.

> LARIA no es un chatbot: el modelo solo genera lenguaje. La estrategia pedagógica vive en el dominio/aplicación (`TutorPolicy`, evidencia de aprendizaje).

## Documentación

| Documento | Contenido |
|-----------|-----------|
| [docs/backend.md](docs/backend.md) | Visión del backend, stack, cómo arrancar y flujo de ramas |
| [docs/architecture.md](docs/architecture.md) | Capas, agregados, puertos, flujo de datos |
| [docs/endpoints.md](docs/endpoints.md) | Catálogo de endpoints REST `/api/v1` |
| [docs/adr/ADR-001-openai-hexagonal-tutor.md](docs/adr/ADR-001-openai-hexagonal-tutor.md) | Decisiones arquitectónicas (ADR-1) |

## Requisitos previos

- Python 3.13+ **o** Docker
- `SECRET_KEY` ≥ 32 caracteres (`openssl rand -hex 32`)
- `OPENAI_API_KEY` válida

## Configuración (sin secretos en git)

```bash
cp .env.example .env
# Edita .env: SECRET_KEY, OPENAI_API_KEY
# Docker Compose también exige MONGO_USERNAME y MONGO_PASSWORD
```

**Nunca** subas `.env` al repositorio. Solo se versiona `.env.example` (valores vacíos).

En producción pública: `ENABLE_DOCS=false`, `DEBUG=false`, `RATE_LIMIT_ENABLED=true`.

## Ejecución local

```bash
pip install -r requirements.txt
uvicorn src.main:app --reload --port 8000
```

- API: http://localhost:8000  
- Swagger (si `ENABLE_DOCS=true`): http://localhost:8000/docs  
- Health: http://localhost:8000/health  

## Ejecución con Docker

```bash
docker compose up --build -d
```

MongoDB autenticado **sin** puertos expuestos al host. API en el puerto `8000`.

## Tests

```bash
pip install -r requirements-dev.txt
RATE_LIMIT_ENABLED=false pytest tests -q
```

Incluye unitarios (`tests/unit`) y API (`tests/api` con TestClient).

## Flujo de ramas (backend)

```
feature/backend  →  develop  →  main
```

1. Desarrollar y documentar en `feature/backend` (esta rama de feature).
2. Fusionar a `develop` y **testear** integración allí.
3. Solo cuando `develop` esté estable, promover a `main`.

## Seguridad rápida

- JWT HS256 fijado en código; `SECRET_KEY` fail-closed al arrancar.
- Contraseñas bcrypt; política ≥12 chars con mayúsculas, minúsculas y dígito.
- Rate limiting en auth y rutas de IA.
- Ownership: recursos ajenos responden 404 (sin oráculo 403/404).
- OpenAPI/docs desactivables con `ENABLE_DOCS`.
