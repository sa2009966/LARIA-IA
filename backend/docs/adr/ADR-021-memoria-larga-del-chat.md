# ADR-021: Memoria larga del chat: ventana de 20 mensajes y resumen de lo anterior

- **Estado:** Aceptado
- **Fecha:** 2026-09-29
- **Rama de origen:** `feature/backend`
- **Decisores:** Equipo LARIA (orquestación backend)
- **Amplía:** [ADR-018](ADR-018-memoria-de-la-conversacion.md)

## Contexto

ADR-018 le dio memoria al tutor: los últimos 8 mensajes (cuatro intercambios),
4000 caracteres en total y 700 por mensaje. Lo más antiguo se descartaba sin
resumir, y el propio ADR dejaba el resumen como siguiente paso.

En uso real no alcanzó: "no recuerda lo que se habló 10 mensajes antes". Es cierto
y era el diseño: lo dicho en el mensaje 1 salía del contexto a partir del mensaje
9, y con respuestas largas del tutor aún antes. El requisito es recordar al menos
10–20 mensajes.

## Decisión

### 1. Ventana de 20 mensajes

Veinte mensajes de diálogo (diez intercambios), 12 000 caracteres en total y 1500
por mensaje. Los `system` siguen sin contar.

### 2. Lo que sale de la ventana se resume, por lotes

- Cuando hay 6 mensajes fuera de la ventana sin resumir (`SUMMARY_BATCH`), el
  modelo reescribe el resumen del chat incorporando el anterior. Es una llamada
  extra cada tres intercambios, no una por turno.
- Hasta que se completa el lote, esos mensajes siguen en la conversación reciente
  (hasta 25), así que entre el resumen y lo reciente **no queda hueco**.
- El resumen guarda lo que el tutor necesita recordar: nombre y lo que el
  estudiante dijo de sí mismo, temas y a qué se refería, objetivo, qué le costó y
  qué le funcionó, preferencias y acuerdos. No guarda el contenido de la clase.
  Máximo 150 palabras (1500 caracteres).
- Se guarda en el chat (`summary`, `summary_upto`) y entra en el prompt antes de
  la conversación reciente, marcado como resumen y no como diálogo.
- Si el modelo falla, el turno sigue: lo pendiente queda en lo reciente y se
  reintenta en el siguiente mensaje. Un resumen vacío no avanza la cobertura; si
  la avanzara, esos mensajes se perderían.

### 3. Se calcula en el turno, antes de responder

El resumen se actualiza en la misma petición que guarda el chat. Así no hay dos
escritores sobre el mismo documento. En modo streaming se hace antes de abrir el
stream.

## Consecuencias

- Verificado contra el modelo real: el dato del mensaje 1 ("me llamo Tomás y
  estudio para un examen de química orgánica el viernes") se recuerda a 2, 10, 20
  y 30 mensajes. A 30 ya sale del resumen.
- Coste: el prompt de cada turno crece (hasta ~3000 tokens de historial), más una
  llamada de resumen cada 6 mensajes en chats largos.
- Privacidad: el resumen es un dato nuevo, se genera con OpenAI y la política lo
  dice. Se borra con el chat y con la cuenta.

## Fuera de alcance

- **Memoria entre chats.** Lo que cruza chats es el perfil: mastery, nivel por
  tema y estilo elegido ([ADR-022](ADR-022-estilo-elegido-y-modo-libre-adaptado.md)).
  Recordar hechos personales entre chats es otra decisión, y también otra
  conversación de privacidad.
