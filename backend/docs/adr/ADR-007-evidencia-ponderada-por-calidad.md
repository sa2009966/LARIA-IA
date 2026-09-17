# ADR-007: La evidencia se pesa por su calidad — preguntar no es fallar

- **Estado:** Aceptado
- **Fecha:** 2026-09-17
- **Rama de origen:** `feature/backend`
- **Decisores:** Equipo LARIA (orquestación backend)
- **Depende de:** [ADR-006](ADR-006-oferta-vs-bloqueo.md) (oferta en vez de bloqueo), [ADR-005](ADR-005-grafo-prerrequisitos-curado.md)

## Contexto

El ADR-006 cerró la fase 1 del plan de experiencia pedagógica: la ausencia de dato dejó de ser
evidencia de ignorancia. El test que lo blinda usa un perfil vacío y una pregunta neutra, y pasa.

Pero el turno real no llega con el perfil vacío. `AnalyzeDocumentService.prepare_pedagogy` detecta la
señal de la pregunta y aplica `record_ask_struggle()` **en memoria antes** de decidir. Con eso, la
misma pregunta cambiaba de trato según cómo estuviera redactada:

```
"¿qué son las matrices?"                           → explain / medium
"no sé nada de ecuaciones, ¿qué son las matrices?" → scaffold / easy
                                                     foco: algebra.equals-as-operation
```

El auto-reporte creaba una entrada en `mastery_by_concept` con `mastery = 0.10` —porque la primera
evidencia fijaba el mastery al ratio— y a partir de ahí:

1. El concepto contaba como **medido**: `_measured_mastery` y `DifficultyCalculator` solo comprobaban
   `c in profile.mastery_by_concept`. Con `concept_m < 0.4` el motor forzaba `SCAFFOLD`/`EASY`.
   `struggle_signals > 0` también volvía "medido" el documento, así que una señal bastaba.
2. `ratio < 0.5` empujaba el concepto a `frequent_errors` **y** a `frequent_misconceptions`.
3. `MisconceptionResolver` indexaba por `anchor_concept`, así que `ecuación` resolvía a
   `algebra.equals-as-operation`: el prompt afirmaba un malentendido concreto que nadie observó, y
   `mapped_focus` —máxima precedencia— sacaba del foco el tema preguntado.
4. Como `focus[0]` era entonces un id del catálogo y no un nodo del grafo, `PrerequisiteGate` no
   encontraba prerrequisitos y devolvía `PROCEED`: **cualquier malentendido en memoria apagaba el
   gate**, justo para quien más evidencia de hueco tenía.
5. Dos preguntas alcanzaban `evidence_count >= min_evidence_for_gap` y `error_streak >= 2`, es decir
   `SEQUENCE`: el bloqueo que el ADR-006 acababa de retirar volvía por la puerta del chat.

El sistema castigaba la honestidad. Avisar "no sé nada de esto" era la forma más rápida de que LARIA
te tratara como deficiente, sin un solo ítem calificado en contra.

## Decisión

**La evidencia no se cuenta: se pesa por su calidad.** Un auto-reporte informa, pero no mide.

1. `EvidenceSample.is_weak_evidence`: débil por flag (`is_weak`, chat) **o por clase**
   (`ASK_STRUGGLE`, `HELP_REQUEST`, `HIGH_LATENCY`). La clase manda sobre el flag, para que no dependa
   de que cada call site se acuerde.
2. `ConceptMastery` cuenta `weak_evidence_count` aparte y expone `weighted_evidence =`
   `measured + WEAK_EVIDENCE_WEIGHT × weak`, con `WEAK_EVIDENCE_WEIGHT = 0.5`: **dos auto-reportes
   pesan lo que un ítem fallado.**
3. Dos umbrales sobre esa misma magnitud, ambos hipótesis nombradas como los cutoffs del ADR-004:
   - `MIN_EVIDENCE_FOR_DECISION = 1.0` — lo que un concepto necesita para mover modo/dificultad.
     Consulta única: `StudentProfile.has_decision_evidence()`.
   - `min_evidence_for_gap = 2.0` (ya existía) — lo que necesita para ser un hueco en el gate.
4. La evidencia débil **no escribe el expediente**: ni `frequent_errors` ni
   `frequent_misconceptions`. Ese canal queda para lo calificado.
5. `MisconceptionResolver` resuelve por id y alias, **nunca por ancla**. El nombre de un concepto no
   es un diagnóstico; sin match va a `unmapped_memory` y sirve de foco sin inventar nada.
6. El gate se evalúa sobre el primer concepto del foco que **no** sea un id del catálogo.
7. `doc_measured` exige `attempts > 0`: las señales de struggle son auto-reporte, no medición.

### Lo que esto NO cambia

- **La conversación sigue pudiendo llegar a `SEQUENCE`** (decisión 5 del ADR-006): cuatro señales
  débiles pesan 2.0. Lo que ya no alcanza son dos.
- **La conversación sigue subiendo el mastery** (fase 2): `record_conversational_success` era ya
  `is_weak`; ahora además no pretende ser una medición.
- **El andamiaje medido sigue intacto**: un quiz flojo sigue dando `SCAFFOLD`/`EASY` al primer intento.
- **El registro sí se adapta al auto-reporte**: el estilo cognitivo lo lee de la pregunta. Cambia
  *cómo* se explica, no *cuánto* se asume que el alumno puede.

## Consecuencias

- Un auto-reporte deja el turno en `EXPLAIN`/`MEDIUM` y responde lo preguntado. Dos sobre el mismo
  concepto sí bajan el nivel: es escalada con evidencia, no con redacción.
- `GET /learning/me/profile` dejará de mostrar como "errores frecuentes" conceptos que el alumno solo
  preguntó. Es la corrección del dato, no una pérdida.
- El gate vuelve a existir para alumnos con malentendidos mapeados.
- Tres tests que fijaban el comportamiento anterior se actualizaron con la razón en el propio test
  (`test_learning_signals`, `test_misconception_catalog`, `test_analyze_document_service`).
  `tests/unit/domain/test_evidencia_ponderada.py` blinda lo nuevo.

## Deuda que esto abre

**Perfiles Mongo anteriores no distinguen.** `weak_evidence_count` no existía, así que su evidencia de
auto-reporte quedó contada como calificada y sigue pesando doble hasta que el concepto reciba
evidencia nueva. Se asume `0` al deserializar. Corregirlo exige recomputar historia que no se guardó;
la alternativa honesta es dejar que el uso lo diluya. Como la deuda #1 del plan, es una acción
deliberada sobre datos de producción.

## Fuera de alcance

- **Que la pregunta lidere el foco** (deuda #3 del plan, primer punto de la fase 3). Sigue abierto:
  con el diagnóstico inventado fuera, el foco lo lidera `frequent_errors` → `weakest_concepts` →
  conceptos del documento, y un concepto que el alumno solo mencionó puede quedar por delante del
  tema preguntado. Es decisión de producto.
- **`pace` pegado en `slow`** por `record_ask_struggle`, recalculado solo en quizzes.
- **`CognitiveStyleSelector` nunca recibe `signal`** desde el motor: el mapeo NOVICE/CONFUSION → SIMPLE
  y HELP → STEP_BY_STEP es código muerto en ese path.
- **Identidad de conceptos sin materia**: `desigualdades` (álgebra) canonicaliza a
  `desigualdad social`.
