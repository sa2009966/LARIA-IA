# Plan de integración — Experiencia pedagógica

> **Objetivo:** que el alumno sienta que el sistema se adapta a su forma de aprender y que lo guía un
> agente, no que lo evalúa un examinador. Al escribirse este plan esta capa estaba en ~30%: la más
> deficiente del sistema y la única que decide si el producto enseña.
>
> **Estado:** fases 1 y 2 hechas ([ADR-006](adr/ADR-006-oferta-vs-bloqueo.md)); fases 3 y 4 pendientes.
>
> Depende de: [ADR-004](adr/ADR-004-adaptacion-por-senales.md) (core adaptativo, shadow mode) y
> [ADR-005](adr/ADR-005-grafo-prerrequisitos-curado.md) (grafo curado). Precede al P0 de control-flow.

---

## Diagnóstico raíz

**El sistema modela al alumno como un déficit, no como una trayectoria.** No es un problema de tono ni
de redacción de prompts: es una asimetría estructural. Todos los caminos que empeoran el perfil están
cableados; todos los que lo mejoran son inalcanzables.

El diagnóstico de abajo es el estado **antes** de las fases 1 y 2; se conserva porque es la
justificación del plan y el punto de comparación.

| Camino | Estado antes de este plan |
|---|---|
| `record_ask_struggle` (negativo) | ✅ cableado — servicio y projector |
| `record_high_latency` (negativo) | ✅ cableado |
| `error_streak` / `incorrect_streak` | ✅ cableado |
| Gate de prerrequisitos que **bloquea** | ✅ cableado, sin umbral de evidencia |
| `EvidenceKind.SUCCESS` | ❌ **nadie lo emite** |
| Envelope `celebration` | ❌ **inalcanzable**: ningún modo mapea a él |
| `AffectState.CELEBRATORY` | ❌ **inalcanzable**: nadie pasa `last_score_ratio` |
| `remember_example` / `remember_analogy` | ❌ **nunca se llaman** (y su salida se expone por API) |
| `mastered_concepts` en el turno del tutor | ❌ solo alimenta métricas |
| Explicarle al alumno *por qué* cambió el enfoque | ❌ no existe |

Consecuencia medida con el código real: un alumno **nuevo** que pregunta *"¿qué son las matrices?"*
recibe `blocked=True`, dificultad `easy`, foco desviado a `variable`, y el modelo recibe la orden
*"No expliques el tema avanzado completo"* más un expediente de ceros. Preguntó y obtuvo una
no-respuesta más un "no estás listo" implícito, con **cero evidencia** en su contra.

Y ya hay un componente que implementa el principio correcto: `DifficultyCalculator.from_profile`
devuelve `MEDIUM` cuando no hay perfil — trata lo desconocido como medio, no como cero. El
`PedagogicalEngine` lo **sobrescribe** a `EASY` en cuanto `concept_m < 0.4`, y `concept_m` de un
alumno nuevo es 0.0 por ausencia de dato, no por fallo.

---

## Principios de diseño

Cinco principios, cada uno con el cambio de código que implica. No son adornos: son la especificación.

### P1. Ante incertidumbre, apostar alto — no bajo

*Zona de desarrollo próximo (Vygotsky):* se enseña en el borde de lo que el alumno puede hacer con
apoyo, no en el suelo. Bajar a `EASY` por falta de datos deja al alumno por debajo de su zona: además
de insultante, es aburrido, y no genera información.

**Implica:** distinguir `mastery=0.0 por ausencia de evidencia` de `mastery=0.0 medido`. Ya tienes el
dato para hacerlo (`ConceptMastery.evidence_count`, `confidence`, `Signal.samples`). Con evidencia
fina, decidir por la cota **alta** del estimado y dejar que la respuesta del alumno revele la verdad.

### P2. Ofrecer, no bloquear

*Autonomía (autodeterminación):* el bloqueo elimina la agencia; la oferta la preserva y consigue la
misma pedagogía. *Fracaso productivo (Kapur):* dejar intentar antes de instruir enseña más que
andamiar preventivamente — y el intento **es** la evidencia que hoy falta.

**Implica:** el gate deja de desviar el foco en silencio. Con hueco detectado, el turno responde lo
que se preguntó y ofrece la base: *"te lo explico; si quieres, antes repasamos qué es una variable"*.
Quien elige seguir da evidencia; quien elige repasar recibe el andamiaje **y lo eligió**.

### P3. La conversación tiene que poder subir el mastery

Hoy solo un quiz genera evidencia positiva. Si tu forma de aprender es conversar, el sistema la lee
como fracaso: cuanto más usas el tutor, más deficiente pareces.

**Implica:** emitir `EvidenceKind.SUCCESS` desde el chat. La señal ya existe y se está desperdiciando:
`SELF_CORRECTION` (*"ah claro, ya entendí"*) hoy **solo** sube la tasa de preguntas socráticas, cuando
es evidencia directa de aprendizaje. Añadir además la pregunta de verificación cuya respuesta puntúa
(*interrogación elaborativa*): enseña y mide en el mismo turno.

### P4. Hacer visible lo logrado

*Autoeficacia (Bandura):* la creencia "puedo con esto" predice la persistencia mejor que la habilidad,
y su fuente principal son las experiencias de dominio **vistas como tales**. El sistema nunca le dice
al alumno qué ya domina, aunque lo sabe (`mastered_concepts`).

**Implica:** cablear el canal positivo que ya existe y está muerto: `celebration` en el envelope,
`CELEBRATORY` en el afecto, y anclar la explicación en lo que el alumno ya domina
(*"esto se apoya en X, que ya manejas"*). Eso es andamiaje y reconocimiento a la vez.

### P5. Decir por qué

La adaptación que no se explica es indistinguible de la arbitrariedad — o de un juicio. Decir *"te doy
más ejemplos porque te funcionaron en los últimos temas"* convierte la adaptación en colaboración y
desarrolla metacognición.

**Implica:** la feature #4 del roadmap (explicabilidad) sube de prioridad: no es una capa de
presentación opcional, es lo que hace legible todo lo demás. Es barata: las señales y bandas ya están.

---

## Fases

### Fase 1 — Dejar de tratar lo desconocido como deficiente — ✅ hecha

1. Umbral de evidencia en `PrerequisiteGate`: un hueco exige evidencia **positiva** de fallo
   (`evidence_count >= N` y mastery bajo), no ausencia de registro. Coherente con el
   `min_samples_for_adaptation` del ADR-004: hoy la intervención más invasiva del sistema es la que
   menos evidencia exige.
2. `PedagogicalEngine` deja de sobrescribir a `EASY` cuando el mastery bajo viene de ausencia de dato.
   Respetar el `MEDIUM` que ya devuelve `DifficultyCalculator`.
3. Quitar el lenguaje de déficit del prompt: el `evidence_summary` crudo
   (`doc_mastery=0.00; confidence=0.00; ...`) sale del system prompt. El modelo no necesita el
   expediente para elegir registro; necesita la decisión.
4. `anti_spoiler` deja de ser `True` incondicional: tiene sentido ante intención de examen, no cuando
   el alumno solo quiere entender algo.

**Cerrado cuando:** un alumno nuevo que pregunta por un tema avanzado recibe una respuesta a **su**
pregunta, con dificultad media, y ningún texto que presuponga que no domina nada. Test que lo blinda:
perfil vacío + tema avanzado ⇒ `blocked=False` y `focus_concepts[0]` es el tema preguntado.

### Fase 2 — Cerrar el lazo positivo — ✅ hecha

1. `EvidenceKind.SUCCESS` emitido desde el turno de tutoría: `SELF_CORRECTION` detectado ⇒ evidencia
   positiva sobre los conceptos en foco.
2. Pregunta de verificación cuya respuesta puntúa: cierra el lazo y genera mastery conversacional.
3. Gate de prerrequisitos como **oferta** (P2), con la elección del alumno registrada como evidencia.
4. `remember_example` / `remember_analogy` conectados: lo que funcionó se guarda y se reutiliza. Hoy se
   persiste y se expone por API un campo que nadie llena.

**Cerrado cuando:** una sesión de solo conversación, sin ningún quiz, puede **subir** el mastery de un
concepto. Test: N turnos con autocorrección ⇒ `effective_concept_mastery` mayor que al inicio.

> Cerrada en [ADR-006](adr/ADR-006-oferta-vs-bloqueo.md). Los puntos 1-3 están hechos; el punto 4
> (capturar el texto del ejemplo o la analogía que funcionó) queda fuera: exige que el LLM etiquete su
> propia salida. Lo que sí se corrigió es que la memoria de estrategia y estilo solo se escriba ante
> evidencia positiva.
>
> **Correcciones que salieron de la auditoría adversarial** (ver Decisión 5 del ADR-006): la evidencia
> conversacional es débil y no puede certificar un concepto de un mensaje; una racha de error se
> descuenta pero no se borra; la dificultad repetida en el chat también alimenta `error_streak`, sin lo
> cual `SEQUENCE` era inalcanzable conversando; y los campos del evento deben viajar en el outbox, sin
> lo cual toda la fase estaba muerta solo en producción.

### Fase 3 — Hacer visible el progreso y el por qué — pendiente

**Hallazgo que redefine esta fase.** La precedencia del foco en `PedagogicalEngine.select()` es
`misconceptions → errores → débiles → conceptos del documento`: **la pregunta del estudiante no entra**
(solo se usa para elegir el estilo). Así que preguntar por derivadas con fallos previos en funciones
produce un prompt que se autocontradice: `Foco conceptual: funciones` junto a "el tema de la respuesta
sigue siendo el que preguntó", y la remediación inyectada puede nombrar un concepto con cero
evidencia mientras el hueco medido no se menciona. El invariante "nunca se desvía el foco en silencio"
se cumple en el gate pero **no** de punta a punta. Decidir si el tema preguntado debe liderar el foco
es producto, no implementación, y es el primer punto de esta fase.

1. `celebration` alcanzable: `envelope_type_for_mode` o el servicio lo emiten ante hito real
   (concepto que cruza a dominado, racha de aciertos, desbloqueo de prerrequisito).
2. `CELEBRATORY` alcanzable: pasar `last_score_ratio` a `AffectPolicy` en el turno de chat.
3. Anclar en lo que ya domina: `mastered_concepts` entra en la decisión y en el prompt.
4. Explicabilidad (#4): derivar de `AdaptationParameters` + señales que lo dispararon una frase en
   lenguaje natural, y exponerla en el envelope para que la UI la muestre.

**Cerrado cuando:** el alumno puede ver, en el envelope, qué logró y por qué el tutor le está hablando
así. Test: hito ⇒ envelope `celebration`; adaptación activa ⇒ payload con su explicación.

### Fase 4 — Recién aquí, control-flow y apagado de shadow — pendiente

El P0 original (`chunk_explanation`, `practice_before_advance`) y el apagado de `ADAPT_SHADOW_MODE`.
Van al final a propósito: afinan la **forma** de la respuesta, y no tiene sentido afinar la forma de un
mensaje que parte de un diagnóstico injusto. Con las fases 1-3 hechas, control-flow sí mueve la sesión.

---

## No ahora

- **Learning Path**: tiene `LearningModule.mastery`, `record_mastery()` y su propio
  `_unlock_dependents()` con puertas de prerrequisito. Sería una segunda verdad de mastery **y** una
  segunda verdad de prerrequisitos, justo lo que ADR-005 acaba de consolidar.
- **Repetición espaciada, misconceptions, dashboard docente**: ninguna cambia cómo se siente el alumno
  en el turno. Después de la fase 3.
- **STT, RAG, scraping**: sin relación con este objetivo.

## Deuda conocida al cerrar las fases 1 y 2

Tres cosas medidas y no resueltas, por orden de coste:

1. **Perfiles Mongo anteriores conservan `preferred_explanation_style: "simple"` persistido.** Cambiar
   el default del dataclass no migra documentos ya escritos, así que la base instalada sigue con el
   estilo congelado que la fase 2 arregla para los perfiles nuevos. Es un `updateMany` que vacíe ese
   campo; es acción sobre datos de producción y se ejecuta a mano, deliberadamente.
2. **El estilo efectivo se fija con una sola muestra.** `set_preferred_style` es una asignación dura,
   sin conteo ni EWMA: un único match de regex fija el estilo del estudiante y a partir de ahí
   cortocircuita las heurísticas. El arreglo honesto exige estado persistido nuevo (éxitos por estilo)
   y toca los repositorios.
3. **El foco se decide por las debilidades, no por la pregunta** — ver Fase 3.

## Decisiones que no son técnicas

Tres puntos que definen producto, no implementación:

1. **¿Oferta o bloqueo?** La fase 2 propone que el alumno pueda elegir avanzar sin la base. Gana
   autonomía y evidencia; pierde la garantía de secuencia curricular.
2. **¿Qué cuenta como hito celebrable?** Celebrar de más quema el canal y se vuelve ruido.
3. **¿Cuánta evidencia exige un hueco?** Es el equivalente pedagógico de
   `min_samples_for_adaptation`, y fija cuán rápido el sistema se atreve a intervenir.
