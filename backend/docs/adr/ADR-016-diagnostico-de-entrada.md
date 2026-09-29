# ADR-016: El tutor puede evaluarte antes de enseñarte

- **Estado:** Aceptado
- **Fecha:** 2026-09-25
- **Rama de origen:** `feature/backend`
- **Decisores:** Equipo LARIA (orquestación backend)
- **Matiza:** [ADR-006](ADR-006-oferta-vs-bloqueo.md) (no asumir ignorancia) · [ADR-007](ADR-007-evidencia-ponderada-por-calidad.md) (calidad de la evidencia)

## Contexto

Un estudiante escribe *"quiero aprender ecuaciones"*. Hoy el motor detecta la
intención (`learn`), no encuentra evidencia medida, y toma esta rama:

```python
elif unmeasured and not in_hint:
    mode = PedagogicalMode.EXPLAIN
    objective = "Responder lo que el estudiante preguntó, asumiendo capacidad…"
```

Explica, y cierra con **una** pregunta de verificación. El modo socrático —el que
pregunta en vez de contar— solo se activa con `concept_m >= 0.7`, es decir **para
quien ya domina**. Justo al revés de lo que hace falta al empezar.

Eso venía del ADR-006, y su razón sigue siendo buena: la ausencia de datos no es
evidencia de ignorancia, y presuponer poco a un alumno nuevo es a la vez injusto y
mal pedagógico. Pero resolvía solo la mitad del problema. La otra mitad es que **el
motor arranca ciego**, y se nota en dos números:

- `min_samples_for_adaptation = 5`: no adapta hasta el quinto turno.
- La confianza sube 0,08 por observación y `mastered_concepts` exige 0,55: un
  concepto no cuenta como dominado **hasta el séptimo acierto calificado**.

Un producto cuya promesa es "me conoce y se adapta a mí" no puede tardar cinco
turnos en empezar a conocerte.

## Decisión

Cuando el estudiante expresa intención de aprender un tema, el tutor **puede
ofrecerle un diagnóstico corto y calificado** antes de explicar.

### 1. Se ofrece, no se impone

Es la línea que el ADR-006 no deja cruzar. Un alumno que solo quiere una respuesta
rápida no debe pasar un examen para obtenerla. El tutor responde lo que le
preguntaron **y además** ofrece el diagnóstico; el estudiante decide.

Por eso el diagnóstico es un endpoint que el cliente llama cuando el alumno acepta,
no un turno que el backend fuerza. Forzarlo sería bloquear, y eso ya se decidió que
no (ADR-006, ADR-015).

### 2. Evidencia medida, no auto-reporte

Preguntar *"¿qué sabés ya de ecuaciones?"* produce **auto-reporte**, que el ADR-007
pesa a la mitad: harían falta diez respuestas para pesar lo que pesan cinco ítems.
Y hay un problema peor que el peso: la gente no sabe lo que no sabe.

El diagnóstico son **ítems de opción múltiple corregidos en el servidor**. Entra por
el mismo camino que cualquier quiz —`POST /quizzes/{id}/attempts`— así que vale lo
que vale un ítem calificado, sin excepciones ni ponderaciones especiales.

### 3. Escalera de dificultad: fácil → media → difícil

Seis ítems repartidos **2 / 2 / 2**. No es decoración: un diagnóstico de dificultad
plana solo dice "aprueba o no aprueba", mientras que una escalera encuentra **el
techo**, que es lo que el motor necesita para elegir modo y dificultad.

### 4. Se prueba el tema y su base

Los ítems no cubren solo el tema pedido: incluyen hasta **dos prerrequisitos
directos** del grafo. Es lo que convierte el diagnóstico en algo que el
`PrerequisiteGate` puede usar después — sin evidencia sobre la base, el gate no
puede escalar a `OFFER` ni a `SEQUENCE` por mucho que el tema esté medido.

La escalera y la base se combinan así: los ítems fáciles van a los prerrequisitos,
los difíciles al tema. Quien falla lo fácil tiene un hueco de base; quien acierta
todo menos lo difícil está listo para avanzar.

### 5. No hace falta libro

Es el punto que motivó todo esto. `TutorPolicy.generate_quiz` ya recibía el
contenido **como texto**, no como documento, así que generar desde un tema no exigía
un motor nuevo. Lo que sí exigía es aceptar que **un quiz puede no tener documento**:
`QuizAggregate.document_id` pasa a ser opcional y aparece `topic`.

Cuando no hay documento, el projector registra la evidencia **por concepto** y no
toca `mastery_by_document`. `StudentProfile` ya lo soportaba
(`record_concept_result(..., document_id=None)`); lo que faltaba era usarlo.

## Consecuencias

- Un estudiante sin material puede ser evaluado y adaptado. Hasta hoy, sin libro no
  había evidencia posible y el tutor era un chatbot genérico.
- El arranque en frío pedagógico baja de cinco turnos a **un diagnóstico**: seis
  ítems calificados sobre tres o cuatro conceptos dejan el perfil listo para que el
  gate y la política actúen desde el turno siguiente.
- `document_id` opcional obliga a que todo consumidor lo trate como tal. El riesgo
  es que algo asuma que existe; los tests cubren el camino sin documento de punta a
  punta.
- El diagnóstico **no cuenta como celebración ni como fallo**: es una medición. Si
  sale mal, el alumno no recibe un juicio, recibe un plan.

## Fuera de alcance

- **Diagnóstico adaptativo por ítem** (que la siguiente pregunta dependa de la
  anterior, tipo CAT). Multiplicaría las llamadas al modelo y exige calibración que
  hoy no tenemos. La escalera fija es la versión honesta de lo que sí se puede
  sostener.
- **Forzar el diagnóstico** antes de responder. Ver decisión 1.
