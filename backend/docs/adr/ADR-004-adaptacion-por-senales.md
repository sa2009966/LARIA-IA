# ADR-004: Adaptación por señales — precedencia, ortogonalidad y familias de parámetros

- **Estado:** Aceptado
- **Fecha:** 2026-09-14
- **Rama de origen:** `feature/backend`
- **Decisores:** Equipo LARIA (orquestación backend)

## Contexto

El blueprint del motor adaptativo define señales de comportamiento (`attention_span`,
`long_explanation_abandonment`, `clarification_rate`, …) que alimentan una `AdaptivePolicy`
para producir parámetros de adaptación (`explanation_length`, `examples_per_explanation`, …).

Cuatro huecos del blueprint permitían que cada implementación los rellenara con suposiciones
distintas. Este ADR los cierra como decisión escrita. **Ninguna feature adaptativa nueva
(grafo de prerrequisitos ampliado, repetición espaciada, misconceptions) se implementa antes
de estos cuatro puntos.**

---

## Decisión 1 — Resolución de conflictos entre señales (precedencia, no orden de `if`)

Varias señales pueden pedir valores distintos del mismo parámetro. Resolverlo por orden de
evaluación es un bug: la última rama sobrescribe a la primera sin justificación pedagógica.

**Regla de precedencia: evidencia observada > proxy inferido.**

Una señal es *observada* cuando mide una conducta directa del estudiante (abandonó una
explicación larga, pidió una aclaración, pidió un ejemplo). Es *proxy* cuando infiere un
estado interno a partir de una correlación (turnos por sesión ⇒ "capacidad de atención").

Ante conflicto, gana la observada. El proxy solo decide si ninguna observada es concluyente.

### Tabla de precedencia completa

| Parámetro | Familia | Señales que compiten | Precedencia | Fallback |
|---|---|---|---|---|
| `explanation_length` | prompt-shaping | `long_explanation_abandonment` (observada), `attention_span` (proxy) | 1. abandono `> CUT_ABANDONMENT` ⇒ `short`<br>2. atención `> CUT_ATTENTION` ⇒ `long` | `medium` |
| `examples_per_explanation` | prompt-shaping | `example_request_rate` (observada) — sin conflicto | banda alta ⇒ 3, media ⇒ 2 | 1 |
| `socratic_question_rate` | prompt-shaping | `self_correction` (observada) — sin conflicto | banda alta ⇒ `high`, media ⇒ `medium` | `low` |
| `prefers_analogy` | prompt-shaping | `analogy_affinity` (observada) — sin conflicto | `> CUT_PREFERENCE` ⇒ `True` | `False` |
| `practice_before_advance` | control-flow | `practice_seeking` (observada) — sin conflicto | `> CUT_PREFERENCE` ⇒ `True` | `False` |
| `chunk_explanation` | control-flow | `response_latency` (observada) — sin conflicto | banda alta ⇒ `True` | `False` |

Solo `explanation_length` tiene conflicto real hoy. Los demás se resuelven con una única señal
y **no requieren** resolución. La tabla se mantiene completa a propósito: al añadir un parámetro
hay que darle una fila, no un `if` suelto.

### Por qué precedencia y no pesos

Precedencia es determinista, explicable al estudiante y debuggable en un test. Un esquema de
pesos/scoring exige datos de outcome que todavía no tenemos para calibrar. Se reevalúa cuando
haya histórico suficiente para medir qué adaptación mejoró el mastery.

### Cutoffs como hipótesis nombradas

Ningún umbral vive como literal en una rama. Todos están en `AdaptationCutoffs`
(`domain/services/adaptive_policy.py`), con valores por defecto y sobrescritura por entorno
(`ADAPT_*` en `Settings`). Son **hipótesis**, no constantes físicas:

`band_low=0.34`, `band_high=0.67`, `abandonment=0.55`, `attention_span=0.6`,
`preference=0.4`, `ewma_alpha=0.3`, `long_explanation_chars=900`,
`session_gap_minutes=20`, `min_samples_for_adaptation=5`.

**Invariante blindada por test:** abandono alto + atención alta ⇒ `short`, nunca `long`.

---

## Decisión 2 — Fuente de verdad de `interaction_gap_ms`

`response_latency` y `long_explanation_abandonment` dependen de "cuándo fue la última
interacción" y "qué largo tenía la respuesta anterior".

1. **El gap se calcula en el borde**, en el servicio que recibe la pregunta, con wall-clock real.
   **No** en el projector: el projector es asíncrono y su `now` no reconstruye el gap vivido.
2. **`last_interaction_at` y `last_answer_length` viven en `StudentProfile`** (opción pragmática).
   El perfil ya se carga en cada turno para decidir ⇒ cero stores nuevos, cero round-trips extra.
3. **Cálculo y escritura se separan.** El borde mide (`profile.interaction_gap_ms()`) y adjunta
   las observaciones resultantes a `TutorQuestionAskedEvent` (`signal_observations`,
   `answer_length`); el `LearningEvidenceProjector` las escribe. Motivo: `StudentProfile` tiene
   deliberadamente **un solo escritor**, con idempotencia por `event_id`. Escribir también desde
   el borde añadiría un segundo escritor compitiendo por el lock optimista sin ganar nada: lo
   que el projector no puede hacer es *medir* el gap, no *guardarlo*.
4. La alternativa purista (read model `InteractionState` separado) queda documentada como
   refactor **opcional**, a ejecutar solo si el acoplamiento en `StudentProfile` estorba.

El perfil expone `interaction_gap_ms(now)` y `record_interaction(answer_length, at)`. Ningún
servicio calcula el gap por su cuenta a partir de otra fuente.

---

## Decisión 3 — Familias de parámetros: prompt-shaping vs. control-flow

`answer_stream()` ignoraba la decisión pedagógica: la adaptación no se aplicaba justo donde el
estudiante pasa la mayor parte del tiempo. La solución no es excluir el streaming, es partir
los parámetros en dos familias:

- **prompt-shaping** (`explanation_length`, `examples_per_explanation`, `socratic_question_rate`,
  `prefers_analogy`): texto aditivo al system prompt. Se inyecta **antes** de abrir el stream ⇒
  idéntico en streaming y no-streaming, coste casi nulo.
- **control-flow** (`practice_before_advance`, `chunk_explanation`): orquestación alrededor de
  la generación, no prompt. El servicio los aplica con o sin streaming.

`TutorPolicy.answer_question()` es el único punto de inyección del fragmento prompt-shaping, y
lo consumen por igual `LlmGate.answer_question()` y `LlmGate.answer_question_stream()`.

**Regla escrita:** todo parámetro de adaptación nuevo debe clasificarse como *prompt-shaping* o
*control-flow* en el momento de definirse. `AdaptationParameters` no admite campos sueltos fuera
de las dos familias.

`POLICY_VERSION` pasa a `v3`.

---

## Decisión 4 — Ortogonalidad: señales observacionales vs. señales de política

`confidence_expression` se deriva de `clarification_rate`. Si ambas entran a `AdaptivePolicy`,
la misma evidencia se cuenta dos veces y la política sobrerreacciona.

1. `confidence_expression` es señal **solo observacional**: dashboard y transparencia. No entra
   a `AdaptivePolicy` en ninguna rama.
2. `clarification_rate` es la única del par que puede alimentar la política.
3. **Regla escrita:** ninguna señal derivada de otra puede alimentar `AdaptivePolicy` junto con
   su componente. Se declara en `DERIVED_FROM` y `AdaptivePolicy.decide()` filtra la entrada a
   `POLICY_SIGNALS` antes de evaluar nada.
4. Si en el futuro se quiere adaptar por confianza, debe derivarse de una fuente **ortogonal**
   (calibración confianza-declarada vs. acierto real), nunca de `1 - clarification_rate`.

---

## Decisión 5 — Arbitraje: la forma no puede contradecir al fondo

*(añadida el 2026-09-22, antes de apagar el modo sombra)*

`PedagogicalEngine.select()` y `AdaptivePolicy.decide()` corren en paralelo en `prepare_pedagogy` y
`TutorPolicy` los concatenaba sin comprobar nada:

```python
system = f"{system} {adaptation.to_prompt_fragment()}"
```

No es un riesgo teórico. Con `LONG_EXPLANATION_ABANDONMENT` y `SELF_CORRECTION` altos, la política
produce `explanation_length=short` y `socratic_question_rate=high`; si el motor decidió `SCAFFOLD`,
el prompt resultante dice, seguido:

> "Usa andamiaje: pista → ejemplo parcial → invitación a completar. Reduce carga cognitiva; un paso
> a la vez." … "Responde de forma breve: ve al grano, evita preámbulos. Guía sobre todo con
> preguntas; deja que el estudiante concluya."

Andamiaje gradual, brevedad e interrogatorio a la vez. Eso no es adaptación: es ruido con dos
autores.

**La regla: la pedagogía decide el fondo, la adaptación decide la forma, y cuando la forma
contradice al fondo gana el fondo.** El fondo sale de evidencia del estudiante sobre *ese* concepto;
la forma, de señales de comportamiento agregadas. Ante conflicto, manda lo específico.

### Tabla de precedencia

Se aplica en `domain/services/plan_composer.py`, función pura, antes de componer el prompt.

| # | Condición (fondo) | Parámetro vetado | Valor efectivo | Por qué |
|---|-------------------|------------------|----------------|---------|
| 1 | `mode = SCAFFOLD` o `gate_action = SEQUENCE` | `explanation_length = short` | `medium` | El andamiaje es pista → ejemplo parcial → invitación; "ve al grano" lo anula |
| 2 | `mode = SCAFFOLD` o `gate_action = SEQUENCE` | `socratic_question_rate ∈ {medium, high}` | `low` | Andamiar es sostener, no interrogar a quien ya está atascado |
| 3 | `mode = SCAFFOLD` o `gate_action = SEQUENCE` | `examples_per_explanation = 0` | `1` | El ejemplo parcial **es** el andamiaje; sin ejemplo no hay tal |
| 4 | `cognitive_style = STEP_BY_STEP` | `explanation_length = short` | `medium` | "Paso a paso" y "ve al grano" se contradicen |
| 5 | `cognitive_style = ANALOGY` | `prefers_analogy = True` | `False` | El estilo ya pide analogía; repetirlo en el prompt es redundancia, no énfasis |
| 6 | `explanation_length` efectivo `= short` | `chunk_explanation = True` | `False` | No se trocea lo que ya es breve |
| — | `mode = SOCRATIC` | — | se respeta entero | Preguntar mucho es coherente con el fondo socrático |
| — | `mode = EXPLAIN` sin estilo en conflicto | — | se respeta entero | No hay contradicción que arbitrar |

Las reglas 1–3 comparten condición a propósito: `SEQUENCE` es "empezar por la base", que
pedagógicamente **es** andamiaje aunque el modo nominal sea otro.

La regla 6 se evalúa **después** de las demás: depende del `explanation_length` ya arbitrado, no del
que pidió la política.

### El arbitraje deja rastro

`compose_plan()` no solo devuelve los parámetros efectivos: devuelve la lista de **vetos aplicados**
(`parámetro`, `de`, `a`, `motivo`). Dos razones:

1. **Depuración.** Cuando se apague el modo sombra, la pregunta será "¿por qué respondió así?", y la
   respuesta está en qué pidió la política y qué sobrevivió al fondo.
2. **Explicabilidad al estudiante** (fase 3 del plan de experiencia pedagógica): *"no acorté la
   explicación porque estábamos construyendo la base"* es exactamente la frase que hace legible la
   adaptación.

### Lo que esto NO hace

- **No toca la decisión pedagógica.** El arbitraje solo puede recortar la forma; jamás cambia modo,
  dificultad ni foco. El fondo es soberano.
- **No inventa parámetros.** Si la política no pidió nada, no hay nada que arbitrar.
- **No resuelve conflictos entre señales**: eso es la Decisión 1, y ocurre antes, dentro de la
  política.

---

## Modo sombra

`ADAPT_SHADOW_MODE=true` (por defecto) computa y persiste señales y parámetros **sin** inyectar
el fragmento en el prompt. Permite acumular evidencia y validar la política antes de que afecte
a estudiantes reales. Se apaga cuando la política esté calibrada.

## Consecuencias

- La adaptación es determinista y auditable: dado un perfil, los parámetros son reproducibles.
- Streaming y no-streaming producen la misma adaptación prompt-shaping. No hay split-brain.
- Un parámetro nuevo obliga a: fila en la tabla de precedencia, familia declarada y cutoff
  nombrado. El coste de añadir señales sin pensar sube a propósito.
