# ADR-041: Borrar cuentas de Clerk sin que se recreen

- **Estado:** Aceptado · **Fecha:** 2026-10-06 · **Amplía:** ADR-019 (borrar la cuenta), ADR-027 (Clerk)

## Contexto
- **Las cuentas de Clerk no se podían borrar.** `DELETE /users/me` pedía contraseña o un
  token de Google, y una cuenta de Clerk no tiene ninguna de las dos. Son 13 de 41
  usuarios. La política de privacidad promete el borrado, y hay menores entre los usuarios.
- **Aunque se hubiera podido, la cuenta se recreaba.** La sesión de Clerk seguía viva
  en el navegador. La siguiente petición (el tiempo de estudio llega cada minuto) no
  encontraba al usuario y `resolve_clerk_user` creaba uno nuevo, vacío.
- **Duplicados posibles al entrar:**
  - El correo no se normalizaba. En producción había una cuenta guardada con
    mayúsculas, y Clerk envía el correo en minúsculas: al entrar con Clerk, esa persona
    habría recibido una segunda cuenta vacía.
  - El índice único de `clerk_user_id` estaba declarado en el repositorio, pero el
    arranque no lo creaba. Además, cada petición de Clerk recorría toda la colección.

## Decisión
- **Confirmar la identidad en cuentas de Clerk:**
  - El cuerpo va vacío. Basta una verificación de identidad en Clerk de hace
    **≤ 10 minutos**, que se lee del claim `fva[0]` del token de sesión.
  - Si no la hay, responde **403** con `reason: "reverification_required"`. El cliente
    pide la reverificación de Clerk (`useReverification`) y reintenta.
  - Un token de sesión robado no basta.
- **Orden del borrado de una cuenta vinculada a Clerk:**
  1. Se desactiva la cuenta: las peticiones en curso reciben 401.
  2. Se borra el usuario en Clerk. Así se cierran sus sesiones y su token ya no puede
     crear otra cuenta (Clerk responde 404 al vincular).
  3. Se borran los datos y la cuenta.
- **Si falla Clerk en el paso 2**, la cuenta se reactiva y responde **503**: no se borró
  nada y se puede reintentar.
- **Si falla el borrado de los datos después de cerrar Clerk**, se registra
  `cuenta_borrado_incompleto user=<id>` para terminarlo a mano. Repetir es seguro.
- **También se borra en Clerk** la cuenta que confirma con contraseña, si está vinculada.
- **Correo normalizado** (`Email` en minúsculas y sin espacios). `find_by_email` encuentra
  también las cuentas antiguas guardadas con mayúsculas.
- **El índice parcial único de `clerk_user_id` se crea al arrancar.** Se comprobó que en
  producción no hay duplicados que lo impidan: 0 correos repetidos y 0 `clerk_user_id` repetidos.

## Impacto de borrar una cuenta (revisado)
- **Se borra:**
  - documentos y sus originales en R2;
  - cuestionarios, intentos, interacciones y sesiones;
  - chats y rutas;
  - perfil, tiempo de estudio y eventos pendientes del outbox;
  - el usuario, y ahora también el usuario en Clerk.
- **Queda, sin datos personales:** el temario investigado (`curriculum_research`), que es
  global, y los logs, que solo llevan identificadores.
- **Queda, y caduca solo:**
  - la caché de respuestas del tutor en Redis (clave = hash del prompt, que incluye
    la conversación; TTL 1 h);
  - la caché del moderador, en memoria del proceso (512 textos, sin usuario asociado).
- **Ventana residual:** un evento que el projector ya estuviera procesando al borrar
  puede recrear un perfil huérfano. Hoy hay 0 en producción.

## Verificado
- `tests/api/test_borrar_cuenta_clerk.py`:
  - se borra y no se recrea;
  - sin verificación reciente pide reverificar;
  - si Clerk falla, no se borra nada;
  - el correo con otra mayúscula es la misma cuenta;
  - las cuentas antiguas con mayúsculas se encuentran en Mongo.

## Pendiente de comprobar en producción
- Que los tokens de sesión de la instancia de Clerk traigan `fva`. Sin ese claim, todas
  las cuentas de Clerk recibirían `reverification_required` y no podrían borrarse. Lo
  comprueba el frontend decodificando un token real.
