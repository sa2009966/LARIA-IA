# Investigación — adaptación pedagógica y check-ins socioemocionales

Fecha: 2026-09-16  
Alcance: backend de LARIA; investigación previa a un plan de integración. No es orientación clínica ni una especificación de interfaz.

## Pregunta

¿Cómo puede LARIA adaptar la tutoría a cada estudiante y conocer su disposición de aprendizaje sin convertir preferencias en etiquetas fijas ni usar el producto como un sistema de diagnóstico psicológico?

## Hallazgos que condicionan el diseño

### 1. Adaptar no significa clasificar al estudiante en un "estilo de aprendizaje"

La revisión de Pashler, McDaniel, Rohrer y Bjork no encontró evidencia suficiente para justificar intervenciones que emparejen instrucción con etiquetas como visual, auditivo o kinestésico. La personalización debe aprender de resultados observables y revisables, no fijar una identidad educativa.

Fuente primaria: [Learning Styles: Concepts and Evidence](https://doi.org/10.1111/j.1539-6053.2009.01038.x).

Implicación para LARIA:

- Persistir hipótesis de baja confianza sobre qué estrategia funcionó en un contexto, nunca un diagnóstico de "tipo de alumno".
- Evaluar estrategias con evidencia posterior: comprensión declarada, intento de recuperación, acierto en microejercicio, resultado de quiz y abandono/continuidad.
- Mantener exploración controlada: una estrategia con poca evidencia no desplaza a la que ya funciona.

### 2. Los check-ins repetidos son viables, pero el bienestar no debe medicalizarse

La literatura de ecological momentary assessment (EMA) muestra que mediciones breves y repetidas pueden recoger afecto y contexto en tiempo real; también señala evidencia limitada, carga de respuesta y necesidad de diseño adaptado para población joven. Eso justifica un check-in educativo breve, no un cribado de depresión, ansiedad o riesgo.

Fuentes: [revisión EMA en niños y adolescentes](https://pubmed.ncbi.nlm.nih.gov/30069650/), [revisión de implementación EMA con jóvenes](https://pubmed.ncbi.nlm.nih.gov/28475765/) y [umbrella review de monitorización móvil](https://pubmed.ncbi.nlm.nih.gov/37725422/).

Implicación para LARIA:

- El P0 debe usar solo respuestas estructuradas y voluntarias: disponibilidad para estudiar, carga percibida y objetivo del turno.
- Frecuencia inicial: como máximo una invitación por 48 horas y nunca bloquear la sesión si se rechaza o ignora.
- No incluir preguntas de diagnóstico, ideación suicida, trauma, medicación ni texto libre en el P0.
- Una respuesta de malestar cambia la forma de estudiar (brevedad, pausa, práctica guiada); no infiere una condición psicológica ni modifica mastery.

### 3. Los datos socioemocionales de estudiantes requieren una protección más estricta

UNESCO exige una aproximación humana, adecuada a la edad y protectora de privacidad para GenAI educativa. El Departamento de Educación de EE. UU. enfatiza transparencia, seguridad, consentimiento/opt-out y evaluación de riesgos al usar datos de estudiantes. La OMS sitúa autonomía, consentimiento válido, privacidad y supervisión humana como principios indispensables cuando la IA trata información de salud.

Fuentes: [UNESCO: Guidance for generative AI in education and research](https://www.unesco.org/en/articles/guidance-generative-ai-education-and-research?hub=253682), [U.S. Department of Education: AI toolkit](https://files.eric.ed.gov/fulltext/ED661924.pdf), [U.S. Department of Education: privacy guidance](https://studentprivacy.ed.gov/sites/default/files/resource_document/file/Student%20Privacy%20and%20Online%20Educational%20Services%20%28February%202014%29_0.pdf) y [OMS: Ethics and governance of AI for health](https://www.who.int/publications/i/item/9789240029200).

Implicación para LARIA:

- Separar `LearningEvidence` de `WellbeingCheckIn`; no mezclar bienestar con mastery, recomendaciones académicas permanentes ni prompts enviados al proveedor LLM.
- Consentimiento explícito, revocable y auditable antes de almacenar check-ins; para menores, el flujo legal/parental debe definirse según jurisdicción antes de activarlo.
- Retención corta configurable, borrado por usuario y acceso restringido. No usar esos datos para entrenamiento, publicidad, calificación ni decisiones disciplinarias.
- Definir un protocolo humano institucional antes de aceptar texto libre o señales de riesgo. Fuera de ese protocolo, el sistema no debe pretender detectar ni gestionar crisis.

## Decisión de producto recomendada

LARIA debe modelar un **estado de aprendizaje contextual y revisable**, no una personalidad permanente. La adaptación puede usar cuatro fuentes, ordenadas por confianza:

1. Evidencia de aprendizaje calificada: quiz, microejercicio, recuperación y errores.
2. Eficacia histórica de una estrategia para ese estudiante y concepto: por ejemplo, si ejemplos trabajados preceden mejora verificable.
3. Preferencia explícita del turno: explicar, practicar, repasar, ir breve o ir paso a paso.
4. Check-in de disposición voluntario: energía/disponibilidad y carga percibida; solo modula el tamaño y el ritmo de la interacción.

No debe usar etiquetas fijas, inferencias clínicas ni el texto emocional como evidencia de dominio conceptual.

## Hipótesis medibles para el piloto

| Hipótesis | Métrica primaria | Guardarraíl |
|---|---|---|
| Elegir estrategia según eficacia contextual mejora aprendizaje | mejora de microejercicio o quiz posterior frente a baseline | no reducir exposición a estrategias alternativas sin evidencia suficiente |
| Adaptar longitud/ritmo a check-in voluntario mejora continuidad | finalización de turno y abandono de sesión | no cambiar mastery ni etiquetar bienestar |
| Explicar el porqué de la adaptación mantiene autonomía | aceptación/rechazo explícito de sugerencia | siempre permitir "seguir como prefiero" |
| Check-in de baja frecuencia no sobrecarga | tasa de respuesta, dismiss y opt-out | límite de una invitación cada 48 h |

## No afirmar todavía

- Que un check-in cada día o cada dos días mejore resultados en LARIA: es una hipótesis de experimento, no un hecho establecido.
- Que una señal conversacional equivalga a bienestar o comprensión.
- Que una preferencia actual sea estable en otras materias, días o niveles de dificultad.
- Que LARIA pueda atender crisis psicológicas sin un protocolo institucional, responsables humanos y revisión legal.
