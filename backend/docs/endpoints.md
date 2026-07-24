# Endpoints REST — LARIA Backend

Base URL: `/api/v1`  
Auth: cabecera `Authorization: Bearer <access_token>` salvo donde se indique.

Swagger: `GET /docs` (si `ENABLE_DOCS=true`)  
OpenAPI: `GET /openapi.json`  
Health: `GET /health` (sin prefijo `/api/v1`)  
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
| `POST` | `/api/v1/documents/` | Subir material (JSON: `filename`, `content`, `subject`) |
| `GET` | `/api/v1/documents/` | Listar mis documentos |
| `GET` | `/api/v1/documents/{document_id}` | Obtener uno propio |
| `DELETE` | `/api/v1/documents/{document_id}` | Eliminar (`204`) |
| `POST` | `/api/v1/documents/{document_id}/analyze` | Análisis IA (cachea resultado; `force_refresh=true` opcional) |
| `POST` | `/api/v1/documents/{document_id}/ask` | Pregunta tutor sobre el documento (registra evidencia) |
| `POST` | `/api/v1/documents/{document_id}/quiz` | Generar quiz (`num_questions` 1–20). **Sin** `correct_answer` en la respuesta |

**IA fallida:** `502` con mensaje seguro (`IAAnalysisError`).

---

## Cuestionarios — `/quizzes`

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/api/v1/quizzes/{quiz_id}` | Quiz propio sin respuestas correctas |
| `POST` | `/api/v1/quizzes/{quiz_id}/attempts` | Enviar intento `{ "answers": { "0": "A", "1": "C" } }`; califica en servidor y revela correctas |

---

## Aprendizaje — `/learning`

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/api/v1/learning/me` | Historial del estudiante: intentos de quiz + interacciones tutor |

Vista embrionaria del progreso; alimentará el perfil cognitivo en iteraciones futuras.

---

## Subjects válidos (documentos)

Whitelist en dominio (`Subject`), entre otros: Matemática, Ciencias, Física, Química, Biología, Historia, Geografía, Lengua, Literatura, Filosofía, Inglés, Educación Física, Artística (y variantes sin tilde).

---

## Errores HTTP habituales

| Código | Significado |
|--------|-------------|
| `401` | Token ausente/inválido/usuario inactivo |
| `403` | Rol insuficiente (p. ej. admin) |
| `404` | Recurso no encontrado **o** no autorizado (ownership) |
| `409` | Conflicto de registro |
| `422` | Validación de body/query |
| `429` | Rate limit |
| `502` | Fallo del proveedor de IA |
