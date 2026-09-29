# ADR-020: Pedir un cuestionario abre uno de verdad; el tutor no lo escribe

- **Estado:** Aceptado
- **Fecha:** 2026-09-28
- **Rama de origen:** `feature/backend`
- **Decisores:** Equipo LARIA (orquestación backend)
- **Complementa:** [ADR-016](ADR-016-diagnostico-de-entrada.md), [ADR-017](ADR-017-nivelacion-por-rondas.md)

## Contexto

Contra producción, "Ponme un quiz de fracciones" en un chat sin material devolvía
el quiz **escrito como texto** en la respuesta ("1. ¿Cuál es la fracción
equivalente a 1/2? a) 2/4…"). Ese quiz no se corrige en el servidor, no deja
evidencia en el perfil y el estudiante lo responde en texto libre: es lo contrario
de lo que el sistema promete.

Había además dos huecos:

- El único quiz sin documento era `/quizzes/diagnostic`, que **cambia el nivel
  guardado**. Practicar no es nivelarse: alguien que ya es intermedio y quiere
  repasar no debería ver su nivel reescrito por un quiz de práctica.
- El detector de `quiz` saltaba con palabras sueltas ("ponme", "prueba", "test").
  "Ponme un ejemplo" era un pedido de quiz. Con un quiz interactivo como reacción,
  pedir un ejemplo habría abierto un cuestionario.

## Decisión

### 1. La intención se estrecha y trae una señal explícita

`quiz` solo salta con un verbo de pedido y un objeto de evaluación ("hazme un
examen", "dame ejercicios", "quiero practicar", "evalúame"). Cuando salta, el
payload trae **`offer_quiz: true`** y, si se nombró, `topic_hint` con el tema tal
como lo escribió el estudiante. Si no se nombró ("ponme un quiz"), no hay
`topic_hint`.

Como con `suggest_placement` (ADR-017), el cliente usa la **señal** y no
`intent`, que es un diagnóstico interno.

### 2. El tutor anuncia; no escribe preguntas

Con un pedido de cuestionario el prompt prohíbe escribir preguntas, opciones o
ejercicios, en los dos caminos:

- **Con material:** confirma que lo prepara a partir de su material (el cliente
  llama a `/chats/{id}/quiz`).
- **Sin material, con tema:** confirma que prepara uno sobre ese tema.
- **Sin tema:** pregunta sobre qué tema.

El texto y el botón del cliente dicen lo mismo.

### 3. `POST /quizzes/practice`: practicar sin tocar el nivel

`{topic, num_questions}` (1–20, 5 por defecto). Se genera como el diagnóstico
(mismo grafo, mismo generador) pero con `round: null`:

- **No escribe nivel:** el intento trae `placement: null` y `level_by_topic` no
  cambia. El veredicto solo sale de `/diagnostic`.
- **Sí deja evidencia** por concepto: las respuestas calificadas son medición
  (invariante 4).
- **La dificultad sigue al nivel guardado.** Sin nivel o `basico`: 60 % fácil,
  40 % medio. `intermedio`: 20/60/20. `avanzado`: 40 % medio, 60 % difícil. El
  reparto usa el método del mayor resto, así que siempre suma lo pedido.

## Consecuencias

- `type: "quiz"` del envelope **sigue sin emitirse**. El quiz vive en su propio
  endpoint; el chat solo lo anuncia.
- Frases verificadas contra el modelo real (5/5 anuncian, 0/5 escriben el quiz):
  "Ponme un quiz de fracciones", "hazme un examen de la revolución francesa",
  "quiero practicar ecuaciones de primer grado", "ponme un quiz" (pregunta el
  tema), "dame ejercicios de derivadas".
- Una frase que pida un quiz sin verbo de pedido ("¿me evalúas?") cae en
  `general`, y el tutor responde en texto normal. Es preferible a abrir quizzes que
  nadie pidió.
