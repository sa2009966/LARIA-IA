# Endpoints REST — LARIA Backend

Base URL: `/api/v1`  
Auth: cabecera `Authorization: Bearer <access_token>` salvo donde se indique.

Swagger: `GET /docs` (si `ENABLE_DOCS=true`)  
OpenAPI: `GET /openapi.json`  
Health: `GET /health` (sin prefijo `/api/v1`)
Ready: `GET /ready` (Mongo/Redis según config; 503 si dependencia caída)
Metrics: `GET /metrics` (Prometheus text si `METRICS_ENABLED=true`; **404** si `false`)
Raíz: `GET /` → redirect a `/docs` o JSON de servicio si docs off.

---

## Autenticación — `/auth`

| Método | Ruta | Auth | Descripción |
|--------|------|------|-------------|
| `POST` | `/api/v1/auth/register` | No | Alta de usuario (`student`). Password ≥12, mayúsculas, minúsculas y dígito. |
| `POST` | `/api/v1/auth/token` | No | OAuth2 password: campo `username` = **email**. Devuelve JWT. |

**Códigos frecuentes:** `201` register, `200` token, `409` conflicto genérico, `401` credenciales, `422` validación, `429` rate limit.

---

## Usuarios — `/users`

| Método | Ruta | Auth | Roles | Descripción |
|--------|------|------|-------|-------------|
| `GET` | `/api/v1/users/me` | JWT | cualquiera activo | Perfil del token |
| `GET` | `/api/v1/users/` | JWT | `admin` | Listar usuarios |
| `DELETE` | `/api/v1/users/{user_id}` | JWT | `admin` | Desactivar usuario (`204`) |

---

## Documentos — `/documents`

Todos requieren JWT. Solo el **propietario** opera sobre el recurso. Ajeno/inexistente → **`404`** genérico.

| Método | Ruta | Descripción |
|--------|------|-------------|
| `POST` | `/api/v1/documents/` | Subir material (JSON: `filename`, `content`, `subject`; cuerpo → blob/GridFS) |
| `POST` | `/api/v1/documents/upload` | Subir archivo multipart (`file`, `subject`, `filename` opcional; hasta 25 MiB). Formatos: texto (`.txt`, `.md`, `.csv`, `.json`, `.log`), código, PDF, `.docx`, `.xlsx`, `.pptx`. Formato no soportado → **422** |
| `GET` | `/api/v1/documents/` | Listar mis documentos |
| `GET` | `/api/v1/documents/{document_id}` | Obtener uno propio |
| `GET` | `/api/v1/documents/{document_id}/content` | **El archivo original**, con su `Content-Type`, para previsualizar o descargar. Solo el dueño; ajeno o inexistente → `404` (no `403`, para no confirmar que existe). Sin original guardado → su texto extraído como `text/plain`. `.html`/`.xml` se sirven como `text/plain` (servirlos inline desde la API sería XSS). Requiere `Authorization: Bearer`: usar `fetch` + `URL.createObjectURL`, porque `<img src>`/`<iframe src>` no mandan la cabecera |
| `DELETE` | `/api/v1/documents/{document_id}` | Eliminar (`204`) |
| `POST` | `/api/v1/documents/{document_id}/analyze` | Análisis IA (cachea resultado; `force_refresh=true` opcional) |
| `POST` | `/api/v1/documents/{document_id}/ask` | Pregunta tutor sobre el documento (registra evidencia) |
| `POST` | `/api/v1/documents/{document_id}/quiz` | Generar quiz (`num_questions` 1–20). **Sin** `correct_answer` en la respuesta |

**IA fallida:** `502` con mensaje seguro (`IAAnalysisError`).

**Almacenamiento / contratos (auditoría GridFS):**
- El cuerpo del material **no** viaja en listados ni se embebe en BSON si hay `content_blob_id` (GridFS `fs.files` / `fs.chunks`).
- JSON (`POST /documents/`) sigue válido para textos ≤ 100 000 caracteres; archivos grandes deben usar `POST /documents/upload`.
- Respuesta de upload/list/get: solo metadatos (sin `content`). Analyze/ask/quiz hidratan desde el blob en servidor.
- La extracción de texto vive en `application/file_parser.py` (PDF, DOCX, XLSX, PPTX, texto y código); el dominio solo ve el texto resultante. Se guardan **dos cosas**: el texto extraído (lo que lee el motor) y el archivo original con su
  tipo real, para previsualizarlo o descargarlo ([ADR-012](adr/ADR-012-texto-y-original.md)).
  Límite configurable: `DOCUMENT_MAX_UPLOAD_BYTES` (25 MiB). Sobre límite → `413`.
- Domínio limpio: routers solo validan HTTP; tamaño y blob viven en application/infrastructure.

---

## Chats — `/chats`

Todos requieren JWT y son del **propietario**; ajeno/inexistente → `404`. Un chat puede vincularse a
un documento (`document_id`): con documento entra el motor pedagógico completo; sin documento el
turno es conversación libre y no sustituye al tutor grounded.

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/api/v1/chats/` | Listar mis chats |
| `POST` | `/api/v1/chats/` | Crear chat (`title`, `document_id` opcional) |
| `POST` | `/api/v1/chats/generate-title` | Generar un título breve desde 1–5 mensajes; no modifica ningún chat. De 1 a 7 palabras: más largo se recorta, y solo una respuesta vacía del proveedor da error |
| `GET` | `/api/v1/chats/{chat_id}` | Chat con sus mensajes |
| `PUT` | `/api/v1/chats/{chat_id}` | Renombrar o vincular documento |
| `POST` | `/api/v1/chats/{chat_id}/messages` | Añadir mensaje. Si `role="user"`, **el tutor responde en la misma llamada**, el turno cuenta como evidencia y su mensaje queda persistido con el envelope en `metadata`. Para una nota que no debe disparar turno, usa `role="system"` |
| `POST` | `/api/v1/chats/{chat_id}/stream` | Igual, en SSE: `thinking` → `token`(s) → `envelope` → `done` |
| `POST` | `/api/v1/chats/{chat_id}/quiz` | Cuestionario sobre el **material vinculado al chat** (`num_questions` 1–20). Sin material → `422`. No incluye `correct_answer`: el intento se envía a `POST /quizzes/{id}/attempts` y se califica en servidor |
| `DELETE` | `/api/v1/chats/{chat_id}` | Eliminar (`204`) |

**Envelope del tutor** (`metadata` del mensaje `assistant`, y evento `envelope` en SSE):

| Campo | Valores |
|-------|---------|
| `type` | `answer`, `explanation`, `hint`, `quiz`, `celebration`, `error` |
| `emotion` | `calm`, `encouraging`, `patient`, `celebratory` |
| `payload` | `content`, `grounded`, `mode`, `difficulty`, `cognitive_style`, `focus_concepts`, `session_step`, `intent`, `practice_before_advance`, `chunk_explanation`, y `celebrated_concept` cuando hay hito ([ADR-009](adr/ADR-009-contabilidad-y-canal-positivo.md)). `grounded=false` = chat sin material: conversación, no tutoría adaptativa |

El envelope es determinista: lo decide el dominio, no el modelo.

---

## Cuestionarios — `/quizzes`

| Método | Ruta | Descripción |
|--------|------|-------------|
| `POST` | `/api/v1/quizzes/diagnostic` | **Diagnóstico de entrada sobre un tema, sin material.** Body `{ "topic": "ecuaciones" }`. Devuelve una escalera de 6 ítems **fácil→media→difícil** sobre el tema y sus prerrequisitos, con `document_id: null` y `topic` canónico. Se responde en `/quizzes/{id}/attempts` como cualquier quiz ([ADR-016](adr/ADR-016-diagnostico-de-entrada.md)) |
| `GET` | `/api/v1/quizzes/{quiz_id}` | Quiz propio sin respuestas correctas |
| `POST` | `/api/v1/quizzes/{quiz_id}/attempts` | Enviar intento `{ "answers": { "0": "A", "1": "C" } }`; califica en servidor y revela correctas |

---

## Aprendizaje — `/learning`

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/api/v1/learning/me` | Historial del estudiante: intentos de quiz + interacciones tutor + recomendaciones |
| `GET` | `/api/v1/learning/me/profile` | Perfil cognitivo: mastery efectivo, memoria pedagógica, ritmo, señales de struggle |
| `GET` | `/api/v1/learning/paths` | Rutas de aprendizaje del estudiante. El mastery y el estado de cada módulo se **proyectan** desde el perfil en cada lectura ([ADR-008](adr/ADR-008-progreso-derivado-no-declarado.md)) |
| `POST` | `/api/v1/learning/paths` | Crear una ruta (plan de módulos y prerrequisitos) |
| `GET` | `/api/v1/learning/paths/{path_id}` | Ruta por id, con el progreso proyectado |
| `DELETE` | `/api/v1/learning/paths/{path_id}` | Borrar una ruta |

> No existe endpoint para escribir el mastery de un módulo: el progreso se gana con evidencia
> (quizzes, tutoría), no se declara.

El perfil se actualiza vía projector a partir de `TutorQuestionAskedEvent` y `QuizAttemptCompletedEvent` (bus `memory` o `outbox`).

---

## Subjects válidos (documentos)

Whitelist en dominio (`Subject`), entre otros: Matemática, Ciencias, Física, Química, Biología, Historia, Geografía, Lengua, Literatura, Filosofía, Inglés, Educación Física, Artística (y variantes sin tilde). Subject inválido en upload → **422**.

---

## Errores HTTP habituales

| Código | Significado |
|--------|-------------|
| `401` | Token ausente/inválido/usuario inactivo |
| `403` | Rol insuficiente (p. ej. admin) |
| `404` | Recurso no encontrado **o** no autorizado (ownership) |
| `409` | Conflicto de registro (email/username ya existentes) |
| `413` | Upload supera `DOCUMENT_MAX_UPLOAD_BYTES` |
| `422` | Validación de body/query/path (UUID malformado, subject inválido, contraseña débil) |
| `429` | Rate limit |
| `502` | Fallo del proveedor de IA |
| `503` | `/ready` degradado (Mongo/Redis no alcanzables) |

### Ops

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/health` | Liveness (siempre 200 si el proceso responde) |
| `GET` | `/ready` | Readiness de dependencias |
| `GET` | `/metrics` | Contadores `outbox_*`, `outbox_unsupported`, `profile_updates`, `laria_llm_latency_ms`, etc. **404** si `METRICS_ENABLED=false`. |
