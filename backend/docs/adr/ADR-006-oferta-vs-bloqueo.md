# ADR-006: Oferta en vez de bloqueo — la intervención escala con la evidencia

- **Estado:** Aceptado
- **Fecha:** 2026-09-15
- **Rama de origen:** `feature/backend`
- **Decisores:** Equipo LARIA (orquestación backend)
- **Depende de:** [ADR-004](ADR-004-adaptacion-por-senales.md), [ADR-005](ADR-005-grafo-prerrequisitos-curado.md)
- **Implementa:** fases 1 y 2 de `docs/3_PLAN_EXPERIENCIA_PEDAGOGICA.md`

## Contexto

El `PrerequisiteGate` era binario: `blocked` sí o no. Con `blocked`, el motor **desviaba el foco en
silencio** — el alumno preguntaba por `matrices` y recibía `variable`, sin explicación. Y bloqueaba
con **cero evidencia**: `_is_gap` devolvía `True` cuando el concepto simplemente no estaba registrado.

Eso produce el peor resultado posible para el objetivo del producto: un alumno nuevo que pregunta algo
avanzado recibe una no-respuesta y un "no estás listo" implícito que nadie midió.

La pregunta abierta era: ¿ofrecer (respetar la autonomía, ganar evidencia) o bloquear (garantizar
secuencia curricular)?

## Decisión

**Ninguna de las dos como binario. La fuerza de la intervención escala con la fuerza de la evidencia.**

El binario es el error: fuerza a elegir entre insultar a quien no hemos medido y abandonar a quien sí
medimos con un hueco real. Cuatro acciones, según lo que el sistema *realmente sabe* del prerrequisito:

| Acción | Cuándo | Qué recibe el alumno |
|---|---|---|
| `PROCEED` | Prerrequisitos dominados, o el concepto no tiene | Respuesta a su pregunta |
| `INTEGRATE` | Hueco **no medido** (sin evidencia suficiente) | Respuesta a su pregunta, apoyada en la base ("esto se apoya en X") |
| `OFFER` | Hueco **medido** (evidencia de mastery bajo) | Respuesta a su pregunta **+** oferta explícita de repasar la base |
| `SEQUENCE` | Hueco medido **y repetido** (racha de error) | Se lidera con la base, explicando por qué y nombrando el destino |

### Invariante que esto blinda

**Nunca se desvía el foco en silencio.** El alumno siempre recibe respuesta a lo que preguntó, o una
explicación de por qué empezamos por otro lado. El desvío mudo queda prohibido.

### Por qué esta forma y no el binario

- **Coherencia con el resto del sistema.** ADR-004 exige `min_samples_for_adaptation` antes de adaptar;
  ADR-005 exige que una arista sea `CURATED` antes de que pueda bloquear. Era incoherente que la
  intervención **más invasiva** —negarle al alumno lo que pidió— fuera la única sin umbral de
  evidencia. `INTEGRATE` es ese umbral.
- **Autonomía.** El bloqueo elimina la agencia; la oferta la preserva y consigue la misma pedagogía.
  Quien elige seguir da evidencia; quien elige repasar recibe el andamiaje **y lo eligió**.
- **La evidencia que falta.** El intento es evidencia. Bloquear antes del intento la destruye: es
  justo el dato que al sistema le falta (el mastery conversacional no podía subir nunca).
- **No abandona la secuencia curricular.** `SEQUENCE` existe: ante un hueco medido y repetido, el
  sistema sí lidera con la base. Lo que desaparece no es la secuenciación, es la secuenciación
  **presuntiva**.

### La elección del alumno no necesita endpoint

Ante `OFFER`, la respuesta del alumno llega como su siguiente mensaje ("sí, repasemos" / "sigamos").
Es conversación, no un formulario. No se construye API de elección: sería código muerto sin frontend.

## Decisión 5 — La evidencia conversacional es débil, y el modelo lo refleja

La fase 2 abre un camino de evidencia positiva desde el chat. Una auditoría adversarial encontró
que, tal como se implementó primero, **un solo mensaje ("ah claro, ya entendí") llevaba un concepto
de 0.00 a 0.76 de mastery** y borraba una racha de cuatro fallos calificados. Eso no es medir: es
corromper el dato que sostiene todas las demás decisiones.

Reglas que lo acotan:

1. **`EvidenceSample.is_weak`**: la evidencia débil **nunca** fija el mastery por sí sola. La primera
   muestra de un concepto normalmente se asigna en crudo (`attempts == 1 → mastery = ratio`), lo cual
   es razonable para un ítem calificado pero no para una frase. La débil siempre pasa por la EWMA.
2. **Una racha de error se descuenta, no se borra**: un acierto débil hace
   `error_streak -= 1`. Si la borrara, una frase de cortesía desarmaría `SEQUENCE` y el gate oscilaría
   entre liderar con la base y abandonarla en turnos consecutivos.
3. **La dificultad repetida en el chat cuenta como dificultad repetida**: `ASK_STRUGGLE` y
   `HELP_REQUEST` incrementan `error_streak`. Antes solo lo hacían los quizzes, así que `SEQUENCE`
   era inalcanzable justo para el estudiante que esta fase venía a rescatar: diez turnos seguidos de
   confusión medida sobre el mismo concepto dejaban el gate en `OFFER` para siempre.
4. **El umbral de evidencia decide si algo ES un hueco, no invalida un nivel que ya pasa.** El orden
   importa: un prerrequisito con mastery suficiente pero pocas muestras no es un hueco.

### Requisito de transporte

Los campos `signal_observations`, `answer_length` y `focus_concepts` **deben** viajar en el
serializador del outbox (`infrastructure/mongodb/outbox_event_bus.py`). Producción exige
`EVENT_BUS_BACKEND=outbox`, y el serializador tiene lista explícita de campos: omitirlos deja muertas
la adaptación del ADR-004 y la evidencia positiva de este ADR **solo en producción**, porque los tests
del projector usan `InMemoryEventBus`, que pasa el objeto por referencia. Hay test de roundtrip.

## Consecuencias

- `GateResult.blocked` pasa a significar exactamente una cosa: "el turno lidera con la base"
  (`SEQUENCE`), no "hay huecos".
- Un alumno nuevo ya no puede ser desviado: sin evidencia, el máximo es `INTEGRATE`.
- Los umbrales (`min_evidence_for_gap`, `error_streak_for_sequence`) son hipótesis nombradas y
  configurables, como los cutoffs del ADR-004.
- Riesgo aceptado: un alumno puede avanzar sobre una base floja si elige seguir. Se considera preferible
  a negarle contenido por una presunción, y el intento genera la evidencia para corregir el rumbo.

## Fuera de alcance

- Capturar el texto del ejemplo o la analogía que funcionó (`remember_example` / `remember_analogy`):
  exige que el LLM etiquete su propia salida (salida estructurada). Queda para después; lo que sí se
  corrige aquí es que la memoria de estrategia y estilo solo se escriba **ante evidencia positiva**.
