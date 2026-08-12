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
| `CACHE_BACKEND` | `redis` (fail-fast en production) | |
| `RATE_LIMIT_BACKEND` | `redis` (fail-fast en production) | |
| `REDIS_URL` | no vacío en production | |
| `SECRET_KEY` | ≥32 chars, no default, rotada | |
| `OPENAI_API_KEY` | Presente; no en git | |
| `CORS_ORIGINS` | No vacío; sin `*`; orígenes del front (Compose local puede usar `:4321`) | |
| Render blueprint | Etiquetado **demo**; no usarlo como prod | |

## Evidencia pedagógica

| Ítem | Criterio | PASS/FAIL |
|------|----------|-----------|
| Ask → perfil | Tras `/ask` con struggle, `total_struggle_signals >= 1` | |
| Quiz → perfil | Tras attempt, `total_attempts` y mastery documento | |
| Outbox | `outbox_processed` sube; ask/quiz con `last_error=null` | |
| Unsupported | eventos no pedagógicos → `outbox_unsupported` (no mezclar con failed) | |
| Persistencia | Datos vivos tras reinicio del contenedor `app` | |

## Observabilidad y seguridad

| Ítem | Criterio | PASS/FAIL |
|------|----------|-----------|
| `/health` | 200; no spam INFO | |
| `/ready` | 200 si Mongo/Redis OK; 503 si caída | |
| `/metrics` | `outbox_*`, `outbox_unsupported`, `profile_updates`, `laria_llm_latency_ms` | |
| Logs | Sin tokens, passwords ni bodies | |
| Ownership | Recurso ajeno → 404 | |
| Auth | Password débil → 422; conflicto → 409; UUID malo → 422 | |

## Embodiment (opcional)

| Ítem | Criterio | PASS/FAIL |
|------|----------|-----------|
| `EMBODIMENT_ENABLED=false` | Arranque y `/ask` idénticos | |
| `EMBODIMENT_ENABLED=true` | Stubs STT/TTS/Presence/Device/Sensor; fallo ≠ 500 en pedagogía | |
| DeviceCommandPort | motion bloqueado en stub; ESTOP ack; gauge `embodiment_degraded` | |

## Cuándo usar outbox vs memory

| Modo | Cuándo basta |
|------|----------------|
| `memory` | Una réplica / demo / beta temprana (Render demo) |
| `outbox` | 2+ réplicas o durabilidad del evento si el proceso muere post-respuesta |

## Staging recomendado

Misma imagen Compose que producción (`APP_ENV=production`, Mongo+Redis+outbox, docs off) en un VPS o máquina de equipo, con secrets distintos. **No** usar Render free como staging persistente.

Compose local ya usa forma de producción (mongo + redis + outbox + cache redis).
