# ADR-009: Contar una vez, mirar el material del turno, y decir lo que se logró

- **Estado:** Aceptado
- **Fecha:** 2026-09-17
- **Rama de origen:** `feature/backend`
- **Decisores:** Equipo LARIA (orquestación backend)
- **Depende de:** [ADR-007](ADR-007-evidencia-ponderada-por-calidad.md), [ADR-008](ADR-008-progreso-derivado-no-declarado.md)
- **Implementa:** puntos 1 y 2 de la fase 3 de `docs/3_PLAN_EXPERIENCIA_PEDAGOGICA.md`

## Contexto

El ADR-007 fijó **cuánto pesa** cada evidencia y el ADR-008 quién puede escribirla. Faltaban tres
cosas de la misma familia: contarla bien, leerla del material correcto, y devolverle al estudiante lo
que dice de bueno.

**1. Un turno lento se contaba dos veces.** `record_ask_struggle()` metía `latency_ms` en la muestra
del concepto y, si superaba el umbral, llamaba además a `record_high_latency()`, que emitía una
**segunda** muestra sobre los mismos conceptos. Una observación, dos `attempts`, dos pasadas de EWMA
y —tras el ADR-007— dos unidades de evidencia débil.

**2. La velocidad dependía del largo del quiz.** `_track_velocity()` corría una vez por concepto
etiquetado. Un quiz de diez ítems aplicaba diez veces la EWMA `0.3·Δ + 0.7·v`, así que
`learning_velocity` la fijaban los últimos conceptos del lote y un quiz largo "aprendía" más rápido
que uno corto con el mismo resultado. Esa velocidad entra en la dificultad y en el ritmo.

**3. La dificultad tomaba el peor documento del estudiante.** Sin foco conceptual,
`DifficultyCalculator` hacía `min()` sobre **todos** los documentos: el material peor dominado fijaba
la dificultad de un tema sin relación con él. Y sin documentos daba `0.0` ⇒ `EASY`, castigando otra
vez la falta de datos, justo lo que el ADR-006 vino a corregir. (El score además pesaba la velocidad
con `0.1 × clamp(v) × 2`, que es `0.2`, no el `0.1` que documentaba la auditoría.)

**4. El canal positivo estaba construido y era inalcanzable.** `celebration` es uno de los seis tipos
de envelope y ningún camino lo devolvía: `envelope_type_for_mode()` solo mapea los cuatro modos
pedagógicos. `AffectState.CELEBRATORY` exige `last_score_ratio` y `ChatTutorService` nunca lo pasaba.
El sistema sabía qué dominaba el estudiante (`mastered_concepts`) y solo lo usaba para un gauge de
métricas. Es el P4 del plan —autoeficacia (Bandura)— sin cablear.

## Decisión

### Decisión 1 — Un turno es una observación

- La latencia alta **penaliza la muestra que ya describe el turno** (`ratio − 0.15` cuando
  `latency_ms ≥ HIGH_LATENCY_THRESHOLD_MS` y la clase no es ya `HIGH_LATENCY`), en vez de añadir otra.
- `record_high_latency()` sigue existiendo para su caso real: el projector, cuando el turno fue lento
  **sin** señal de lucha en el texto.
- `_apply_concept_evidence()` aplica la muestra y **devuelve el delta**; `_track_batch_velocity()`
  hace una sola observación de velocidad por evento, con la media de los conceptos tocados. La
  velocidad deja de depender de cuántos ítems etiquetó `ConceptTagger`.

### Decisión 2 — Sin foco, manda el material del turno

- `DifficultyCalculator.from_profile(..., document_id=...)`: sin conceptos en foco se usa el mastery
  de **ese** documento, y si no tiene intentos calificados se devuelve `MEDIUM`.
- El peso de la velocidad se escribe como la constante `_VELOCITY_WEIGHT = 0.2`, que es lo que el
  código ya hacía.

### Decisión 3 — El hito: un concepto que cruza a dominado, reconocido una sola vez

El plan dejaba abierta la pregunta *"¿qué cuenta como hito celebrable?"* porque celebrar de más quema
el canal. La respuesta:

- **Hito = un concepto en `mastered_concepts()` que aún no se le ha reconocido.** Reutiliza umbrales
  ya calibrados (mastery efectivo ≥ 0.8 **y** confianza ≥ 0.55): no hay hipótesis nueva que ajustar.
- **Irrepetible por concepto.** `StudentProfile.celebrated_concepts` lo recuerda; el hito se comunica
  una vez en la vida de ese concepto.
- **No se celebra remediando.** Si el turno es `SCAFFOLD` o el gate es `SEQUENCE`, no hay celebración
  ni tono celebratorio: sería ruido encima de una dificultad.
- **El tono se apoya en evidencia calificada.** `last_score_ratio` solo se pasa a `AffectPolicy` si el
  documento tiene `attempts > 0`: un documento sin quizzes lo tiene en `0.0` por defecto y leerlo
  sería inventar un mal resultado (ADR-007).
- **El perfil conserva un único escritor.** El servicio decide y comunica; el hito viaja en
  `TutorQuestionAskedEvent.celebrated_concept` y el projector lo marca dentro de la idempotencia por
  `event_id` (ADR-004, Decisión 2). El campo viaja también en el outbox: sin eso la feature estaría
  muerta solo en producción, como ya pasó en la fase 2 del ADR-006.
- Streaming y no-streaming comparten el cálculo, como exige el ADR-004, Decisión 3.

## Consecuencias

- El mastery de quien pregunta con turnos lentos baja algo menos que antes (una muestra, no dos) y su
  evidencia débil crece la mitad de rápido: eso retrasa un poco `OFFER`/`SEQUENCE` en el gate. Es la
  corrección del doble conteo, no un ablandamiento.
- La dificultad de un turno sobre material nuevo es `MEDIUM` aunque el estudiante venga de fallar en
  otro documento.
- El estudiante recibe, una vez por concepto dominado, un envelope `celebration` con
  `payload.celebrated_concept`, y tono `CELEBRATORY` en los turnos posteriores a un buen resultado
  calificado. La UI decide cómo renderizarlo; el backend ya lo emite.
- `GET /learning/me/profile` no expone `celebrated_concepts`: es estado de presentación, no evidencia.

## Fuera de alcance

- **Apagar `ADAPT_SHADOW_MODE`** (fase 4). El flag sigue en `True`: las señales del ADR-004 se
  computan y persisten, y el fragmento prompt-shaping no se inyecta. Encenderlo es una decisión de
  calibración —hoy no hay con qué medir si la adaptación mejora resultados— y el plan lo pone al
  final a propósito. Es un flag, no código: `ADAPT_SHADOW_MODE=false` cuando haya datos que lo
  justifiquen.
- **Anclar la explicación en lo que ya domina** (punto 3 de la fase 3): `mastered_concepts` entra en
  el envelope, todavía no en el prompt.
- **Explicabilidad pedagógica** (punto 4 de la fase 3, feature #4 del roadmap): decir *por qué* se
  está enseñando así. Es lo que hace legible todo lo demás y sigue pendiente.
- **Histéresis de `pace`** y la identidad de conceptos por materia (`desigualdades` ⇒
  `desigualdad social`), heredados de los ADR-007 y 008.
