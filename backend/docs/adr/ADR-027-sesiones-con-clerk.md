# ADR-027: Sesiones con Clerk, con transición sin cortes

- **Estado:** Aceptado. Implementado B1 (convivencia y vinculación); B2 a B4, pendientes
- **Fecha:** 2026-09-30
- **Rama de origen:** `feature/backend`
- **Decisores:** Equipo LARIA (orquestación backend) y usuario
- **Sustituye, al terminar:** [ADR-025](ADR-025-entrar-con-google.md) (Google propio: Google Cloud no aceptó la tarjeta)

## Contexto

El registro propio no verificaba correos y no había recuperación de contraseña.
"Continuar con Google" propio quedó bloqueado porque Google Cloud no aceptó la
tarjeta. Clerk resuelve todo esto en su plan gratuito (sin tarjeta, 50 000
usuarios al mes): verificación por código, Google y Microsoft con credenciales
compartidas en desarrollo, protección contra fuerza bruta y bots, y sesiones
cortas que no viven en `localStorage`.

## Decisión

- **Clerk dice QUIÉN es; Plenum es dueño de los DATOS.** Cada usuario de Clerk
  (`user_…`) se vincula a nuestro usuario (`clerk_user_id`). El `id` interno no
  cambia, así que chats, perfil, nivelaciones y documentos no se migran.
- **Verificación del token sin red:**
  - JWKS de la instancia, en caché;
  - RS256 e `iss` igual al de la instancia. El issuer se deriva de la clave
    pública, o se toma de `CLERK_ISSUER`;
  - `exp`/`nbf` con 30 s de margen;
  - `azp` dentro de los orígenes del CORS, lista o regex de previews. Un token
    emitido para otro sitio no vale; si falta `azp`, se acepta, como indica
    Clerk.
- **Vinculación, solo la primera vez.** Se consulta la Backend API de Clerk para
  obtener el correo primario y si está verificado:
  - sin correo verificado → 403;
  - hay cuenta nuestra con ese correo → se vincula; si su correo nunca se había
    verificado, se anula su contraseña, que podría venir de un pre-registro;
  - no hay cuenta → se crea.
  - Dos primeras peticiones a la vez: los índices únicos (correo y
    `clerk_user_id` parcial) hacen fallar a una, que relee la de la otra.
  - Clerk caído al vincular → 503; reintentar es seguro.
- **`AUTH_MODE`:**
  - `own`: lo de antes;
  - `both`: transición; acepta el JWT propio y el de Clerk. El despliegue no
    rompe a nadie;
  - `clerk`: solo Clerk.
- **Rate limit:** con un token de Clerk la clave es `c:<user_…>`. Si se contara
  por IP volvería a ser global (ADR-024).
- **`/users/me`** añade `auth_provider`: `password`, `google` o `clerk`.

## Pendiente (fases siguientes)

- **B2.**
  - Webhook `/webhooks/clerk` con firma Svix: `user.deleted` borra en cascada y
    `user.updated` sincroniza.
  - `DELETE /users/me` exigirá `fva[0]` ≤ 10 min; si no, 403 en el formato de
    reverificación de Clerk, para que el frontend use `useReverification`.
    Después borrará también el usuario en Clerk.
- **B3.** La política de cookies dice que Plenum no usa cookies, pero **Clerk usa
  cookies de sesión**. Hay que actualizar cookies y privacidad (Clerk como
  proveedor) antes de abrirlo al público.
- **B4.** `AUTH_MODE=clerk`: `/auth/register`, `/auth/token` y `/auth/google`
  responden 410. Después se retira el código de ADR-025 y el límite de login por
  correo, que ya lo cubre Clerk.
- **Producción de Clerk.** Exige dominio propio y, para Google, credenciales de
  Google propias. Hasta entonces se usa la instancia de desarrollo, que muestra
  el aviso "Development mode" y tiene tope de usuarios.
