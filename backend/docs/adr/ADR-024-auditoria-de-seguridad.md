# ADR-024: Auditoría de seguridad del backend (2026-09-30)

- **Estado:** Aceptado
- **Fecha:** 2026-09-30
- **Rama de origen:** `feature/backend`
- **Decisores:** Equipo LARIA (orquestación backend)

## Contexto

El producto funciona; la seguridad del usuario no se había revisado entera. Se
auditó el código y se sondeó producción (Render) sin credenciales ajenas:
autenticación, autorización por recurso, límites, subidas, cabeceras, CORS,
secretos y superficie expuesta.

## Lo que estaba bien

- **Autorización por recurso.** Documentos, chats, quizzes, intentos y rutas
  comprueban el dueño; a otro usuario se le responde 404, sin confirmar que
  existe.
- **Contraseñas** con bcrypt. El login no distingue "no existe" de "contraseña
  mala" y compara contra un hash señuelo para igualar tiempos.
- **Secretos.** `SECRET_KEY` se valida al arrancar (≥ 32 caracteres, no
  conocida). `.env` no está versionado. `correct_answer` nunca sale en un quiz
  público.
- **CORS** rechaza orígenes ajenos. La regex de previews va anclada (ADR-019).
- **Borrado de cuenta** real, con contraseña (ADR-019).

## Hallazgos corregidos

| # | Gravedad | Hallazgo | Arreglo |
|---|---|---|---|
| 1 | Alta | **Límites globales por IP compartida.** En Render la app ve la IP del balanceador, así que cada límite era de toda la plataforma: 10 logins/min, 8 preguntas/min, 5 registros/min. Un atacante bloqueaba a todos y una clase no podía registrarse a la vez | Con sesión, la clave es el **usuario** (token verificado). El login se limita **por cuenta** (10 intentos cada 15 min). Las rutas sin sesión quedan con topes holgados por IP (frenan volumen) |
| 2 | Alta | **Mensajes del chat sin límite.** Cada uno es una llamada a OpenAI: un solo usuario podía generar gasto ilimitado | `ia:chat`, 20/min por usuario (`/messages` y `/stream`) |
| 3 | Alta | **Bombas de descompresión.** Un .docx/.xlsx/.pptx es un zip que se abría sin mirar su tamaño; 1 MB podía expandirse a gigas y tumbar la instancia (512 MB) | Se lee el índice del zip antes de abrirlo: ≤ 200 MB descomprimidos y ≤ 5000 entradas. PDF ≤ 2000 páginas. Texto extraído ≤ 5 M caracteres |
| 4 | Media | **Parseo en el event loop.** Un PDF grande congelaba todas las peticiones mientras se procesaba | `asyncio.to_thread` |
| 5 | Media | **Sin cabeceras de seguridad** | `nosniff`, `X-Frame-Options: DENY`, HSTS, `Referrer-Policy`, `Permissions-Policy`, COOP. Middleware ASGI puro, no bufferiza el SSE |
| 6 | Media | **`/metrics` público** (volumen de uso, latencias, fallos) | Exige `Authorization: Bearer <METRICS_TOKEN>` (generado en Render) |
| 7 | Baja | **Swagger público en producción** | `ENABLE_DOCS=false` en `render.yaml` |
| 8 | Baja | **Fallos de OpenAI sin causa registrada** | Log con status y código del proveedor, nunca la clave (commit 388b10f) |

## Pendiente, con su razón

| Hallazgo | Por qué no se arregló aquí |
|---|---|
| **`APP_ENV=development` en Render.** Apaga las comprobaciones de producción del arranque | Pasar a `production` exige el bus outbox (durabilidad de eventos). Es un cambio de infraestructura con su propia prueba; el bug de `document_id` nulo que lo impedía ya se arregló (ADR-022) |
| **Token de 60 min en `localStorage` sin revocación.** Un XSS en el frontend lo robaría; cerrar sesión no lo invalida | Cookies httpOnly o tokens de refresco con revocación es un rediseño de sesión en los dos lados. Mitigado: vida corta y cabeceras |
| **No hay "olvidé mi contraseña"** | Necesita enviar correo, y eso necesita dominio propio. "Continuar con Google" lo evita para quien entre con Google |
| **El registro revela si un correo existe (409)** | Es la práctica común y el login no lo revela. Con Google se diluye |
| **IP real del cliente en rutas sin sesión** (`TRUSTED_PROXIES`) | No se pudo observar qué cabeceras pone el proxy de Render. Con los límites por cuenta y por usuario ya no hace falta para la seguridad |
| **Menores de edad** | Es una decisión legal: edad mínima y consentimiento (placeholders de ADR-019) |
