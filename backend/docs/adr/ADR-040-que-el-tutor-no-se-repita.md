# ADR-040: Que el tutor no se repita

- **Estado:** Aceptado · **Fecha:** 2026-10-05

## Contexto
- En producción había 14 pares de respuestas del tutor casi iguales (> 60 %) a menos de
  3 turnos, entre 109 respuestas de 40 chats. No había mensajes duplicados en la base
  de datos ni en la pantalla: era el contenido.
- La mayoría eran de antes de la memoria del chat (ADR-021). Por ejemplo, "dame más
  ejemplos" recibía "¿sobre qué tema?" dos veces seguidas.
- Con un banco de conversaciones con el tutor actual (los mismos patrones, el modelo
  real), quedaban tres problemas:
  - "Más ejemplos" daba el mismo molde con otras cifras.
  - Ante los insultos, la misma plantilla.
  - Al contestar un ejercicio, decía "¡Muy bien!… sin embargo hay un error" o lo
    resolvía otra vez desde cero.

## Decisión
- `domain/services/repetition.py` es puro: reconoce qué hace el estudiante respecto a
  lo anterior.
  - Los casos son `more_examples`, `not_understood`, `repeated` (pregunta casi igual
    o contenida en una anterior) y `answer` (un número, una expresión breve o una
    opción, tras un ejercicio del tutor).
  - "sí" u "ok" no cuentan como respuesta.
- Con conversación previa, el prompt incluye la apertura de la respuesta anterior
  ("no empieces igual") y la instrucción del caso. En el caso `answer`: decir primero
  si es correcto, no decir "¡Muy bien!" si está mal y no resolverlo entero si acertó.
  Así funciona igual con y sin streaming.
- **Control:** si la respuesta sale ≥ 0.8 parecida a una de las 3 últimas del tutor:
  - Sin streaming, se regenera **una vez**, diciendo qué no repetir
    (`LearnerContext.avoid_reply`).
  - Con streaming ya se mostró, así que solo se registra (`respuesta_repetida` en el log).

## Verificado
Banco con el modelo real, parecido máximo entre las respuestas de una conversación:

| Escenario | Antes | Después |
|---|---|---|
| Frustración | 0.40 | 0.12 |
| Más ejemplos | 0.52 (mismo molde) | 0.50–0.52 (otra situación; solo coincide el formato de lista) |
| Respuesta a un ejercicio | "¡Muy bien!… hay un error" | "El resultado que obtuviste es incorrecto…" |

La re-pregunta (0.12) y el "no entiendo" (0.09) ya estaban bien.

Tests: `tests/unit/domain/test_repeticion.py`.

## Consecuencias
- En streaming no hay segundo intento: la prevención es el prompt. Si el log muestra
  muchas `respuesta_repetida streaming=si`, la opción es retener el primer párrafo
  hasta compararlo.
- El modo con documento recibe la misma instrucción en el prompt, pero no regenera.
