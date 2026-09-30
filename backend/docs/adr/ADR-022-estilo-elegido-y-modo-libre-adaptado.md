# ADR-022: El estudiante elige cómo le explican, y el modo libre también se adapta

- **Estado:** Aceptado
- **Fecha:** 2026-09-29
- **Rama de origen:** `feature/backend`
- **Decisores:** Equipo LARIA (orquestación backend)
- **Complementa:** [ADR-017](ADR-017-nivelacion-por-rondas.md)

## Contexto

Dos huecos entre el producto que se promete y lo que había.

1. **El estilo de explicación nunca se preguntaba.** `CognitiveStyleSelector` lo
   deducía de palabras del mensaje, de señales o de lo que le había funcionado.
   Además, las palabras eran temas: "ecuación" forzaba el estilo matemático
   aunque el estudiante aprendiera mejor con analogías. El flujo esperado es
   nivelarse y que después el tutor pregunte cómo prefiere aprender.
2. **Sin material no había adaptación.** El chat libre no pasa por el motor
   pedagógico. El nivel que dejaba la nivelación solo lo leía el generador de
   quizzes: el estudiante se nivelaba en "ecuaciones" y el chat le volvía a
   ofrecer nivelarse o le explicaba desde cero.

## Decisión

### 1. Preferencia declarada: `PUT /learning/me/preferences`

- `{"explanation_style": "analogy"}` con los seis valores de `CognitiveStyle`
  (simple, step_by_step, analogy, visual, mathematical, technical), o `null` para
  "que lo decida LARIA".
- **Vale para todo, no por tema.** Es cómo aprende la persona, y por tema habría
  muy pocos datos para que cambiara algo.
- **Prioridad:** un pedido explícito en el mensaje ("explícamelo paso a paso")
  gana en ese turno. Después va la elección. Lo deducido (palabras sueltas,
  señales, memoria) solo decide si no hay ninguna de las dos.
- Los pedidos explícitos se reconocen con patrones estrictos
  (`style_requested_in`): "ecuación" o "esquema de Ponzi" no son un pedido de
  forma.
- Se guarda por evento (`ExplanationStyleChosenEvent`) y la escribe el projector.
  Una preferencia no es evidencia, pero el perfil sigue teniendo un único
  escritor (invariante 1). El evento viaja por el outbox.
- En el perfil queda como `explanation_style_choice`, separado de
  `pedagogical_memory.preferred_explanation_style`, que es lo deducido.

### 2. Modo libre adaptado, en versión ligera

El tutor sin material recibe un `LearnerContext`:

- **Nivel del tema que pide aprender**, buscado por el tema canónico (el mismo con
  que se guardó). Si existe, no se le ofrece otra nivelación: el tutor empieza la
  clase desde ese nivel, elige él el primer punto y cierra con una pregunta de
  comprobación. El envelope deja de traer `suggest_placement` y trae
  `placement_level`.
- **Si no pide un tema concreto**, los últimos 5 niveles guardados, para ajustar
  la profundidad si la pregunta cae en uno de ellos.
- **Estilo:** el pedido en el mensaje o el elegido.

Es ligero a propósito: sin material no hay mastery por concepto del documento que
dispare andamiaje, socrático o `SEQUENCE`. El motor completo sigue exigiendo
material.

### 3. Arreglo colateral: el outbox con `document_id` nulo

`QuizAttemptCompletedEvent` serializaba `document_id=None` como `"None"`, y al
leerlo `UUID("None")` fallaba fuera del `try` del worker. Toda nivelación o
práctica se habría perdido con `EVENT_BUS_BACKEND=outbox`. Producción usa hoy el
bus en memoria, así que no llegó a morder. Se lee también el `"None"` que ya
pudiera haber guardado la versión anterior.

## Consecuencias

- Verificado contra el modelo real:
  - con nivel **intermedio** en ecuaciones empieza por un error frecuente al
    trasponer términos, no por la definición;
  - con **avanzado** empieza por un tema avanzado;
  - con estilo **analogy** explica la inflación con una analogía;
  - **sin nivel** sigue ofreciendo la nivelación.
- Antes de ajustar el prompt, el modelo saludaba, definía lo elemental o
  preguntaba por dónde empezar. Por eso la instrucción dice "elige tú el primer
  punto".
- Con el estilo elegido, "ecuación" en el mensaje ya no cambia la forma de
  explicar. Sin elección, todo sigue como antes.

## Fuera de alcance

- **Escuchar (voz del tutor).** Es la fase de texto a voz; no es un estilo de
  explicación.
- **Dialogar como modalidad elegible.** Hoy el socrático lo decide el motor con
  evidencia (≥ 0.7 de mastery). Convertirlo en preferencia chocaría con el
  andamiaje cuando el concepto cuesta.
