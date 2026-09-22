# Contrato del envelope del tutor

> **Para quien construye el cliente.** Todos los JSON de esta página son **capturas reales** del
> backend, no maquetas. Si algo aquí no coincide con lo que recibes, es un bug nuestro: repórtalo.
>
> Catálogo de rutas: [`endpoints.md`](endpoints.md) · Guía de integración:
> [`frontend-integration.md`](frontend-integration.md) · Rutas y quizzes:
> [`api-contracts.md`](api-contracts.md)

## Qué es

Cada respuesta del tutor viaja con un **envelope**: una estructura pequeña que dice *qué* renderizar
y *cómo* se expresa el tutor. Lo decide el dominio con la evidencia del estudiante, **no el modelo de
lenguaje**. Es determinista: con el mismo perfil y la misma pregunta, sale el mismo envelope.

El modelo solo escribe `payload.content`. Todo lo demás —el tipo, la emoción, el modo, la
dificultad, el foco— lo decide `PedagogicalEngine` antes de llamar al LLM.

## Dónde viaja

| Camino | Dónde aparece |
|---|---|
| `POST /api/v1/chats/{chat_id}/messages` | En `metadata` del mensaje `assistant` de la respuesta |
| `POST /api/v1/chats/{chat_id}/stream` | Evento SSE `envelope`, antes de `done` |

En ambos casos el mensaje queda **persistido** con su envelope: si recargas el chat, `metadata` sigue
ahí. No hace falta guardarlo en el cliente.

Orden de eventos del SSE: `thinking` → `token`(n) → `envelope` → `done`. En caso de fallo:
`thinking` → `error`, y el evento `error` **también** es un envelope.

## Forma

```
{ "type": <EnvelopeType>, "emotion": <AffectState>, "payload": { ... } }
```

### `type` — qué renderizar

| Valor | Cuándo lo emite el backend | Qué esperaría un cliente |
|-------|---------------------------|--------------------------|
| `explanation` | modo `explain`: se explica el tema asumiendo capacidad | burbuja normal, quizá más ancha |
| `hint` | modo `scaffold`: hay evidencia medida de dificultad | destacado (borde, icono), es andamiaje |
| `answer` | modo `socratic`, o chat **sin material** | burbuja normal |
| `celebration` | el estudiante acaba de cruzar un concepto a dominado | reconocimiento visible, **una sola vez por concepto** |
| `error` | el proveedor de IA falló | mensaje de fallo reintentable |
| `quiz` | — **hoy no se emite nunca** (ver abajo) | — |

> **`quiz` está en la unión y es inalcanzable.** Mapea al modo `practice`, y ese modo solo aparece
> cuando la intención es generar un cuestionario, camino que no produce envelope (el quiz se pide a
> `POST /chats/{id}/quiz` y devuelve el quiz, no un mensaje). Se documenta para que nadie construya
> una rama de UI que nunca se va a ejecutar. Si algún día se emite, será con este mismo contrato.

### `emotion` — cómo se expresa

| Valor | Cuándo |
|-------|--------|
| `patient` | andamiaje (`scaffold`) o ritmo lento: paciencia, no ánimo genérico |
| `calm` | modo socrático: se está preguntando, no explicando |
| `celebratory` | el último resultado **calificado** del material fue ≥ 0.85 |
| `encouraging` | por defecto |

### `payload` — el contenido y el porqué

**Solo `content` está garantizado.** El resto depende del camino: un chat sin material no pasa por el
motor pedagógico, así que no trae `mode`, `difficulty`, `focus_concepts` ni control-flow. **El cliente
debe degradar con elegancia**: `payload.mode ?? null`, nunca `payload.mode.toUpperCase()`.

| Campo | Siempre | Qué es |
|-------|---------|--------|
| `content` | sí | El texto a mostrar. Lo escribe el modelo |
| `grounded` | sí | `true` = el turno pasó por el motor con material; `false` = conversación libre, **no prometas tutoría adaptativa** |
| `intent` | sí | Intención detectada: `learn`, `quiz`, `hint`, `celebrate`, `general` |
| `mode` | solo con material | `explain` · `socratic` · `scaffold` · `practice` |
| `difficulty` | solo con material | `easy` · `medium` · `hard` |
| `cognitive_style` | solo con material | `simple` · `technical` · `mathematical` · `analogy` · `visual` · `step_by_step` |
| `focus_concepts` | solo con material | Conceptos sobre los que versa el turno, el primero es el principal |
| `session_step` | solo con material | `introduce` · `hint` · `practice` · `check` |
| `chunk_explanation`, `practice_before_advance` | solo con material | Orquestación sugerida: trocear la explicación, pedir práctica antes de avanzar |
| `celebrated_concept` | solo con `type: celebration` | Qué concepto se acaba de dominar |
| `explanation` | cuando hay adaptación activa | **Por qué el tutor habla así**, en una frase ([ADR-013](adr/ADR-013-decir-por-que.md)). Ausente si no hubo nada que adaptar o si la adaptación no se está aplicando: nunca se promete lo que no se hizo |

## Ejemplos reales

### `explanation` — alumno con material, sin evidencia en contra

```json
{
  "type": "explanation",
  "emotion": "encouraging",
  "payload": {
    "content": "Restas 3 en ambos lados y divides entre 2.",
    "intent": "general",
    "grounded": true,
    "practice_before_advance": false,
    "chunk_explanation": false,
    "mode": "explain",
    "difficulty": "medium",
    "cognitive_style": "simple",
    "focus_concepts": ["variable", "ecuacion"],
    "session_step": "introduce"
  }
}
```

### `hint` — hay evidencia medida de dificultad

```json
{
  "type": "hint",
  "emotion": "patient",
  "payload": {
    "content": "Vamos por partes: ¿qué representa la x aquí?",
    "intent": "hint",
    "grounded": true,
    "practice_before_advance": false,
    "chunk_explanation": false,
    "mode": "scaffold",
    "difficulty": "easy",
    "cognitive_style": "mathematical",
    "focus_concepts": ["variable", "ecuacion"],
    "session_step": "introduce"
  }
}
```

### `answer` — modo socrático (dominio alto)

```json
{
  "type": "answer",
  "emotion": "calm",
  "payload": {
    "content": "Buena pregunta: ¿qué le pasa a la igualdad si haces lo mismo en los dos lados?",
    "intent": "general",
    "grounded": true,
    "practice_before_advance": false,
    "chunk_explanation": false,
    "mode": "socratic",
    "difficulty": "hard",
    "cognitive_style": "simple",
    "focus_concepts": ["variable", "ecuacion"],
    "session_step": "introduce"
  }
}
```

### `answer` — chat libre, **sin material**

Fíjate en el payload reducido: esto es lo que hay que saber manejar.

```json
{
  "type": "answer",
  "emotion": "encouraging",
  "payload": {
    "content": "Puedo tutorizarte sobre el material que subas.",
    "intent": "general",
    "grounded": false
  }
}
```

### `celebration` — un concepto cruzó a dominado

```json
{
  "type": "celebration",
  "emotion": "calm",
  "payload": {
    "content": "Ya manejas variable. Vamos con ecuaciones.",
    "intent": "general",
    "grounded": true,
    "practice_before_advance": false,
    "chunk_explanation": false,
    "celebrated_concept": "variable",
    "mode": "socratic",
    "difficulty": "hard",
    "cognitive_style": "simple",
    "focus_concepts": ["variable"],
    "session_step": "introduce"
  }
}
```

`emotion` puede no ser `celebratory`: el tono lo decide el último resultado calificado, y el hito lo
decide el dominio del concepto. Son dos señales distintas y pueden no coincidir.

### Con `explanation` — el tutor dice por qué habla así

Mismo turno que el primero, pero de un estudiante cuyo historial muestra que abandona las
explicaciones largas y pide ejemplos, y con la adaptación aplicada (fuera del modo sombra):

```json
{
  "type": "explanation",
  "emotion": "encouraging",
  "payload": {
    "content": "Restas 3 en ambos lados y divides entre 2.",
    "intent": "general",
    "grounded": true,
    "explanation": "Voy al grano porque las explicaciones largas se te hacen cuesta arriba, y te pongo 2 ejemplos porque los has pedido varias veces.",
    "practice_before_advance": false,
    "chunk_explanation": false,
    "mode": "explain",
    "difficulty": "medium",
    "cognitive_style": "simple",
    "focus_concepts": ["variable", "ecuacion"],
    "session_step": "introduce"
  }
}
```

La frase está escrita para mostrarse tal cual. Nombra la conducta, nunca la métrica, y **solo aparece
cuando la adaptación se aplicó de verdad**: hoy el despliegue corre en modo sombra, así que este
campo no llegará todavía ([ADR-013](adr/ADR-013-decir-por-que.md)).

### `error` — falló el proveedor

```json
{
  "type": "error",
  "emotion": "encouraging",
  "payload": {
    "content": "Lo siento, no pude generar una respuesta en este momento. Intenta de nuevo.",
    "grounded": true
  }
}
```

En el turno normal llega como mensaje `role: "system"`; en SSE, como evento `error`.

## Reglas para el cliente

1. **`content` es lo único garantizado.** Todo lo demás es opcional: trata ausencia como "no aplica".
2. **No infieras pedagogía.** Si quieres mostrar "te estoy andamiando", usa `type`/`mode`, no el
   texto. El texto lo escribe un modelo y cambia.
3. **`grounded: false` es información, no un error.** Es el momento de invitar a subir material, no
   de mostrar un fallo.
4. **`celebration` se emite una sola vez por concepto**, para siempre. Si la descartas, el estudiante
   no la vuelve a ver: no la escondas detrás de un toast de 2 segundos.
5. **Nunca uses `content` para evaluar.** La corrección de un quiz vive en
   `POST /quizzes/{id}/attempts` y la calcula el servidor.
6. **`explanation` es del estudiante, no de depuración.** Está escrita para mostrarse tal cual
   ("Voy al grano porque las explicaciones largas se te hacen cuesta arriba"). No la recortes ni la
   escondas en un tooltip: es lo que convierte la adaptación en colaboración.
7. **Tipos y emociones pueden crecer.** Trata valores desconocidos con un caso por defecto en vez de
   romper la vista.

## Qué puede cambiar y qué no

| Estable | Puede cambiar sin aviso |
|---------|-------------------------|
| Las tres claves `type`, `emotion`, `payload` | Que se añadan campos nuevos al `payload` |
| `payload.content` siempre presente | El **texto** de `content` (lo escribe un modelo) |
| Los valores de `type` y `emotion` ya publicados | Que aparezcan valores nuevos |
| Que el envelope sea determinista y del dominio | Qué evidencia dispara cada `type` (es pedagogía, y evoluciona) |

Origen de las decisiones: [ADR-004](adr/ADR-004-adaptacion-por-senales.md) (señales y control-flow),
[ADR-006](adr/ADR-006-oferta-vs-bloqueo.md) (ofrecer, no bloquear),
[ADR-009](adr/ADR-009-contabilidad-y-canal-positivo.md) (celebración y afecto).
