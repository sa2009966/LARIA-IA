# Backend LARIA — Overview

## Qué es

LARIA-IA es el **backend del tutor inteligente adaptativo**. Expone una API REST que:

1. Autentica estudiantes y administradores (JWT).
2. Gestiona materiales educativos (documentos de texto).
3. Analiza documentos y responde preguntas **acotadas al foco conceptual**.
4. Genera y califica cuestionarios adaptativos.
5. Mantiene **perfil cognitivo** (mastery por documento y por concepto), sesión multi-turno y recomendaciones.

La IA (OpenAI) **no decide la pedagogía**: solo genera lenguaje según `PedagogicalEngine` + `TutorPolicy`.

## Stack

| Capa | Tecnología |
|------|------------|
| API | FastAPI + Uvicorn |
| Dominio | Aggregates, value objects, domain events (DDD) |
| Persistencia | MongoDB (Motor) o memoria (`DB_PROVIDER=memory`) |
| Rate limit | Memory (dev) o Redis (Compose/prod) |
| Eventos | Memory sync o outbox Mongo + worker |
| IA | OpenAI Chat Completions (`gpt-4o-mini` por defecto) |
| Auth | JWT (HS256) + bcrypt |
| Contenedores | Docker Compose: app + Mongo + Redis |

## Escalabilidad (operación)

- `APP_ENV=production` exige `DB_PROVIDER=mongodb` (fail-fast).
- Perfil y `TutorSession` usan **versión optimista** ante escrituras concurrentes.
- Índices Mongo en colecciones calientes al arranque.
- Listados de documentos **no** hidratan `content`.
- Réplicas de API: Mongo compartido + Redis rate limit + `EVENT_BUS_BACKEND=outbox`.
- `TRUSTED_PROXIES` habilita `X-Forwarded-For` solo detrás de proxies confiables.

## Arranque

### Local

```bash
cp .env.example .env   # SECRET_KEY y OPENAI_API_KEY
pip install -r requirements.txt
uvicorn src.main:app --reload --port 8000
```

### Docker (escala horizontal lista)

```bash
# .env: MONGO_USERNAME, MONGO_PASSWORD, SECRET_KEY, OPENAI_API_KEY
docker compose up --build -d
# Escala app: docker compose up --scale app=2 -d
```

Variables críticas: `SECRET_KEY`, `OPENAI_API_KEY`, `APP_ENV`, `DB_PROVIDER`, `REDIS_URL`, `RATE_LIMIT_BACKEND`, `EVENT_BUS_BACKEND`.

## Flujo de ramas

```
feature/backend ──PR/merge──► develop ──testeo──► main
```

## Qué falta (roadmap)

- Ontología de misconceptions más rica
- Transacciones multi-doc en delete cascada
- Observabilidad (métricas de outbox / latencia OpenAI)

## Contacto de documentación

Los ADR viven en `docs/adr/`.
