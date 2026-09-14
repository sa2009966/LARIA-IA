# ADR-001: Tutor hexagonal con OpenAI único y evidencia de aprendizaje

- **Estado:** Aceptado
- **Fecha:** 2026-07-21
- **Rama de origen:** `feature/backend`
- **Decisores:** Equipo LARIA (orquestación backend)

## Contexto

LARIA debe ser un **tutor inteligente adaptativo**, no un chatbot genérico. El backend necesitaba:

- Separar reglas educativas del transporte HTTP y de los proveedores externos.
- Un proveedor de lenguaje estable y operable en despliegue.
- Base de **evidencia de aprendizaje** (quizzes + interacciones) antes del perfil cognitivo completo.
- Seguridad mínima para exposición (JWT, secretos, abuse, docs).

Existía deuda: dual Kimi/OpenAI con default Kimi, stack `AnalysisRepository` no cableado, prompts embebidos en infraestructura, y contratos de análisis inconsistentes.

## Decisiones

### 1. Arquitectura hexagonal + DDD

- Dominio con aggregates, value objects, events y ports.
- Casos de uso en `application/`.
- Adaptadores en `infrastructure/`.
- HTTP solo en `interfaces/api/`.

**Consecuencia:** se puede cambiar Mongo↔memoria u OpenAI↔otro chat-compatible sin reescribir dominio.

### 2. Un solo proveedor de IA: OpenAI

- `IA_PROVIDER` solo admite `openai`.
- Arranque exige `OPENAI_API_KEY`.
- Modelo por defecto: `gpt-4o-mini`.
- Se elimina el adaptador Kimi/Moonshot del producto.

**Por qué:** el producto desplegado usa OpenAI; mantener Kimi como default generaba riesgo operativo y ruido arquitectónico sin valor pedagógico.

**Consecuencia:** menos superficie de configuración; un solo camino de fallos/observabilidad. Si en el futuro se necesita otro vendor, se añade un adaptador detrás de `IAAnalyst` sin cambiar servicios.

### 3. El modelo solo genera lenguaje; la pedagogía es de LARIA

- Los prompts viven en `domain/services/tutor_policy.py` (`TutorPolicy`).
- `BaseChatAnalyst` ejecuta HTTP y parseo JSON; no “inventa” la estrategia educativa.

**Consecuencia:** se puede evolucionar scaffolding, dificultad y uso de evidencia sin tocar el cliente OpenAI.

### 4. Análisis embebido en el documento

- Se elimina el bounded context muerto `AnalysisAggregate` + `AnalysisRepository`.
- El resultado de análisis se persiste en `DocumentAggregate.analysis_result`.
- Contrato canónico: `summary`, `key_concepts: list[str]`, `suggested_questions: list[str]`, `confidence_score`.

**Consecuencia:** menos duplicación y un solo camino de persistencia alineado con la API.

### 5. Evidencia de aprendizaje vía eventos

- `TutorQuestionAskedEvent` y `QuizAttemptCompletedEvent` alimentan `LearningEvidenceProjector`.
- Read model actual: `GET /learning/me`.

**Consecuencia:** base para el perfil cognitivo futuro sin acoplar el grading HTTP a proyecciones complejas todavía.

### 6. Seguridad de borde

- `SECRET_KEY` fail-closed; JWT HS256 fijado en código.
- Rate limiting; docs bajo `ENABLE_DOCS`; ownership → 404 uniforme.
- Password policy reforzada; anti-enumeración en registro; bcrypt dummy en login.

**Consecuencia:** apto para integración en `develop` con menor riesgo de abuso y fuga de metadatos.

### 7. Secretos fuera de git

- Solo se versiona `.env.example` vacío.
- `.env`, claves y PEM están en `.gitignore`.
- Tests usan placeholders (`sk-test-…`), nunca claves reales.

## Alternativas consideradas

| Alternativa | Rechazo |
|-------------|---------|
| Multi-provider (Kimi + OpenAI) configurable en runtime | Complejidad y default peligroso; producto es OpenAI-only |
| Prompts solo en infraestructura | Viola la visión “IA = lenguaje”; dificulta adaptación pedagógica |
| Mantener AnalysisRepository paralelo | Código muerto y doble serialización |
| GPT-4o como default global | Costo/latencia innecesarios para JSON tutor; mini basta como base |

## Estado de cumplimiento

Implementado en `feature/backend`. Pendiente de **testeo en `develop`** antes de promover a `main`.

## Referencias

- [architecture.md](../architecture.md)
- [endpoints.md](../endpoints.md)
- [backend.md](../backend.md)
