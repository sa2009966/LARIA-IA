# ADR-008: El progreso se deriva de la evidencia — nadie lo declara

- **Estado:** Aceptado
- **Fecha:** 2026-09-17
- **Rama de origen:** `feature/backend`
- **Decisores:** Equipo LARIA (orquestación backend)
- **Depende de:** [ADR-007](ADR-007-evidencia-ponderada-por-calidad.md), [ADR-003](ADR-003-mastery-forgetting-prereqs.md)

## Contexto

El principio del producto es que **responder bien no prueba comprensión**: el mastery se gana con
evidencia y `StudentProfile` es su única fuente de verdad. Había dos lugares donde el progreso se
**declaraba** en vez de derivarse, uno dentro del agregado y otro en la frontera HTTP.

**1. `pace` se fijaba a mano y nadie lo recalculaba.** `record_ask_struggle()` terminaba con
`if entry.mastery < 0.4: self.pace = "slow"`, fuera de `_update_pace()`, que solo corre en
`record_quiz_result()`. Una pregunta con señal de struggle dejaba al estudiante en `slow` hasta que
hiciera un quiz — quizá nunca. Y `pace` no es decorativo: resta `0.1` en `DifficultyCalculator` y
fuerza `STEP_BY_STEP` en `CognitiveStyleSelector`. Además `_update_pace` contaba como "documento
débil" cualquier documento con mastery bajo, incluido el que solo bajó por señales de auto-reporte,
que el ADR-007 ya había declarado no-medición.

La misma sombra aparecía en `AffectPolicy`: la rama `profile.pace == "slow"` devolvía `ENCOURAGING`,
que es el valor por defecto. La rama existía, se leía como intención y no cambiaba nada; su test
pasaba sin ejercitarla.

**2. El cliente podía escribir su propio mastery.** `PUT /learning/paths/{id}/modules/{id}/mastery`
aceptaba `{"mastery": 0.9}` y marcaba el módulo `completed`, desbloqueando los siguientes. Sin
evidencia, sin quiz, sin tutoría: el estudiante se declaraba competente y la ruta lo creía.
`LearningModule.mastery` era además una segunda verdad del mastery y `module.prerequisites` una
segunda verdad de los prerrequisitos —justo lo que el [ADR-005](ADR-005-grafo-prerrequisitos-curado.md)
acababa de consolidar en `ConceptGraph`— y nunca se sincronizaba con el perfil (W13 de la auditoría,
R10 de sus recomendaciones, y el "No ahora" del plan de experiencia pedagógica).

## Decisión

**El progreso es derivado. Ningún actor —ni un método del agregado, ni el cliente— lo declara.**

### Decisión 1 — `pace` tiene un único escritor

- `_update_pace()` es el único sitio que escribe `pace`. `record_ask_struggle()` lo **llama** en vez
  de asignar, así que el ritmo se recalcula con cada evidencia, en los dos caminos.
- `_update_pace()` cuenta solo documentos con `attempts > 0`: los intentos calificados hablan del
  ritmo; un documento que solo bajó por auto-reporte, no (ADR-007).
- Consecuencia medible: un estudiante que solo pregunta queda `steady` —"su ritmo no se ha medido"—
  en vez de `slow`.
- `AffectPolicy`: ritmo lento → `PATIENT`, junto con el modo `SCAFFOLD`. La rama deja de ser
  decorativa y `ENCOURAGING` queda como lo que es, el default.

### Decisión 2 — La ruta de aprendizaje es una proyección de solo lectura

- **Se elimina** `PUT /learning/paths/{id}/modules/{id}/mastery` y su schema. No se sustituye por
  otra escritura: no hay forma de declarar progreso por HTTP.
- `LearningPathAggregate.project_mastery(mastery_by_concept)` deriva el mastery y el estado de cada
  módulo desde el perfil, y `_unlock_dependents()` abre lo que la evidencia respalde.
- `StudentProfile.effective_mastery_by_concept()` es el snapshot que se le pasa: mastery **efectivo**,
  con olvido incluido, coherente con el ADR-003.
- La proyección ocurre en cada lectura (`GET /paths`, `GET /paths/{id}`, y la respuesta del `POST`)
  y **no se persiste**: guardarla recrearía las dos verdades que esto elimina.
- `record_mastery()` sobrevive como primitiva de proyección, con el estado derivado también cuando el
  mastery **baja**: sin esa rama un módulo se quedaba `completed` después de que el perfil perdiera la
  evidencia (olvido, documento borrado).

### Lo que esto NO cambia

- La ruta sigue existiendo como **plan**: crearla, listarla, consultarla y borrarla no cambia.
  Un plan lo puede escribir quien lo diseña; el progreso no.
- El grafo curricular sigue siendo `ConceptGraph` para la tutoría. La ruta no gatea nada del turno.

## Consecuencias

- Una ruta refleja la evidencia real del estudiante en el momento de leerla, incluido el olvido: un
  módulo puede volver de `completed` a `available` si el perfil decae. Es la consecuencia buscada de
  que el mastery tenga curva de olvido.
- `module.prerequisites` sigue siendo una lista propia de la ruta, distinta del `ConceptGraph`. Ya no
  es una segunda verdad del *mastery*, pero sí sigue siendo una segunda verdad de las *aristas*.
  Unificarlas exige decidir si la ruta es un producto (ver "Fuera de alcance").
- Tres tests de API que ejercitaban la escritura se sustituyen por tres que blindan lo contrario:
  el endpoint no existe, el progreso se proyecta, y la proyección no se persiste.

## Fuera de alcance

- **Si la ruta de aprendizaje debe ser un producto** o retirarse del API. El plan de experiencia
  pedagógica la dejó en "No ahora" y sigue sin cliente que la consuma (`lib/laria-api.ts` de
  `feature/frontend` no la usa). Esta decisión la deja inofensiva, no la promueve.
- **Unificar `module.prerequisites` con `ConceptGraph`**: tiene sentido cuando la ruta se decida como
  producto, no antes.
- **Histéresis en `pace`**: sigue saltando de `slow` a `fast` sin zona intermedia en cuanto la
  velocidad y los documentos fuertes lo permiten.
