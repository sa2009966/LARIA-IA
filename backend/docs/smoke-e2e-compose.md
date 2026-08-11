# Smoke E2E contra Docker Compose (IA stub / sin OpenAI en CI)

El flujo pedagógico automatizado (sin OpenAI) vive en
`tests/api/test_pedagogical_flow_e2e.py` (3 corridas parametrizadas).

Este documento cubre el smoke **manual** contra Compose con persistencia real.

## Prerrequisitos

```bash
cd backend
# .env con SECRET_KEY, OPENAI_API_KEY (o stub local), MONGO_USERNAME, MONGO_PASSWORD
docker compose up --build -d
```

Compose usa: `DB_PROVIDER=mongodb`, `EVENT_BUS_BACKEND=outbox`,
`RATE_LIMIT_BACKEND=redis`, `CACHE_BACKEND=redis`, `APP_ENV=production`,
`ENABLE_DOCS=false`.

## Flujo

1. `POST /api/v1/auth/register` → usuario + password fuerte.
2. `POST /api/v1/auth/token` → JWT.
3. `POST /api/v1/documents/` o `/upload` (GridFS para blob grande).
4. `POST /api/v1/documents/{id}/analyze`
5. `POST /api/v1/documents/{id}/ask`
6. `POST /api/v1/documents/{id}/quiz`
7. `POST /api/v1/quizzes/{quiz_id}/attempts`
8. `GET /api/v1/learning/me` y `GET /api/v1/learning/me/profile`

## Persistencia post-reinicio

```bash
docker compose restart app
# repetir GET /learning/me/profile — mismos datos
```

## Rate limit Redis entre procesos

Con dos workers/réplicas apuntando al mismo Redis, el contador de
`RATE_LIMIT_BACKEND=redis` es compartido (smoke manual: disparar auth desde
dos clientes hasta 429).

## Nota sobre IA

En CI no se llama a OpenAI: usar el test API con stub. Contra Compose real se
necesita `OPENAI_API_KEY` válida o un mock en el borde (no incluido en la imagen).
