# Cumplimiento del Diagrama de Gantt — Backend

**Fuente:** `LARIA_Diagrama_Gantt.xlsx` (cronograma Sep–Oct 2024).  
**Código evaluado:** rama `origin/feature/backend` (2026-07).  
**Alcance:** solo backend (Fases 1–2, 4–6 en lo que afecta API/BD). Frontend y despliegue Vercel quedan fuera.

> Nota de workspace: en `feature/frontend` el árbol local `backend/src` puede tener solo `.pyc` sin `.py`. La evaluación usa el código versionado en `feature/backend`.

## Resumen ejecutivo

El backend **cumple la mayor parte** del Gantt y, en pedagogía/persistencia, **supera** lo planificado originalmente. Los huecos claros respecto al Excel son:

1. **RAG vectorial** — no hay embeddings / vector store; el contexto sale del texto del documento (`ContextSelector`).
2. **Web scraping** — no implementado (y no aparece en el diseño actual del tutor).
3. **Pen-testing formal** — hay hardening y tests de seguridad unitarios, no un informe de penetración.
4. **Deploy en Render** — Compose/Docker listos; el despliegue cloud concreto no está documentado como hecho en repo.

Arquitectura: el Gantt pedía **Hexagonal**; el código es **Clean Architecture + DDD / hexagonal** (puertos/adaptadores). Se asume que se alineará/documentará después, como indicaste.

## Matriz de cumplimiento

| Ítem del Gantt | Estado | Evidencia |
|----------------|--------|-----------|
| **F1** Definición del problema / factibilidad | N/A código | Diseño/producto |
| **F1** Diseño arquitectura hexagonal | Cumple (con matiz DDD) | Capas `domain` / `application` / `infrastructure` / `interfaces`; ADR-001 |
| **F1** Diseño BD y esquema MongoDB | Cumple | Colecciones + índices; ver [mongodb-schema.md](mongodb-schema.md) |
| **F1** Diseño UI/UX | Fuera de alcance backend | Frontend |
| **F2** FastAPI + Docker | Cumple | `Dockerfile`, `docker-compose.yml` (app + Mongo + Redis) |
| **F2** Rutas autenticación JWT | Cumple | `POST /auth/register`, `POST /auth/token`; HS256 + bcrypt |
| **F2** OpenAI API y RAG | Parcial | OpenAI sí (`IAAnalyst`). RAG vectorial **no**; grounding por documento |
| **F2** Web scraping | No cumple | Sin scrapers / ingestión web en backend |
| **F4** MongoDB local Docker | Cumple | Servicio `mongodb:7`, DB `laria_db`, sin puerto host |
| **F4** Modelos de datos y esquemas | Cumple | Repos Motor + aggregates |
| **F4** Persistencia conversaciones | Cumple | `tutor_interactions` + `tutor_sessions` |
| **F5** Pruebas unitarias backend | Cumple | ~30 archivos de test; dominio, servicios, repos, seguridad |
| **F5** Pruebas de integración | Parcial | `tests/api`, `tests/integration`; no suite e2e Mongo real amplia |
| **F5** Seguridad y penetración | Parcial | Rate limit, ownership 404, fail-closed secrets, tests security; sin pentest formal |
| **F6** Deploy backend Render | No verificado en repo | Artefactos Docker listos; no hay config Render versionada |
| **F6** Documentación final | Cumple en `feature/backend` | `docs/*`, ADRs, OpenAPI |

## Lo que el Gantt no pedía y el backend ya tiene

Capacidades pedagógicas alineadas con la visión tutor (más allá del Excel):

- Perfil cognitivo `student_profiles` (mastery por documento/concepto + curva del olvido)
- `PedagogicalEngine` / `TutorPolicy` (IA solo genera lenguaje)
- Eventos de evidencia + outbox Mongo
- Redis rate limit, métricas, learning APIs (`/learning/me`)

## Brechas accionables (prioridad)

| Prioridad | Brecha | Recomendación |
|-----------|--------|----------------|
| Alta (si el Gantt sigue vigente) | RAG | Decidir: (A) renombrar el entregable a “contexto documental / grounding”, o (B) añadir embeddings + retrieval |
| Alta (si el Gantt sigue vigente) | Web scraping | Confirmar si sigue siendo requisito; hoy el flujo es upload de texto por API |
| Media | Integración Mongo real en CI | Tests con Mongo de Compose o Testcontainers |
| Media | Pentest / checklist OWASP | Documentar checklist ejecutado + hallazgos |
| Baja | Deploy Render | Añadir `render.yaml` o runbook de despliegue |

## Veredicto

**Backend listo como tutor API + Mongo** respecto a auth, documentos, OpenAI, quizzes, conversaciones y perfil de aprendizaje.  
**No 100% del Gantt literal** por RAG vectorial, scraping y cierre formal de QA/deploy cloud.

Si el Excel es contrato académico, documenta el desvío RAG/scraping como cambio de alcance hacia tutor adaptativo grounded en material del estudiante.
