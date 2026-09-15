# LARIA-IA

LARIA es un **tutor inteligente adaptativo**: una API que usa evidencia de aprendizaje (perfil cognitivo, quizzes, interacciones) para decidir *cómo* enseñar, y un modelo de lenguaje solo para *decir* esa decisión. El objetivo no es responder preguntas; es que el estudiante aprenda.

No es un chatbot con historial. Responder bien no se toma como prueba de comprensión.

## Finalidad

El estudiante sube material, pregunta, practica y recibe una estrategia que cambia con lo que demuestra saber — y con lo que olvida. LARIA adapta modo (explicar, socrático, andamiaje, práctica), dificultad, foco conceptual y estilo *antes* de llamar al modelo.

La inteligencia educativa pertenece al dominio de LARIA (`PedagogicalEngine`, `TutorPolicy`, perfil y evidencia). El LLM no elige pedagogía.

## Cómo funciona

```
estudiante → documento / chat / quiz
                ↓
     motor pedagógico (contexto, prerrequisitos, dificultad, memoria)
                ↓
     TutorPolicy (prompts acotados a esa decisión)
                ↓
     LLM (solo genera lenguaje)
                ↓
     evidencia → perfil cognitivo → siguiente decisión
```

Flujo típico hoy:

1. **Documento.** El estudiante autentica (JWT) y sube material de texto (`.txt` / `.md`). El análisis extrae resumen, conceptos y preguntas sugeridas; el resultado queda en el documento. El contexto sale de ese texto, no de un índice vectorial (no hay RAG).
2. **Chat o pregunta.** Puede preguntar sobre un documento (`POST /documents/{id}/ask`) o conversar en un chat, opcionalmente vinculado a un documento. Con material propio, entra el motor pedagógico; sin documento, el turno es más libre y no sustituye al tutor grounded.
3. **Evaluación.** Se genera un cuestionario MCQ (sin revelar las correctas al cliente). El intento se califica en servidor.
4. **Adaptación.** Preguntas y quizzes publican eventos. Un projector actualiza mastery por concepto (con olvido), memoria pedagógica y señales de dificultad. Las siguientes decisiones —y las recomendaciones de `GET /learning/me`— usan ese perfil, no solo el hilo del chat.

El proveedor de lenguaje actual es **OpenAI** (`gpt-4o-mini` por defecto; un modelo más capaz solo cuando la política lo justifica). La arquitectura hexagonal permite otro adaptador detrás del puerto `IAAnalyst` sin reescribir el dominio.

## Qué hay hoy

En este árbol (`backend/`) el producto es la **API FastAPI** del tutor:

| Capacidad | Estado |
|-----------|--------|
| Auth JWT, roles estudiante/admin, ownership (recurso ajeno → 404) | En código |
| Documentos, análisis, pregunta tutor, quizzes y calificación | En código |
| Chats multi-turno (con o sin documento; streaming disponible) | En código |
| Perfil cognitivo, historial y recomendaciones (`/learning/me`, `/learning/me/profile`) | En código |
| Gate de prerrequisitos y catálogo de misconceptions (álgebra, no todas las materias) | En dominio |
| Persistencia MongoDB o memoria; Docker Compose (app + Mongo + Redis) | En código |
| Observabilidad de borde (`/health`, `/ready`, `/metrics`) | En código |

Límites honestos: no extrae PDF; no hay embeddings ni scraping web; no hay LMS, SSO de organización ni plan de estudio HTTP cerrado. El embodiment (voz/presencia) está detrás de puertos y **desactivado** por defecto. Un cliente web existe en la rama `feature/frontend` (Next.js); **no** está en este checkout ni integrado en `develop`/`main`.

Detalle de capas, agregados y contratos: [`backend/docs/architecture.md`](backend/docs/architecture.md) y [`backend/docs/endpoints.md`](backend/docs/endpoints.md).

## Arranque local

Stack: **Python 3.13**, FastAPI, MongoDB (opcional; `DB_PROVIDER=memory` basta para desarrollo y tests), OpenAI.

```bash
cd backend
cp .env.example .env    # completar las variables que pide el ejemplo
pip install -r requirements.txt
uvicorn src.main:app --reload --port 8000
```

API en `http://localhost:8000`. Health: `/health`. Swagger solo si la configuración de docs está habilitada.

Con Docker, desde `backend/`:

```bash
docker compose up --build -d
```

Tests (desde `backend/`, sin Mongo real): `pip install -r requirements-dev.txt` y `python -m pytest tests -q`. Guía completa: [`backend/README.md`](backend/README.md).

## Integraciones futuras (posibles, no comprometidas)

La frontera HTTP y los puertos permiten encajar esto **sin** meter pedagogía en el adaptador. Nada de lo siguiente es roadmap con fecha:

| Dirección | Por qué encaja | Qué no implica |
|-----------|----------------|----------------|
| Cliente web en `develop` | El contrato ya es REST `/api/v1` | Que el Next.js de `feature/frontend` se mergee tal cual |
| Más proveedores LLM | Puerto `IAAnalyst`; hoy solo OpenAI | Multi-vendor el mismo día |
| LMS (Moodle, Canvas, LTI) | El LMS entrega identidad y materiales; LARIA sigue decidiendo la tutoría | Que LARIA se convierta en el campus |
| SSO / organizaciones | Auth y ownership ya están en el borde | Multi-tenant o Clerk/SAML ya diseñados |
| Plan de estudio / learning path | El perfil y el grafo de prerrequisitos son la base; falta producto HTTP estable | Un planner automático fiable |
| Analítica educativa / vista docente | Eventos, perfil y `/metrics` ya existen | Un dashboard de institución |
| Recuperación semántica (RAG) | Hoy el foco es el documento del estudiante | Que el grounding actual sea insuficiente para tutoría sobre *ese* material |
| Repetición espaciada como producto | El olvido ya está en mastery | Un scheduler tipo Anki en la API |

Prioridad de producto: fortalecer el tutor (memoria, adaptación, evidencia), no acumular integraciones.

## Documentación

| Recurso | Contenido |
|---------|-----------|
| [`backend/README.md`](backend/README.md) | Stack, arranque, tests y seguridad del API |
| [`backend/docs/`](backend/docs/) | Arquitectura, endpoints, Mongo, ADRs, despliegue |
| [`CICD.md`](CICD.md) | Flujo de ramas, PRs y verificación (equipo + agentes) |

## Ramas

```
feature/backend   → develop
feature/frontend  → develop
develop           → main
```

`develop` integra; `main` recibe releases. Convención y comandos: [`CICD.md`](CICD.md).
