# ADR-025: "Continuar con Google" para tener correos verificados

- **Estado:** Aceptado
- **Fecha:** 2026-09-30
- **Rama de origen:** `feature/backend`
- **Decisores:** Equipo LARIA (orquestación backend)
- **Descarta, por ahora:** Clerk y verificación por código de correo

## Contexto

Cualquiera podía registrarse con un correo que no era suyo: el registro no
verificaba nada. Se evaluaron tres caminos:

- **Google:** Google garantiza el correo.
- **Código por correo:** exige enviar correo, y eso exige dominio propio, que no
  hay.
- **Clerk:** resuelve todo, pero reescribe la sesión en los dos lados.

En esta etapa, Google resuelve lo que se pide en un día sin tocar el login
actual.

## Decisión

- **`POST /auth/google {id_token}`.** Recibe el `credential` del botón de Google
  Identity Services y lo verifica con las claves públicas de Google (JWKS, en
  caché): firma RS256, emisor `accounts.google.com`, audiencia igual a NUESTRO
  `GOOGLE_CLIENT_ID`, caducidad y `email_verified`. Devuelve el mismo JWT que
  `/auth/token`. Sin la librería oficial: bastan PyJWT y `cryptography`.
- **El correo es la identidad.** Si no hay cuenta, se crea: correo verificado y
  sin contraseña; el nombre visible sale del nombre de Google. Si ya hay una
  cuenta con ese correo, se vincula.
- **Secuestro por pre-registro.** Si la cuenta que se vincula nunca había
  verificado su correo, su contraseña se anula. Si no, quien registró primero el
  correo de otra persona con una contraseña suya compartiría la cuenta con la
  dueña real.
- **Borrar una cuenta de Google.** Como no tiene contraseña, se confirma con un
  `google_id_token` recién emitido para el mismo correo. Otra cuenta de Google →
  403.
- **`GET /auth/providers`** devuelve el client id público, para que el frontend
  no lo duplique. `/users/me` expone `email_verified` y `has_password`.

## Consecuencias

- Hay que crear el client id en Google Cloud Console, con los orígenes de
  JavaScript del frontend, y ponerlo en Render como `GOOGLE_CLIENT_ID`. Sin él,
  todo sigue igual y el endpoint responde 401 "no está configurado".
- Las vistas previas de Vercel no pueden usar el botón: Google no admite
  comodines en los orígenes autorizados.
- La política de privacidad lista a Google como proveedor de identidad.

## Pendiente

- **Registro con contraseña.** Sigue sin verificar el correo. Verificarlo
  (código por correo) exige dominio propio.
- **Recuperar la contraseña.** Igual: necesita enviar correo.
