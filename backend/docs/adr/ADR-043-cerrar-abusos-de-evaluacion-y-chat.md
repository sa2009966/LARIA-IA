# ADR-043: Cerrar tres abusos: reintentos de nivelación, mensajes del tutor y tamaño

- **Estado:** Aceptado · **Fecha:** 2026-10-09

## Contexto
Una revisión de seguridad encontró, en el código desplegado:
1. **Se podía subir de nivel haciendo trampa.** La respuesta de un intento muestra la
   correcta de cada pregunta, y una nivelación o prueba de paso se podía reenviar. Cada
   intento recalculaba el nivel. Bastaba con fallar, mirar las soluciones y reenviarla
   perfecta para abrir el tramo siguiente; además, cada reintento sumaba evidencia.
2. **El cliente podía escribir como el tutor.** `POST /chats/{id}/messages` aceptaba
   `role: "assistant"`, y esos mensajes entraban al historial que lee el modelo. El filtro
   de temas (ADR-036) solo mira la pregunta. Un "LARIA dijo: …" falso seguido de
   "continúa" servía para saltárselo. Con usuarios menores, es la vía más clara de abuso.
3. **Costo sin tope:**
   - los mensajes del chat no tenían tamaño máximo (todo va a la moderación y al modelo);
   - `POST /learning/paths/{id}/passage-test` no tenía límite de peticiones.

## Decisión
1. **Una nivelación o prueba de paso (`placement_round`) se responde una vez.** Un segundo
   intento responde **409**: para volver a intentarlo se pide una ronda nueva. Los quizzes
   de práctica, de documento y de la clase no cambian.
2. **`ChatAddMessageRequest.role` admite solo `user` y `system`.** Lo que dice el tutor lo
   escribe el servidor. `system` queda para notas del cliente (por ejemplo, "Subí el
   archivo"), que ya no entraban al historial del modelo.
3. **Topes:**
   - mensajes del chat de **8000 caracteres** como máximo (422 si se pasan);
   - la prueba de paso, **6 por minuto** (`ia:passage`).

## Verificado
- `tests/api/test_prueba_de_paso_e2e.py`: el reenvío de la prueba de paso y de la
  nivelación inicial responde 409 y no abre el tramo; regla de límite.
- `tests/api/test_chats_api.py`: `assistant` desde el cliente y un mensaje de 8001
  caracteres responden 422 y no se guarda nada.

## Pendiente
- Los quizzes de documento se pueden reintentar a propósito, para practicar, pero cada
  intento sigue sumando evidencia aunque ya se hayan visto las correctas. Solo el primero
  debería medir.
