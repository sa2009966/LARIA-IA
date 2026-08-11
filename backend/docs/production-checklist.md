# Checklist de producción temprana — backend LARIA

Marca cada ítem PASS/FAIL antes de exponer el API fuera de demo.

## Configuración

| Ítem | Criterio | PASS/FAIL |
|------|----------|-----------|
| `APP_ENV` | `production` | |
| `DB_PROVIDER` | `mongodb` (fail-fast si memory) | |
| `MONGODB_URL` | Alcanzable; auth; sin exponer puerto al host público | |
| `EVENT_BUS_BACKEND` | `outbox` (fail-fast en production+mongodb) | |
| `ENABLE_DOCS` | `false` (fail-fast si true en production) | |
| `CACHE_BACKEND` / `RATE_LIMIT_BACKEND` | `redis` con `REDIS_URL` | |
| `SECRET_KEY` | ≥32 chars, no default, rotada | |
| `OPENAI_API_KEY` | Presente; no en git | |
| `CORS_ORIGINS` | Solo orígenes del front real | |
| Render blueprint | Etiquetado **demo**; no usarlo como prod | |

## Evidencia pedagógica

| Ítem | Criterio | PASS/FAIL |
|------|----------|-----------|
| Ask → perfil | Tras `/ask`, `GET /learning/me/profile` refleja struggle/style | |
| Quiz → perfil | Tras attempt, mastery/conceptos actualizados | |
| Outbox | `outbox_processed` sube; 0 `unsupported_event` para ask/quiz | |
| Persistencia | Datos vivos tras reinicio del contenedor `app` | |

## Observabilidad y seguridad

| Ítem | Criterio | PASS/FAIL |
|------|----------|-----------|
| `/health` | 200; no spam INFO | |
| `/metrics` | Contadores `outbox_*`, `profile_updates`, request-id en respuestas | |
| Logs | Sin tokens, passwords ni bodies | |
| Ownership | Recurso ajeno → 404 | |
| Auth | Password débil → 422; conflicto → 409; UUID malo → 422 | |

## Embodiment (opcional)

| Ítem | Criterio | PASS/FAIL |
|------|----------|-----------|
| `EMBODIMENT_ENABLED=false` | Arranque y `/ask` idénticos | |
| `EMBODIMENT_ENABLED=true` | Stubs con timeout; fallo TTS/STT no → 500 en pedagogía | |

## Cuándo usar outbox vs memory

| Modo | Cuándo basta |
|------|----------------|
| `memory` | Una réplica / demo / beta temprana (Render demo) |
| `outbox` | 2+ réplicas o durabilidad del evento si el proceso muere post-respuesta |

Compose local ya usa forma de producción (mongo + redis + outbox + cache redis).
