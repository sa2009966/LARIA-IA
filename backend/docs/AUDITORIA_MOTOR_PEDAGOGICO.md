# Auditoría del Motor Pedagógico de LARIA — Backend

> Fecha: 2026-08-15  
> Fuente: código fuente rama `feature/backend` (`backend/src/`)  
> Principio rector: **el LLM solo genera lenguaje; toda decisión pedagógica pertenece al dominio.**

---

## 1. Resumen ejecutivo

LARIA-IA implementa un **tutor inteligente adaptativo** sobre una arquitectura hexagonal/DDD con Python/FastAPI. El motor pedagógico decide *qué* enseñar, a qué dificultad, con qué estilo cognitivo y si bloquear avanzar por prerrequisitos. El dominio acumula evidencia del estudiante (quizzes + interacciones tutor) en `StudentProfile`, un agregado con `mastery_by_concept`, `mastery_by_document`, `PedagogicalMemory` y métricas operativas (pace, velocity, struggle).

**Fortaleza central:** la separación entre "evidencia" (hechos observables) y "pedagogía" (decisión sobre qué hacer con esa evidencia) es limpia y testeable. El dominio es puro; la IA es un cliente.

**Debilidad estructural:** el perfil cognitivo se construye *después* de la experiencia (proyector reactivo), no antes. La toma de decisiones en caliente usa una versión del perfil que puede no reflejar la sesión recién iniciada con precisión. Además, el catálogo de prerrequisitos es un grafo estático de ~23 nodos (álgebra/cálculo/física) con aliases hardcodeados; cualquier expansión curricular requiere editar código.

---

## 2. Diagrama del flujo de evaluación

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         FLUJO DE EVALUACIÓN DEL ESTUDIANTE                  │
└─────────────────────────────────────────────────────────────────────────────┘

  ESTUDIANTE
     │
     ├── (1) SUBE DOCUMENTO ──► DocumentUploadedEvent ──► [sin efecto en perfil]
     │                                              (solo auditoría de documento)
     │
     ├── (2) ANALIZA DOCUMENTO ──► LlmGate.analyze() ──► OpenAI → AnalysisResult
     │                         (caché por hash de contenido, 7 días)
     │                         Resultado embebido en DocumentAggregate.analysis_result
     │                         (key_concepts, summary, suggested_questions, confidence)
     │
     ├── (3) PIDE AL TUTOR ──► AnalyzeDocumentService.answer_question_with_pedagogy()
     │      │                    │
     │      │                    ├── LearningSignalDetector.detect(pregunta)
     │      │                    │   → signal.kind (NOVICE/CONFUSION/HELP/NONE)
     │      │                    │   + conceptos extraídos por regex
     │      │                    │
     │      │                    ├── profile.record_ask_struggle() [in-mem]
     │      │                    │   (solo para decisión; persistencia via evento)
     │      │                    │
     │      │                    ├── PedagogicalEngine.select(profile, doc, intent)
     │      │                    │   ├── PrerequisiteGate.evaluate(foco)
     │      │                    │   │   └── PrerequisiteGraph.all_prerequisites()
     │      │                    │   │       └── DFS topológico sobre _DEFAULT_EDGES
     │      │                    │   ├── weakest_concepts(effective=true)
     │      │                    │   ├── CognitiveStyleSelector.select()
     │      │                    │   ├── DifficultyCalculator.from_profile()
     │      │                    │   └── → PedagogicalDecision (modo, dificultad, foco)
     │      │                    │
     │      │                    ├── ContextSelector.select(doc, focus) ──► contexto acotado
     │      │                    │
     │      │                    ├── ModelRouter.select(task=ASK, decision)
     │      │                    │   └── mini o strong según modo+dificultad+struggle
     │      │                    │
     │      │                    └── LlmGate.answer_question(ctx, q, decision)
     │      │                        ├── TutorPolicy.answer_question(decision) ──► prompt
     │      │                        │   └── _MODE_INSTRUCTIONS[mode] + _STYLE_INSTRUCTIONS[style]
     │      │                        ├── caché de prompt/respuesta (1h)
     │      │                        └── OpenAI → texto
     │      │
     │      └── TutorQuestionAskedEvent ──► [outbox si producción] / [memory si dev]
     │              │
     │              └── LearningEvidenceProjector.handle_tutor_question()
     │                  ├── profile.record_ask_struggle() [persist]  ← evita double-count con in-mem
     │                  ├── profile.pedagogical_memory.remember_strategy(mode)
     │                  ├── profile.pedagogical_memory.set_preferred_style(style)
     │                  ├── StudentProfileRepository.save()  (optimista, version)
     │                  └── metrics: profile_updates, laria_struggle_signals
     │
     ├── (4) QUIZ ──► QuizService.generate()
     │               ├── PedagogicalEngine.select(intent=QUIZ, profile, session)
     │               ├── LlmGate.generate_quiz(document, n, decision)
     │               │   ├── reuso de quiz si tags coinciden con focus (5 max)
     │               │   ├── caché por focus_hash (24h)
     │               │   └── OpenAI → JSON preguntas
     │               ├── ensure_quiz_quality() → rebalanceo de claves (anti-A bias)
     │               ├── ConceptTagger.tag_questions() (keyword + document_concepts)
     │               └── QuizAggregate.create() → QuizGeneratedEvent
     │
     │               └── ESTUDIANTE RESPONDE ──► QuizService.submit_attempt()
     │                   ├── quiz.grade(answers) ──► QuizGrade(per_question_correct, score, total)
     │                   ├── QuizAttemptAggregate.create() → QuizAttemptCompletedEvent
     │                   │
     │                   └── QuizAttemptCompletedEvent ──► LearningEvidenceProjector
     │                       ├── ConceptTagger.tag_question() por pregunta
     │                       ├── profile.record_quiz_result(doc_id, score, missed, concept_results)
     │                       │   ├── DocumentMastery.apply_result() [EMA alpha=0.4]
     │                       │   ├── ConceptMastery.apply_evidence() [multi-señal]
     │                       │   ├── _push_errors(missed) → frequent_errors
     │                       │   └── pedagogical_memory.remember_misconception(missed)
     │                       ├── TutorInteractionAggregate.create() → guardado
     │                       ├── StudentProfileRepository.save() (optimista)
     │                       └── metrics: profile_updates, laria_quiz_attempts, laria_quiz_score_ratio
     │
     └── (5) RECOMENDACIÓN / PERFIL ──► LearningQueryService.get_learning_history()
                                       ├── intentos + interacciones (repos)
                                       ├── RecommendationEngine.build(profile)
                                       │   ├── forgotten_concepts (gap Ebbinghaus)
                                       │   ├── pending (intentos≤1, mastery<0.6)
                                       │   ├── review_priority (weakest, con bloqueo)
                                       │   ├── next_topic (sucesores en PrerequisiteGraph)
                                       │   ├── mastered
                                       │   └── document-level fallback (review/challenge)
                                       ├── get_profile() → StudentProfileDTO
                                       │   ├── mastery_by_document, mastery_by_concept
                                       │   ├── effective_mastery (con decaimiento)
                                       │   ├── confidence, learning_velocity, pace
                                       │   └── pedagogical_memory
                                       └── GET /api/v1/learning/me, /api/v1/learning/me/profile
```

---

## 3. Responsabilidad de cada servicio

### 3.1 `StudentProfile` (aggregate, `domain/aggregates/student_profile.py` — 504 lns)

| Responsabilidad | Método clave |
|----------------|--------------|
| Almacenar mastery por concepto y documento | `mastery_by_concept: dict[str, ConceptMastery]`, `mastery_by_document: dict[UUID, DocumentMastery]` |
| Recibir evidencia de quiz | `record_quiz_result()` → delega a `ConceptMastery.apply_evidence()` |
| Recibir evidencia de ask | `record_ask_struggle()`, `record_high_latency()` |
| Calcular mastery con olvido | `ConceptMastery.effective_mastery()` — Ebbinghaus, half_life configurable |
| Detectar conceptos débiles | `weakest_concepts()`, `forgotten_concepts()`, `mastered_concepts()` |
| Rastrear errores frecuentes | `_push_errors()` → `frequent_errors[:20]` |
| Actualizar pace | `_update_pace()` (slow/steady/fast basado en velocity y weak vs strong) |
| Memoria pedagógica | `PedagogicalMemory` (misconceptions, ejemplos, analogías, estilo, estrategias) |

### 3.2 `PedagogicalEngine` (domain/services/pedagogical_engine.py — 225 lns)

| Responsabilidad | Qué produce |
|----------------|-------------|
| Seleccionar modo pedagógico | `PedagogicalMode` (EXPLAIN/SOCRATIC/SCAFFOLD/PRACTICE) según `concept_m` y paso de sesión |
| Seleccionar dificultad | `DifficultyCalculator.from_profile()` → `Difficulty` |
| Seleccionar estilo cognitivo | `CognitiveStyleSelector.select()` → `CognitiveStyle` |
| Evaluar prerrequisitos | `PrerequisiteGate.evaluate()` → `GateResult(blocked, remediation_focus)` |
| Resolver misconceptions | `MisconceptionResolver` → `MisconceptionEntry` del catálogo |
| Priorizar foco | mapped_focus > errors > weak > unmapped_memory > doc_focus |
| Producir decisión | `PedagogicalDecision` (modo, dificultad, foco, anti_spoiler, objective, evidence_summary) |

### 3.3 `LearningEvidenceProjector` (application/services/learning_evidence_projector.py — 182 lns)

| Responsabilidad | Qué hace |
|----------------|----------|
| Suscribirse a eventos | `register()` → `QuizAttemptCompletedEvent`, `TutorQuestionAskedEvent` |
| Proyectar ask → perfil | `handle_tutor_question()`: `record_ask_struggle`, set_preferred_style, remember_strategy |
| Proyectar quiz → perfil | `handle_quiz_attempt()`: `record_quiz_result` con tagged conceptos, missed concepts |
| Persistir perfil | `StudentProfileRepository.save()` con dedup (`was_event_applied` + versionado optimista) |
| Métricas | `profile_updates`, `laria_struggle_signals`, `laria_high_latency`, `laria_concepts_weak`, `laria_concepts_mastered` |

### 3.4 `DifficultyCalculator` (domain/services/difficulty_calculator.py — 77 lns)

| Responsabilidad | Algoritmo |
|----------------|-----------|
| Calcular `DifficultySignals` | `effective_mastery = min(masteries de foco)`, `confidence = avg(confidences)`, `err_rate`, `learning_velocity`, `pace` |
| Mapear a nivel | score = effective_mastery; -0.15×(1-conf); -0.2×err_rate; +0.1×velocity; pace ±0.1 |
| Umbrales | < 0.38 → EASY; < 0.72 → MEDIUM; ≥ 0.72 → HARD |

### 3.5 `RecommendationEngine` (domain/services/recommendation_engine.py — 213 lns)

| Responsabilidad | Qué genera |
|----------------|-----------|
| Recomendaciones | hasta 10 `LearningRecommendation` priorizadas por `priority` |
| forgotten | gap Ebbinghaus → `priority = 0.9 + gap`, minutos `10 + 20×gap` |
| pending | intentos ≤ 1 y mastery < 0.6 → `priority = 0.75` |
| review_priority | weakest efectivo con `priority = (1 - mastery) × (1.1 - 0.3×conf) × blocker` |
| next_topic | sucesores de PrerequisiteGraph desbloqueados con mastery < 0.7 |
| mastered | mastery ≥ 0.8 y confidence ≥ 0.55 → `priority = 0.2` |
| Document-level | doc mastery < 0.4 → review; < 0.7 → guided_explain; ≥ 0.7 → challenge |
| study_time | agrega ~total_min de los top-3 |

### 3.6 `PrerequisiteGraph` / `PrerequisiteGate` (domain/services/prerequisite_graph.py — 174 lns)

| Responsabilidad | Qué hace |
|----------------|----------|
| Grafo curricular | `_DEFAULT_EDGES`: ~23 nodos (variable → expresión → ecuación → sistemas → matrices; funciones → derivadas → integrales; mru → cinemática → dinámica) |
| Resolver prerrequisitos | `all_prerequisites()` — DFS topológico inverso |
| Sucesores | `successors_of()` — inverso de `prerequisites_of` |
| Extensión por documento | `extend_with_document_concepts()` — heurística de orden lineal débil |
| Gate | `PrerequisiteGate.evaluate()` — bloquea si mastery efectivo < 0.45 en algún prerrequisito; devuelve `remediation_focus` (primeros 4 faltantes) |

### 3.7 `CognitiveStyleSelector` (domain/services/cognitive_style.py — 61 lns)

| Responsabilidad | Qué usa |
|----------------|---------|
| Detectar estilo de la pregunta | regex en texto: paso a paso → STEP_BY_STEP, analogía → ANALOGY, visual → VISUAL, fórmula → MATHEMATICAL, técnico → TECHNICAL, simple → SIMPLE |
| Señales de aprendizaje | NOVICE/CONFUSION → SIMPLE; HELP → STEP_BY_STEP |
| Perfil | preferred_explanation_style; pace slow/struggle≥3 → STEP_BY_STEP; pace fast/attempts≥4 → TECHNICAL |
| Default | SIMPLE |

### 3.8 `MisconceptionResolver` + `MisconceptionCatalog` (domain/services/misconception_resolver.py + catalog/misconception_catalog.py)

| Responsabilidad | Qué hace |
|----------------|----------|
| Catálogo | 8 misconceptions de álgebra (variable-as-label, adding-unlike-terms, like-terms-drop-variable, distributive-partial, equals-as-operation, moving-terms-wrong-sign, cross-multiply-always, inequality-flip) |
| Match | `MisconceptionResolver.resolve_entry(label)` → id/alias/anchor → `MisconceptionEntry` |
| Uso en PedagogicalEngine | mapped_focus incluye misconception.id + anchor_concept; objective incluye `remediation_strategy` |

### 3.9 `LlmGate` (application/services/llm_gate.py — 297 lns) — *referencia: NO decide pedagogía*

| Responsabilidad | Qué hace (solo economía) |
|----------------|--------------------------|
| Caché | analyze: 7 días por hash de contenido; ask: 1h por hash de prompt+modelo; quiz: 24h por focus_hash |
| Reuso de quizzes | Busca quiz del mismo doc con tags en focus (5 max) |
| Selección de modelo | ModelRouter: mini por defecto, gpt-4o solo para SOCRATIC+HARD o struggle≥3 |
| Métricas | `laria_llm_latency_ms`, `laria_llm_calls`, `laria_cache_hit`, `laria_llm_skipped` |
| Invalidación | `invalidate_document()` → borra cache de análisis y quizzes del doc |

### 3.10 Otros servicios de dominio relevantes

| Servicio | Responsabilidad |
|----------|----------------|
| `TutorPolicy` | Compone prompts del LLM a partir de `PedagogicalDecision` (sistema + usuario). `_MODE_INSTRUCTIONS` y `_STYLE_INSTRUCTIONS` son los únicos textos pedagógicos versionados (`POLICY_VERSION = "v2"`). |
| `QuizQuality` | Validación y reequilibrio determinista de claves de respuesta (anti-sesgo A). `rebalance_answer_keys()` rota opciones. |
| `ConceptTagger` | Heurística keyword → concept_tags en preguntas de quiz (sin LLM). ~15 patrones regex. |
| `ContextSelector` | Recorta documento a summary + key_concepts + párrafos que contengan foco (max 2500 chars). |
| `ModelRouter` | Selecciona modelo OpenAI según task + decisión + struggle_signals. |
| `LearningSignalDetector` | Regex en pregunta → NOVICE/CONFUSION/HELP con strength 0.9/0.75/0.45 + conceptos extraídos. |
| `TutorSession` | Máquina de estados multi-turno: INTRODUCE → HINT (tras ask) → PRACTICE (tras ≥2 hints) → CHECK. |

---

## 4. Variables almacenadas

### 4.1 En `StudentProfile` (`student_profiles` colección MongoDB)

```
{
  "_id": UUID,                    // = student_id
  "student_id": UUID,
  "mastery_by_document": {        // clave: str(document_id)
    "<doc_id>": {
      "document_id": UUID,
      "attempts": int,
      "mastery": float,           // EMA alpha=0.4
      "last_score_ratio": float,
      "incorrect_streak": int,
      "struggle_signals": int
    }
  },
  "mastery_by_concept": {         // clave: concept_key (canonicalizado)
    "<concept>": {
      "concept_key": str,
      "attempts": int,
      "mastery": float,
      "last_score_ratio": float,
      "document_ids": [UUID],
      "confidence": float,        // 0..1, delta +0.08×w / -0.096×w
      "last_practiced_at": datetime,
      "help_requests": int,
      "latency_ms_ema": float,    // EMA 0.3×lat + 0.7×ema
      "error_streak": int,
      "subject": str | null,
      "evidence_count": int,
      "half_life_days": float     // default 14
    }
  },
  "frequent_errors": [str],       // top 20 misconceptions (canonicalizadas)
  "pace": "slow"|"steady"|"fast",
  "total_attempts": int,
  "total_struggle_signals": int,
  "learning_velocity": float,     // EMA 0.3×delta + 0.7×velocity
  "applied_event_ids": [str],     // hasta 256 (dedup)
  "pedagogical_memory": {
    "frequent_misconceptions": [str],  // top 15
    "successful_examples": [str],      // top 10, truncado 240 chars
    "successful_analogies": [str],     // top 10
    "preferred_explanation_style": str, // "simple"|...
    "last_effective_strategies": [str] // top 8
  },
  "updated_at": datetime,
  "version": int                  // optimismo
}
```

### 4.2 En `DocumentAggregate` (`documents` colección)

```
{
  "_id": UUID,
  "owner_id": UUID,
  "filename": str,
  "content": str,                  // vacío si hay blob
  "content_blob_id": UUID | null,  // GridFS fs.files
  "subject": str,                  // Subject whitelist
  "status": "uploaded"|"analyzing"|"analyzed"|"error",
  "analysis_result": {             // embebido, NO colección separada
    "summary": str,
    "key_concepts": [str],
    "suggested_questions": [str],
    "confidence_score": float
  },
  "error_message": str | null,
  "uploaded_at": datetime,
  "analysis_result" → conceptos clave usados en focus de tutor/quiz
}
```

### 4.3 En `tutor_sessions` colección

```
{
  "_id": "{student_id}:{document_id}",  // compuesto único
  "id": UUID,
  "student_id": UUID,
  "document_id": UUID,
  "step": "introduce"|"hint"|"practice"|"check",
  "objective": str,
  "focus_concepts": [str],
  "hints_given": [str],              // top 10, truncado 200 chars
  "turns": int,
  "version": int                     // optimismo
}
```

### 4.4 En `event_outbox` (si `EVENT_BUS_BACKEND=outbox`)

```
{
  "_id": UUID,
  "event_type": "TutorQuestionAskedEvent"|"QuizAttemptCompletedEvent",
  "payload": { ... },
  "created_at": datetime,
  "processed_at": datetime | null,
  "attempts": int,
  "last_error": str | null
}
```

### 4.5 Variables derivadas (no persistentes, cálculo en caliente)

| Variable | Fórmula |
|----------|---------|
| `effective_mastery(concept)` | `mastery × exp(-ln2 × days / half_life) × (0.85 + 0.15×confidence)` |
| `forgetting_gap(concept)` | `stored_mastery - effective_mastery(now)` |
| `pace` | slow si velocity < -0.05 OR weak_count > strong_count; fast si velocity > 0.08 AND strong > weak AND attempts≥3; sino steady |
| `learning_velocity` | EMA 0.3×Δmastery + 0.7×velocity_prev |
| `difficulty_score` | effective_mastery - 0.15×(1-confidence) - 0.2×err_rate + 0.1×velocity + pace_bonus |
| `weakest_concepts()` | sorted por effective_mastery asc, limit 5 |

---

## 5. Puntos débiles

### 5.1 Debilidades del modelo de evaluación

**W1 — El perfil se actualiza reactivamente, no proactivamente.**  
`LearningEvidenceProjector` solo persiste el perfil cuando el evento sale del `EventBus`. En `memory` es inmediato; en `outbox` hay un `_outbox_worker_loop` con polling de 1s y batch de 25. Un estudiante que abre `/learning/me` justo después de un quiz puede ver un perfil desactualizado si el outbox no ha procesado aún el evento.  
*Impacto:* experiencia inconsistente en producción.

**W2 — Dedup de eventos con `applied_event_ids` tiene un techo.**  
`_MAX_APPLIED_EVENT_IDS = 256`. Cuando el buffer se llena, se descarta el evento más antiguo. Si un evento antiguo se re-procesa (por ejemplo, tras un `restart app` donde el outbox re-procesa todo), se aplicará de nuevo y el conteo de intentos/struggle subirá artificialamente.  
*Impacto:* mastery inflado tras reinicios si el outbox no gestiona idempotencia externamente.

**W3 — `ConceptMastery.apply_evidence` tiene alpha dinámico que puede saturar.**  
El alpha efectivo está acotado a [0.05, 0.9] y se modifica por tipo de señal. Pero HELP_REQUEST fuerza `effective_alpha = max(effective_alpha, 0.35)` y REPEATED_ERROR fuerza ≥0.5. Esto significa que **ayuda repetida** o **errores repetidos** hacen que mastery converja más rápido al ratio de la señal, sin un mecanismo de "estancamiento" o "plató".  
*Impacto:* un estudiante que pide ayuda muchas veces converge rápido a mastery baja, pero el modelo no distingue "ayuda legítima por complejidad natural" de "desorientación total".

**W4 — `effective_mastery` no diferencia entre "nunca visto" y "olvidado".**  
Si `concept_key` no existe en `mastery_by_concept`, `effective_concept_mastery()` devuelve 0.0. Pero 0.0 puede ser "nunca lo practiqué" o "lo dominé y olvidé". El sistema trata ambos igual.  
*Impacto:* `RecommendationEngine` prioriza igual un concepto nunca visto y uno olvidado, con la misma lógica de `forgotten_concepts` que requiere `forgetting_gap ≥ 0.15` (imposible si nunca existió).

**W5 — `DifficultyCalculator` usa `min(masteries)` sin ponderación.**  
Si el foco tiene 5 conceptos y 4 están en mastery 0.9 y 1 en 0.3, la dificultad se fija por el 0.3. Esto puede ser excesivamente conservador. No hay peso por importancia del concepto ni por número de intentos.  
*Impacto:* dificultad sub-óptima (demasiado fácil o demasiado difícil) cuando hay un concepto atípico en el foco.

**W6 — PrerequisiteGraph es estático y no se auto-amplía con datos reales.**  
`extend_with_document_concepts()` crea aristas "débiles" basadas en orden de documento. Pero no hay un mecanismo de retroalimentación: si un estudiante falla un prerrequisito que el grafo no conocía, el grafo no se actualiza.  
*Impacto:* el gate puede ser inexacto para dominios fuera del seed de álgebra/cálculo/física.

**W7 — `LearningSignalDetector` usa regex frágil.**  
Las detecciones de NOVICE/CONFUSION/HELP son por patrones de texto en español. No hay generalización semántica. Frases como "no logro captarlo" no serán detectadas como confusión.  
*Impacto:* señales débiles subestimadas en estudiantes que no usan las palabras clave exactas.

**W8 — `ChatTutorService.answer_stream()` ignora el motor pedagógico.**  
En streaming, `decision = None` y el LLM recibe `context=""`. El perfil no se usa. Solo funciona el path no-stream.  
*Impacto:* el modo streaming no es adaptativo; es un chatbot genérico disfrazado.

**W9 — No hay detección de "abandono" ni "monotonomía".**  
El sistema mide struggle pero no mide *tiempo desde última interacción*, *frecuencia de sesión*, ni *variedad de temas*. Un estudiante que solo hace quizzes de un solo concepto 50 veces no genera ninguna señal de sobreentrenamiento.  
*Impacto:* no se puede recomendar variedad ni descanso.

### 5.2 Debilidades de persistencia y arquitectura

**W10 — `DocumentMastery` no persiste `error_streak` ni `help_requests` en MongoDB.**  
El serializer `_to_doc()` de `MongoDBStudentProfileRepository` incluye `struggle_signals` pero no `error_streak` ni `help_requests` de `DocumentMastery`. Se pierden en persistencia.  
*Impacto:* métricas de documento incompletas tras reinicio.

**W11 — `DocumentMastery` no tiene `mastery` con decaimiento.**  
A diferencia de `ConceptMastery`, `DocumentMastery.apply_result()` no implementa `effective_mastery()`. El mastery del documento es EMA sin olvido.  
*Impacto:* un documento dominado hace 6 meses sigue con mastery alta aunque el estudiante haya olvidado el concepto.

**W12 — Concurrencia optimista sin backoff.**  
`MongoDBStudentProfileRepository.save()` usa `version` y lanza `ConcurrencyError` si hay conflicto. Pero `with_concurrency_retry` en el projector no tiene límite de reintentos documentado ni backoff exponencial.  
*Impacto:* en alta concurrencia, fallos silenciosos o reintentos sin control.

**W13 — `LearningPathAggregate.record_mastery` es independiente de `StudentProfile`.**  
La ruta de aprendizaje tiene su propio `mastery` por módulo, pero no está sincronizada con el `mastery_by_concept` del perfil. Son dos fuentes de verdad.  
*Impacto:* incoherencia entre "progreso de ruta" y "perfil cognitivo real".

---

## 6. ¿Qué decisiones toma el dominio y cuáles toma el LLM?

### 6.1 El dominio decide (SIEMPRE)

| Decisión | Dónde |
|----------|-------|
| Si el estudiante puede avanzar a un tema | `PrerequisiteGate.evaluate()` → `GateResult(blocked)` |
| Qué modo pedagógico usar | `PedagogicalEngine.select()` → `PedagogicalMode` |
| A qué dificultad | `DifficultyCalculator.from_profile()` → `Difficulty` |
| Qué estilo cognitivo | `CognitiveStyleSelector.select()` → `CognitiveStyle` |
| Qué conceptos son el foco | Prioridad: mapped_misconceptions > errors > weak > unmapped_memory > doc_focus |
| Si reutilizar un quiz existente | `LlmGate.generate_quiz()` con `quiz_repo.find_by_document()` |
| Si invalidar caché de análisis | `LlmGate.invalidate_document()` por cambio de contenido |
| Calificar un quiz | `QuizAggregate.grade()` — puro, sin LLM |
| Reequilibrio de claves de quiz | `ensure_quiz_quality()` — puro |
| Si una pregunta apunta a qué concepto | `ConceptTagger.tag_question()` — puro keyword |
| Si la pregunta del estudiante muestra struggle | `LearningSignalDetector.detect()` — puro regex |
| Qué recomendaciones dar | `RecommendationEngine.build()` — puro, basado en perfil |

### 6.2 El LLM solo genera (NUNCA decide)

| Acción | Qué genera |
|--------|-----------|
| `analyze` | JSON con `summary`, `key_concepts`, `suggested_questions`, `confidence_score` |
| `answer_question` | Texto libre dentro del prompt del `TutorPolicy` (modo + estilo + objetivo + evidencia) |
| `generate_quiz` | JSON con preguntas MCQ con `concept_tags` |

**Prueba de principio:** `PedagogicalDecision` es un dataclass inmutable creada por `PedagogicalEngine` y pasada a `TutorPolicy.answer_question()`. El prompt incluye `decision.mode.value`, `decision.target_difficulty.value`, `decision.focus_concepts`, `decision.evidence_summary`. El LLM no puede salirse de eso: no recibe ninguna instrucción para "decidir" pedagogía; solo para "generar lenguaje dentro de estos parámetros".

---

## 7. Preguntas específicas

### 7.1 ¿Qué métricas utiliza LARIA para medir el aprendizaje?

| Métrica | Dónde vive | Cómo se calcula |
|---------|-----------|-----------------|
| `mastery` (concepto) | `ConceptMastery.mastery` | EMA: `mastery = α×ratio + (1-α)×mastery_prev`, α∈[0.05,0.9] según señal |
| `effective_mastery` (concepto) | `ConceptMastery.effective_mastery(now)` | `mastery × exp(-ln2 × days/half_life) × (0.85 + 0.15×confidence)` |
| `mastery` (documento) | `DocumentMastery.mastery` | EMA: `α=0.4` |
| `confidence` (concepto) | `ConceptMastery.confidence` | +0.08×w si acierto y no help; -0.096×w si falla; -0.05 si help |
| `learning_velocity` | `StudentProfile.learning_velocity` | EMA 0.3×Δmastery + 0.7×prev |
| `pace` | `StudentProfile.pace` | slow/steady/fast basado en velocity y ratio weak/strong |
| `total_attempts` | `StudentProfile.total_attempts` | contador acumulado |
| `total_struggle_signals` | `StudentProfile.total_struggle_signals` | contador acumulado de asks con struggle |
| `struggle_signals` (doc) | `DocumentMastery.struggle_signals` | contador de `apply_soft_struggle` |
| `error_streak` | `ConceptMastery.error_streak`, `DocumentMastery.incorrect_streak` | consecutive failures |
| `latency_ms_ema` | `ConceptMastery.latency_ms_ema` | EMA 0.3×lat + 0.7×prev |
| `help_requests` | `ConceptMastery.help_requests`, `DocumentMastery.struggle_signals` | contador |
| `forgetting_gap` | `ConceptMastery.forgetting_gap(now)` | `stored_mastery - effective_mastery(now)` |
| `evidence_count` | `ConceptMastery.evidence_count` | total de `apply_evidence` llamadas |

### 7.2 ¿Cómo calcula el mastery del estudiante?

El mastery se calcula como una **media móvil exponencial (EMA) adaptativa**:

1. **Alpha base** (`α = 0.45` para conceptos, `0.4` para documentos).
2. **Modificación por señal:**
   - HELP_REQUEST: `ratio = min(ratio, 0.45)`, `α = max(α, 0.35)`. El help reduce el crédito del acierto.
   - ASK_STRUGGLE: `ratio = min(ratio, 0.35)`, `α = max(α, 0.4)`.
   - HIGH_LATENCY: `ratio = max(0, ratio - 0.15)`, `α = max(0.2, α×0.7)`.
   - REPEATED_ERROR: `ratio = min(ratio, 0.25)`, `α = max(α, 0.5)`, `error_streak++`.
   - QUIZ_ITEM/SUCCESS: `error_streak` se resetea si `ratio ≥ 0.5`, se incrementa si `< 0.5`.
3. **Penalización por ayuda:** `ratio = ratio × (1 - 0.35 × help_level)`.
4. **Actualización:** `mastery = α_eff × ratio + (1 - α_eff) × mastery_prev`.
5. **Con decaimiento (effective):** `effective = mastery × e^(-ln2×days/half_life) × (0.85 + 0.15×confidence)`.

**Nota:** alpha se acota a [0.05, 0.9]. La primera evidencia establece `mastery = ratio`.

### 7.3 ¿Qué evidencias modifican el perfil cognitivo?

| Evento | Fuente | Qué modifica |
|--------|--------|-------------|
| `TutorQuestionAskedEvent` | Ask tutor | `record_ask_struggle(doc, strength, concepts, latency, help_level)` → `DocumentMastery.apply_soft_struggle`, `ConceptMastery.apply_evidence(kind=ASK_STRUCH|HELP_REQUEST|HIGH_LATENCY)`, `total_struggle_signals++`, `frequent_errors`, `pedagogical_memory.remember_misconception`, `preferred_explanation_style`, `remember_strategy` |
| `QuizAttemptCompletedEvent` | Quiz | `record_quiz_result(doc, score, missed_concepts, concept_results)` → `DocumentMastery.apply_result`, `ConceptMastery.apply_evidence(kind=QUIZ_ITEM|REPEATED_ERROR)`, `total_attempts++`, `frequent_errors`, `pedagogical_memory.remember_misconception` |
| `LearningSignalDetector.detect(question)` | Pregunta del estudiante | Se usa en `AnalyzeDocumentService.answer_question_with_pedagogy` para mutar perfil *antes de la decisión* (in-mem, persistido via evento) |
| `DocumentMastery.apply_soft_struggle` | Ask implícito | `pull_toward = 0.15 + 0.25×strength`, `weight = 0.35 + 0.35×strength` |
| `PedagogicalMemory.remember_misconception` | Fracaso conceptual | Inserta en `frequent_misconceptions[:15]` |
| `PedagogicalMemory.remember_strategy` | Modo pedagógico aplicado | Inserta en `last_effective_strategies[:8]` |
| `PedagogicalMemory.set_preferred_style` | Estilo detectado | `preferred_explanation_style` |
| `_push_errors` | Cualquier concepto fallido | `frequent_errors[:20]` |
| `_update_pace` | Acumulación | `pace` |

### 7.4 ¿Cómo decide la dificultad de una explicación?

1. `DifficultyCalculator.from_profile(profile, focus_concepts)` extrae:
   - `effective_mastery = min(mastery de cada concepto en foco)` (o min de todos los documentos si no hay foco).
   - `confidence = avg(confidence de conceptos en foco)`.
   - `recent_error_rate = count(error_streak>0 OR last_score<0.5) / len(foco)`.
   - `pace = profile.pace`.
2. Calcula `score = effective_mastery - 0.15×(1-confidence) - 0.2×err_rate + 0.1×velocity + pace_bonus`.
3. Umbrales: <0.38 → EASY, <0.72 → MEDIUM, ≥0.72 → HARD.
4. `PedagogicalEngine` puede *sobrescribir* esto: si `blocked_by_prereq` o `concept_m < 0.4` o `in_hint` → fuerza EASY. Si `concept_m < 0.7` o `in_practice` y难度 era HARD → fuerza MEDIUM.

### 7.5 ¿Cómo detecta conceptos débiles y prerrequisitos?

**Conceptos débiles** (`StudentProfile.weakest_concepts`):
- Ordena `mastery_by_concept.values()` por `effective_mastery` asc (o `mastery` si `use_effective=false`).
- Filtra opcionalmente por `document_id` en `cm.document_ids`.
- Devuelve top-5.

**Conceptos olvidados** (`forgotten_concepts`):
- Ordena por `forgetting_gap() = stored_mastery - effective_mastery(now)` desc.
- Filtra `gap ≥ 0.15`.
- Devuelve top-5.

**Prerrequisitos** (`PrerequisiteGate.evaluate(target, profile)`):
- `all_prerequisites(canon)` → DFS topológico inverso sobre `_DEFAULT_EDGES`.
- Para cada prerrequisito: `mastery = profile.effective_concept_mastery(pre)`.
- Si `mastery < 0.45` o no existe en perfil → `missing`.
- Si `missing` no vacío → `blocked=True`, `remediation_focus = missing[:4]` (los más básicos primero).

**Misconceptions mapeadas** (`PedagogicalEngine.select`):
- Itera `profile.pedagogical_memory.frequent_misconceptions[:8]`.
- Para cada una: `MisconceptionResolver.resolve_entry(raw)` → `MisconceptionEntry` con `id`, `anchor_concept`, `remediation_strategy`.
- `mapped_focus` incluye `entry.id` + `anchor_concept` (si existe en grafo).
- Si no hay mapping → `unmapped_memory` (se usa como foco fallback).

### 7.6 ¿Qué información permanece persistente entre sesiones?

**Persistente en MongoDB (`student_profiles`):**
- `mastery_by_document` y `mastery_by_concept` (todo: intentos, mastery, confidence, error_streak, help_requests, latency_ms_ema, document_ids, half_life_days).
- `frequent_errors` (top 20).
- `pace`, `total_attempts`, `total_struggle_signals`, `learning_velocity`.
- `pedagogical_memory` (misconceptions, examples, analogies, style, strategies).
- `applied_event_ids` (top 256).
- `version` para optimismo.

**Persistente en MongoDB (`tutor_sessions`):**
- `step`, `focus_concepts`, `hints_given` (top 10), `turns`.
- Persistencia solo si `session_repo` configurado.

**Persistente en MongoDB (`event_outbox`):**
- Eventos publicados con `processed_at` y `last_error`.

**No persistente (volátil):**
- `LearningVelocity`, `pace` se recalculan en memoria.
- `ConceptMastery.confidence` se persiste.
- `TutorPolicy.POLICY_VERSION` persistido implícitamente en la caché de prompts de LlmGate.

**Persistencia dual memory/mongo:**
- `DB_PROVIDER=memory` → InMemory repos (datos en proceso, pierden todo con reinicio).
- `DB_PROVIDER=mongodb` → Motor async (persiste).
- El contrato de campos es idéntico.

### 7.7 ¿Qué decisiones toma el dominio y cuáles toma el LLM?

*(Ver sección 6 arriba. Resumen:)*
- **Dominio decide:** modo, dificultad, estilo, foco, prerrequisitos, calificación, recomendaciones, reuso de quiz, detección de señales.
- **LLM genera:** summary de documento, texto de respuesta tutor, preguntas de quiz. Todo bajo prompt inmutable de `TutorPolicy`.

### 7.8 ¿Qué información falta para personalizar verdaderamente la experiencia?

| Dato faltante | Por qué importa | Dónde debería vivir |
|---------------|----------------|---------------------|
| **Diario temporal de sesiones** | Detectar ritmo circadiano, días sin practicar, consistencia | Nueva colección `study_sessions` o campo `engagement_history` en perfil |
| **Detección de abandón** | Re-engagement proactivo | `last_interaction_at` + `days_since_last` en perfil |
| **Variedad de temas** | Evitar sobreentrenamiento en un solo concepto | `topics_explored` + `topic_diversity_index` |
| **Estilo de aprendizaje confirmado** (no inferido por regex) | Mejor predicción de preferencia | Encuesta inicial → `learning_style_profile` (VARK, Kolb) |
| **Metacognición** | ¿El estudiante sabe lo que sabe? | `self_assessment` por quiz de metacognición post-módulo |
| **Emoción/afecto** (más allá de `AffectPolicy`) | Adaptar tono emocional real | Integración opcional de sentimiento (NLP) → `affect_state` persistente |
| **Tiempo real por concepto** | Calcular "inversión" y ROI pedagógico | `concept_time_spent` en `ConceptMastery` |
| **Fuerza relativa entre conceptos** | Predecir qué concepto es prerrequisito de otro que aún no se ha mapeado | `prerequisite_strength` en `PrerequisiteGraph` con feedback de student outcomes |
| **Contexto social** (compañeros, cohort) | Aprendizaje colaborativo, benchmarking | `cohort_mastery` comparativo (anónimo) |
| **Feedback explícito del estudiante** | Validar si la percepción del sistema coincide con la del estudiante | `subjective_rating` post-sesión |

---

## 8. Recomendaciones de mejora sin romper la arquitectura DDD actual

### R1 — Persistencia atómica del perfil *antes* de la decisión
**Problema:** W1.  
**Solución:** En `AnalyzeDocumentService.answer_question_with_pedagogy`, después de `profile.record_ask_struggle()` in-mem, guardar *síncrono* el profile con `await self._profile_repo.save(profile)` **antes** de `self._engine.select()`.  
**Sin romper DDD:** El servicio ya tiene `profile_repository` inyectada. Es aplicación orquestando dominio + infraestructura. El dominio no cambia.  
**Riesgo:** Latencia extra (~5-15ms MongoDB). Mitigar con `with_concurrency_retry` y timeout.

### R2 — Desduplicación robusta de eventos
**Problema:** W2.  
**Solución:** Cambiar `_MAX_APPLIED_EVENT_IDS = 256` por un TTL temporal: `applied_event_ids` solo mantiene eventos de las últimas 24h (o últimos 500). Alternativamente, cambiar el dedup a base de `event_id` en `event_outbox` con `processed_at` y rechazar re-procesamiento por timestamp.  
**Sin romper DDD:** `StudentProfile` sigue siendo el agregado; la lógica de dedup se mueve a `LearningEvidenceProjector` o a `MongoOutboxEventBus.process_pending`.

### R3 — `DocumentMastery.effective_mastery` con decaimiento
**Problema:** W11.  
**Solución:** Agregar `effective_mastery(now)` a `DocumentMastery` siguiendo el patrón de `ConceptMastery` (misma fórmula Ebbinghaus). Actualizar `mastery_for()` y `weakest_documents()` en `StudentProfile` para usarlo.  
**Sin romper DDD:** Es un método nuevo en un dataclass existente. Sin cambio de interfaz de repositorio.

### R4 — Persistencia de `DocumentMastery.error_streak` y `help_requests`
**Problema:** W10.  
**Solución:** Añadir a `MongoDBStudentProfileRepository._to_doc()` las campos `error_streak` y `help_requests` dentro de cada entrada de `mastery_by_document`. Añadir en `_from_doc()`.  
**Sin romper DDD:** Solo infraestructura serializer. El aggregate no cambia.

### R5 — Ponderación de conceptos en `DifficultyCalculator`
**Problema:** W5.  
**Solución:** Permitir `DifficultyCalculator` recibir un `weight` por concepto (por ejemplo, desde `PrerequisiteGraph` o desde `PedagogicalEngine` basado en `mastery_by_concept[c].attempts`). O cambiar a weighted harmonic mean en vez de `min`.  
**Sin romper DDD:** Firmar ampliado de `from_profile(profile, focus_concepts)` a opcional `focus_weights: dict[str, float] = None`. Backward compatible.

### R6 — Auto-ampliación del grafo de prerrequisitos
**Problema:** W6.  
**Solución:** Añadir método `PrerequisiteGraph.learn_from_failure(target, missing_prereqs)` que añade `missing_prereqs` como prerrequisitos implícitos de `target` si no existen. O crear una `PrerequisiteGraph.upsert_edge(concept, prereq)`.  
**Sin romper DDD:** Mutación controlada del aggregate. El `PrerequisiteGate` sigue evaluando el mismo grafo.

### R7 — `ChatTutorService.answer_stream()` usar decisión pedagógica
**Problema:** W8.  
**Solución:** En `answer_stream`, resolver la decisión pedagógica (como en `answer`) y pasarla a `LlmGate.answer_question_stream`. Si hay latencia, hacer un *preflight* rápido de `PedagogicalEngine.select()` async.  
**Sin romper DDD:** Es un cambio de servicio (aplicación), no de dominio. `PedagogicalEngine.select()` ya es async-compatible vía repos async.

### R8 — Señales débiles semánticas
**Problema:** W7.  
**Solución:** Añadir al `LearningSignalDetector` un segundo paso con matching difuso (Levenshtein sobre verbos clave) o un pequeño modelo TF-IDF por categoría de señal. O integrar `ConceptTagger`-like para detectar *frustración* por patrones de error repetido en la sesión.  
**Sin romper DDD:** El detector sigue devolviendo `LearningSignal`. La mejora es interna del detector.

### R9 — Detección de abandono y monotonía
**Problema:** W9.  
**Solución:** Añadir a `StudentProfile`: `last_interaction_at: datetime`, `session_count_7d: int`, `topics_explored: set[str]` (persistido como list). Añadir `RecommendationEngine` recommendations: `re-engagement` si `days_since_last > 3`, `diversity` si `len(topics) < 3` y `total_attempts > 10`.  
**Sin romper DDD:** Campos nuevos en el aggregate. Serializer de repositorio actualizado.

### R10 — Unificar `LearningPath` y `StudentProfile`
**Problema:** W13.  
**Solución:** Hacer que `LearningPathAggregate.record_mastery` publique un `LearningPathUpdatedEvent` que el `LearningEvidenceProjector` use para sincronizar `StudentProfile.mastery_by_concept` con `LearningModule.mastery`. O hacer que `LearningPath` sea un *read model* derivado del perfil (no agregado separado).  
**Sin romper DDD:** Si `LearningPath` se convierte en read model, se elimina la doble fuente. La escritura sigue en `StudentProfile`.

### R11 — Caché de perfil con `lru_cache` o Redis
**Problema:** Cada `find_by_student` hace un roundtrip MongoDB.  
**Solución:** En `dependencies.py`, envolver `get_profile_repo()` con un adaptador que use `CachePort` (ya inyectado en otras partes). El perfil es lectura-frecuente-escritura-rara.  
**Sin romper DDD:** Infrastructure-only. `StudentProfileRepository` interface unchanged.

### R12 — `applied_event_ids` con compactación por TTL
**Problema:** W2 (complemento).  
**Solución:** Añadir `updated_at` a cada entry en `applied_event_ids` como metadato, o cambiar a `applied_event_timestamps: dict[str, datetime]` y compactar periódicamente. O usar Bloom filter persistente.  
**Sin romper DDD:** Es un cambio de implementación del agregado, no de interfaz.

---

## 9. Resumen de responsabilidad por archivo (referencia rápida)

| Archivo | Tipo | Responsabilidad principal |
|---------|------|--------------------------|
| `domain/aggregates/student_profile.py` | Aggregates | Perfil cognitivo, mastery, evidencia, memoria |
| `domain/aggregates/tutor_session.py` | Aggregates | Sesión multi-turno, máquina de estados |
| `domain/aggregates/quiz_aggregate.py` | Aggregates | Quiz + grading |
| `domain/aggregates/quiz_attempt_aggregate.py` | Aggregates | Intento de quiz + evento |
| `domain/aggregates/learning_path.py` | Aggregates | Ruta curricular con prerrequisitos |
| `domain/aggregates/document_aggregate.py` | Aggregates | Documento + análisis embebido |
| `domain/aggregates/tutor_interaction.py` | Aggregates | Interacción Q&A tutor |
| `domain/aggregates/user_aggregate.py` | Aggregates | Identidad, roles, auth |
| `domain/services/pedagogical_engine.py` | Services | Decisión pedagógica (modo/dificultad/foco) |
| `domain/services/difficulty_calculator.py` | Services | Cálculo de dificultad |
| `domain/services/recommendation_engine.py` | Services | Recomendaciones de estudio |
| `domain/services/prerequisite_graph.py` | Services | Grafo curricular + gate |
| `domain/services/cognitive_style.py` | Services | Selección de estilo cognitivo |
| `domain/services/misconception_resolver.py` | Services | Match de misconceptions al catálogo |
| `domain/services/tutor_policy.py` | Services | Composición de prompts |
| `domain/services/quiz_quality.py` | Services | Validación y reequilibrio de quiz |
| `domain/services/concept_tagger.py` | Services | Tagging de conceptos en preguntas |
| `domain/services/context_selector.py` | Services | Recorte de contexto de documento |
| `domain/services/model_router.py` | Services | Selección de modelo OpenAI |
| `domain/services/learning_signal_detector.py` | Services | Detección de struggle por regex |
| `domain/catalog/misconception_catalog.py` | Catalog | 8 misconceptions de álgebra |
| `domain/concept_identity.py` | Core | `canonicalize_concept()` |
| `application/services/learning_evidence_projector.py` | Application | Proyectar eventos → perfil |
| `application/services/analyze_document_service.py` | Application | Orquestar ask + pedagogía |
| `application/services/quiz_service.py` | Application | Generar + submit quiz |
| `application/services/learning_query_service.py` | Application | Lectura de historial/perfil/recomendaciones |
| `application/services/llm_gate.py` | Application | Economía de tokens + caché |
| `application/services/chat_tutor_service.py` | Application | Tutor chat (pedagógico o libre) |
| `application/services/chat_tutor_service.py` | Application | Tutor chat (pedagógico o libre) |
| `infrastructure/mongodb/student_profile_repository.py` | Infrastructure | Serializer MongoDB + optimista |
| `infrastructure/mongodb/outbox_event_bus.py` | Infrastructure | Outbox + process_pending |
| `infrastructure/openai/openai_ia_analyst.py` | Infrastructure | Cliente OpenAI |
| `interfaces/api/dependencies.py` | Interfaces | Wire-up de dependencias FastAPI |
| `interfaces/api/routers/learning.py` | Interfaces | Endpoints `/learning/me` y `/learning/me/profile` |
| `interfaces/api/routers/quizzes.py` | Interfaces | Endpoints quizzes |
| `interfaces/api/routers/documents.py` | Interfaces | Endpoints documentos |
| `interfaces/api/routers/auth.py` | Interfaces | Registro y token JWT |
| `domain/events/domain_events.py` | Events | `TutorQuestionAskedEvent`, `QuizAttemptCompletedEvent`, etc. |
| `main.py` | Entrypoint | Lifespan: índices, admin, projector, outbox worker |

---

## 10. Métricas del sistema ( `/metrics` )

El backend expone `GET /metrics` con contadores operativos que reflejan la actividad del motor pedagógico:

| Métrica | Tipo | Qué mide |
|---------|------|----------|
| `laria_llm_calls` | Counter | Llamadas a OpenAI por task/model/outcome |
| `laria_llm_latency_ms` | Histogram | Latencia de LLM por task/model |
| `laria_llm_skipped` | Counter | Skips por razón (cache, document_embedded, reuse_quiz) |
| `laria_cache_hit` | Counter | Hits de caché por task |
| `profile_updates` | Counter | Persistencias de perfil (origen ask/quiz) |
| `laria_struggle_signals` | Counter | Señales de struggle por kind |
| `laria_high_latency` | Counter | Preguntas con latency ≥ 8s |
| `laria_concepts_weak` | Gauge | # conceptos con mastery bajo (agg) |
| `laria_concepts_mastered` | Gauge | # conceptos dominados (agg) |
| `laria_quiz_attempts` | Counter | Intentos de quiz |
| `laria_quiz_score_ratio` | Histogram | Ratio de acierto por intento |
| `outbox_processed` | Counter | Eventos procesados del outbox |
| `outbox_unsupported` | Counter | Eventos no soportados |
| `outbox_pending` | Gauge | Eventos pendientes |
| `outbox_failed` | Counter | Fallos de handler |

---

*Fin de la auditoría.*
