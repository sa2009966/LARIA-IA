# ADR-023: Preguntar y elegir cómo aprender desde el chat

- **Estado:** Aceptado
- **Fecha:** 2026-09-29
- **Rama de origen:** `feature/backend`
- **Decisores:** Equipo LARIA (orquestación backend)
- **Complementa:** [ADR-021](ADR-021-memoria-larga-del-chat.md), [ADR-022](ADR-022-estilo-elegido-y-modo-libre-adaptado.md)

## Contexto

La prueba del flujo completo contra Render (nivelación → estilo → clase → 20
mensajes) sacó tres fallos:

1. **"Pregúntame cómo me gusta aprender" era un pedido de quiz.** El patrón del
   cuestionario incluye "pregúntame", y el tutor contestó "te prepararé un
   cuestionario para que practiques cómo te gusta aprender".
2. **La preferencia dicha en el chat no se guardaba.** "Me siento más cómodo con
   esquemas y dibujos" solo vivía en la memoria del chat. El estilo elegido
   (ADR-022) solo entraba por la tarjeta del cliente.
3. **El tema arrastraba el propósito.** "Quiero aprender electrónica para armar
   un robot seguidor de línea" guardó el nivel bajo esa frase entera, y después
   "quiero aprender electrónica, empecemos" no lo encontraba. El tutor volvía a
   ofrecer la nivelación.

Y uno de memoria. Con respuestas largas del tutor, el tope de 12 000 caracteres
dejaba fuera mensajes que el resumen aún no cubría, porque el resumen solo se
disparaba por número de mensajes. "Lo presento en la feria de ciencias" se
perdió a 12 mensajes de distancia.

## Decisión

### 1. Intención `learning_style`, antes del quiz

- **Pedir que se le pregunte** ("pregúntame cómo me gusta aprender", "¿cuál es mi
  estilo de aprendizaje?") → `ask_learning_style: true` en el payload. El tutor
  pregunta con las mismas 7 opciones numeradas de la tarjeta del cliente, en el
  mismo orden, y no explica nada en ese mensaje.
- **Declarar cómo aprende** ("me siento más cómodo con…", "aprendo mejor…",
  "prefiero que me lo compares…") → se guarda el estilo. Tiene que ser una
  declaración general: "ponme un ejemplo" pide un ejemplo en este turno y no es
  una preferencia para siempre.
- **Responder a las opciones** justo después de que el tutor las ofreciera ("la 4",
  "con esquemas", "que lo decidas tú") → se guarda. Fuera de ese momento, un
  número es solo un número.
- Se guarda por el mismo camino que la tarjeta: evento y projector
  (invariante 1). El payload trae `explanation_style_chosen` (null = que decida
  LARIA) y el tutor lo confirma en una frase.
- Con material, estos turnos no pasan por el motor: no son una duda del
  documento, igual que `about`.

### 2. El tema sin propósito ni coletilla

Se corta "para + infinitivo" ("para armar…"), "porque…/ya que…" y lo que viene
tras una coma. "Matemáticas para ingeniería" no lleva infinitivo y se conserva.

### 3. Memoria sin hueco por caracteres

Si el tope de caracteres deja fuera mensajes que el resumen no cubre, se resumen
ya, con un lote de margen para no llamar al modelo cada turno. El tope sube a
24 000 caracteres (~6000 tokens por turno con el modelo barato). Una prueba de
propiedad lo verifica: tras cada mensaje, cada mensaje está en el resumen o en lo
reciente.

## Consecuencias

- Verificado con el modelo real en local: pregunta con las 7 opciones; "la 4"
  guarda `visual` y lo confirma; la siguiente duda llega con un esquema.
- El cliente puede reaccionar a `ask_learning_style` mostrando la tarjeta, y a
  `explanation_style_chosen` reflejando la elección sin pedirla otra vez.

## Pendiente, visto en la misma prueba

- **Calibración de la nivelación.** Un estudiante simulado que "casi no sabe de
  transistores" sacó 6/6 en la ronda base y 8/8 en la avanzada, y la primera
  pregunta se repitió en las dos rondas. Las preguntas "difíciles" parecen
  demasiado fáciles para el tema, y las rondas no evitan repetir ítems.
- **No hay ranking entre estudiantes.** La nivelación da un nivel por tema
  (básico, intermedio, avanzado), no una posición frente a otros.
