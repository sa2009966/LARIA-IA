# ADR-003: Mastery multi-señal, curva del olvido y gate de prerrequisitos

- **Estado:** Aceptado
- **Fecha:** 2026-07-24
- **Rama de origen:** `feature/backend`
- **Decisores:** Equipo LARIA (orquestación backend)

## Contexto

LARIA ya proyectaba evidencia de quizzes a `ConceptMastery` (EMA de aciertos) y adaptaba modo/dificultad con `PedagogicalEngine`. Eso no bastaba para un tutor de largo plazo:

- El dominio no distinguía ayuda solicitada, latencia ni errores repetidos.
- No existía olvido temporal (Ebbinghaus).
- Se podía “explicar” temas avanzados sin bases.
- La memoria era historial conversacional, no memoria pedagógica compacta.

## Decisiones

### 1. Extender `StudentProfile` / `ConceptMastery` (no nuevo bounded context)

- Evidencia multi-señal vía `EvidenceSample` + `apply_evidence`.
- `effective_mastery(now)` con decaimiento exponencial (half-life configurable).
- `PedagogicalMemory` compacta en el perfil (misconceptions, analogías, estilo).

**Consecuencia:** un solo agregado cognitivo; proyecciones y API de perfil siguen en el mismo puerto.

### 2. Gate de prerrequisitos determinista en dominio

- `PrerequisiteGraph` + `PrerequisiteGate` bloquean focos avanzados si faltan bases.
- El LLM **nunca** decide saltar prerrequisitos; solo genera lenguaje sobre el foco de remediación que fija LARIA.

### 3. Pedagogía sigue fuera de infraestructura

- `DifficultyCalculator`, `CognitiveStyleSelector`, `RecommendationEngine`, `ModelRouter` viven en dominio/aplicación.
- `LlmGate` aplica economía de tokens (caché / reuso) antes de OpenAI.
- Métricas vía `MetricsPort` (sistema), no como “inteligencia” del modelo.

### 4. Un solo vendor OpenAI; router interno de modelos

- Compatible con ADR-001: `OPENAI_MODEL_DEFAULT` (mini) y `OPENAI_MODEL_STRONG`.
- Escalado solo cuando struggle / socrático+hard / reintento JSON lo justifican.

## Alternativas rechazadas

| Alternativa | Rechazo |
|-------------|---------|
| Mastery solo % aciertos | No captura ayuda/tiempo/olvido |
| Dejar que el LLM decida prerrequisitos | Rompe “pedagogía en LARIA” |
| Nuevo microservicio de mastery | Acoplamiento y deuda prematura |
| Caché sin invalidación | Riesgo de servir pedagogía obsoleta |

## Consecuencias

- API de perfil expone `effective_mastery`, `confidence`, memoria pedagógica.
- Recomendaciones incluyen forgotten / pending / next_topic / study_time.
- Tests de dominio deben cubrir olvido, gate y multi-señal sin red.
