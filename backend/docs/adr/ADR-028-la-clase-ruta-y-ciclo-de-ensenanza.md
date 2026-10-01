# ADR-028: La clase: de la nivelación a una ruta y un ciclo de enseñanza persistente

- **Estado:** Aceptado
- **Fecha:** 2026-10-01
- **Rama de origen:** `feature/backend`
- **Decisores:** Equipo LARIA (orquestación backend)
- **Complementa:** ADR-016/017 (nivelación), ADR-006/007 (gate y evidencia), ADR-008 (la ruta proyecta el perfil)

## Contexto

La evaluación terminaba en `POST /quizzes/{id}/attempts`: devolvía el nivel y
ahí se cortaba. Las rutas de aprendizaje solo se creaban a mano y nadie las
usaba para enseñar. El chat libre adaptaba el tono, pero no tenía plan ni sabía
cuándo avanzar. Hacía falta que el **backend** decidiera la clase y que el
modelo solo la redactara.

## Decisión

### 1. Ruta desde la nivelación

`POST /learning/paths/from-topic` es idempotente: si ya hay ruta para el tema,
devuelve la misma.

- **Tema cubierto por el grafo curricular:** módulos = todos sus prerrequisitos
  (bases primero) + el tema.
- **Tema fuera del grafo:** el modelo propone un temario de 3 a 6 subtemas. El
  backend lo valida (sin repetidos; un prerrequisito solo puede ser un subtema
  anterior, así que no hay ciclos posibles) y lo congela. Si no queda nada
  usable, se enseña el tema entero.
- **Cada módulo tiene un tipo:**
  - *contenido*: lo que vino a aprender;
  - *prerrequisito*: base del tema.
- **Prerrequisito sin evidencia → "dado por sabido".** No se enseña ni bloquea a
  sus dependientes. No medido ≠ medido en cero (invariante 3).
- **El contenido solo cuenta como sabido** si se superó en clase, o con mastery
  alto **y** veredicto "avanzado". Dos preguntas medias de la nivelación no
  prueban el tema: sin esta regla, quien salía "intermedio" veía la ruta
  completada antes de la primera clase.

### 2. El estado de la clase vive en la ruta

`LearningPathAggregate.teaching` se persiste con la ruta (Mongo y memoria). Cada
petición continúa exactamente donde quedó la anterior; no hay estado en memoria
del proceso.

Fases:

| Fase | Significado |
|---|---|
| `assessment` | El tema aún no tiene nivelación: no se enseña |
| `teaching` | Toca explicar el concepto actual |
| `check` | Explicación entregada; se espera la comprobación |
| `remediation` | Desvío a un prerrequisito; luego se vuelve |
| `advance` | Dominó el concepto; toca el siguiente |
| `completed` | No queda nada que enseñar |

No se reutilizó `TutorSession`: está atada a un documento y sus pasos son
heurísticos.

### 3. Las decisiones son de `TeachingPolicy`

Es un servicio de dominio puro. El modelo no elige concepto, ni dificultad, ni
cuándo avanzar o remediar.

- **Siguiente concepto:** el primer módulo pendiente. Si el `PrerequisiteGate`
  existente, aplicado sobre el grafo de la propia ruta, dice `SEQUENCE`
  (evidencia medida y repetida), se desvía primero a la causa raíz y se promete
  volver (invariante 5).
- **Tras la comprobación** (2 preguntas):

| Resultado | Qué hace |
|---|---|
| 2/2, entendió | Si domina (mastery ≥ 0.7, o dos comprobaciones seguidas superadas) avanza, o vuelve al tema si era un desvío. Si no, afianza con preguntas media y difícil |
| 1/2, a medias | Otro ejemplo, distinto del anterior |
| 0/2, no entendió | Si el gate ve una base floja medida (`OFFER`/`SEQUENCE`), o es el segundo fallo seguido, remedia la causa raíz. Si no, reformula, más paso a paso |

- **La dificultad de las preguntas la fija la política**, según el tipo de
  explicación, y el adaptador la impone sobre lo que diga el modelo.

### 4. Un solo sistema de evidencia

La comprobación es un quiz normal: se guarda, se califica en el servidor
(`QuizService.submit_attempt`) y su evento lleva la evidencia al perfil por el
projector, como cualquier quiz. El mastery que decide la clase es el mismo del
perfil; no hay un segundo sistema.

### 5. El modelo redacta, y se valida

`LessonGenerator.generate_lesson` pide en modo JSON:

- explicación;
- ejemplo resuelto;
- resumen del ejemplo;
- exactamente N preguntas con una sola opción correcta.

Lo que no tiene esa forma se reintenta una vez y, si vuelve a fallar, el cliente
recibe 502. Las preguntas salen etiquetadas con el concepto del paso.

### 6. API

- `POST /learning/paths/from-topic`.
- `POST /learning/paths/{id}/lesson`: el paso actual. Si ya se entregó, devuelve
  el mismo sin regenerarlo. 409 si falta la nivelación.
- `POST /learning/paths/{id}/check`: 409 si no es la comprobación pendiente.
- `GET /learning/paths/{id}` muestra el estado de la clase.

La voz usa `POST /speech` con el markdown de la lección; no hay otro sistema de
voz.

## Verificación

- Tests unitarios (política, agregado, temario, persistencia) y de punta a punta
  por HTTP, con repositorios y projector reales del modo memoria; solo el modelo
  es un doble. Cubren: evaluación → ruta, recuperación del mismo paso, evidencia
  en el perfil, a medias → nuevo ejemplo, no entendió → reformula → remedia →
  vuelve, avance hasta completar, 409 y 404.
- Contra el modelo real (OpenAI):
  - **fracciones:** falla → reformula → acierta → afianza → completada; el
    mastery pasó de 0.00 a 0.66 y a 0.87;
  - **ecuaciones:** dos fallos → remedia «Número entero» → vuelve a «Ecuaciones»;
  - **python:** temario propuesto y validado, avanza subtema a subtema.

## Pendiente

- **Títulos sin tildes** en los módulos que salen del grafo ("Numero entero"):
  las claves canónicas no llevan acentos.
- **Calidad de las preguntas.** El prompt exige una sola opción correcta, pero
  el servidor no puede verificar la equivalencia semántica (antes del ajuste
  salió "3/4" y "9/12" en la misma pregunta).
- **Frontend:** la pantalla de la clase la implementa la sesión del frontend.
