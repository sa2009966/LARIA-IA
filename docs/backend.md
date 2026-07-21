# Backend LARIA — Overview

## Qué es

LARIA-IA es el **backend del tutor inteligente adaptativo**. Expone una API REST que:

1. Autentica estudiantes y administradores (JWT).
2. Gestiona materiales educativos (documentos de texto).
3. Analiza documentos y responde preguntas **acotadas al contenido**.
4. Genera y califica cuestionarios.
5. Acumula **evidencia de aprendizaje** (intentos + interacciones tutor) como base del futuro perfil cognitivo.

La IA (OpenAI) **no decide la pedagogía**: solo genera lenguaje según prompts definidos en `TutorPolicy`.

## Stack

| Capa | Tecnología |
|------|------------|
| API | FastAPI + Uvicorn |
| Dominio | Aggregates, value objects, domain events (DDD) |
| Persistencia | MongoDB (Motor) o memoria (`DB_PROVIDER=memory`) |
| IA | OpenAI Chat Completions (`gpt-4o-mini` por defecto) |
| Auth | JWT (HS256) + bcrypt |
| Contenedores | Docker Compose (app + Mongo sin puerto host) |

## Estructura de carpetas (`src/`)

```
src/
├── main.py                 # Composition root, lifespan, middlewares
├── domain/                 # Reglas de negocio (sin FastAPI/Mongo/OpenAI)
│   ├── aggregates/
│   ├── events/
│   ├── ports/              # Interfaces (repos, IAAnalyst, EventBus)
│   ├── services/           # TutorPolicy (estrategia pedagógica)
│   └── value_objects/
├── application/            # Casos de uso + DTOs + projector de evidencia
├── infrastructure/         # Adaptadores: Mongo, memory, OpenAI, rate limit, config
└── interfaces/api/         # Routers, schemas Pydantic, DI
```

## Arranque

### Local

```bash
cp .env.example .env   # rellenar SECRET_KEY y OPENAI_API_KEY
pip install -r requirements.txt
uvicorn src.main:app --reload --port 8000
```

### Docker

```bash
# .env debe incluir también MONGO_USERNAME y MONGO_PASSWORD
docker compose up --build -d
```

Variables críticas (ver `.env.example`; **nunca** versionar `.env`):

- `SECRET_KEY`, `OPENAI_API_KEY`, `IA_PROVIDER=openai`
- `DB_PROVIDER=memory|mongodb`
- `ENABLE_DOCS`, `RATE_LIMIT_ENABLED`, `DEBUG=false`

## Flujo de ramas

Rama actual de feature del backend: **`feature/backend`**.

```
feature/backend ──PR/merge──► develop ──testeo──► main
```

| Rama | Rol |
|------|-----|
| `feature/backend` | Desarrollo del API, docs y tests del backend |
| `develop` | Integración; aquí se destea el conjunto antes de release |
| `main` | Producción / estable |

### Checklist antes de merge a `develop`

- [ ] `.env` **no** está en el commit (`git check-ignore -v .env`)
- [ ] `.env.example` sin secretos reales (solo placeholders vacíos)
- [ ] `RATE_LIMIT_ENABLED=false pytest tests -q` en verde
- [ ] README y `docs/` actualizados
- [ ] Sin claves `sk-proj-…` ni hashes reales en el diff

## Qué falta (roadmap pedagógico)

- Perfil cognitivo / mastery model a partir de `/learning/me`
- Adaptación de dificultad y prompts condicionados por evidencia
- Política tutorial más rica (scaffolding, misconceptions)
- Posible router de modelos (mini vs 4o por tarea)

## Contacto de documentación

Los ADR viven en `docs/adr/`. Nuevas decisiones relevantes deben añadirse como `ADR-00N-….md`.
