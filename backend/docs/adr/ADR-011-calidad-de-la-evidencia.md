# ADR-011: La evidencia sabe de qué concepto habla

- **Estado:** Aceptado
- **Fecha:** 2026-09-18
- **Rama de origen:** `feature/backend`
- **Decisores:** Equipo LARIA (orquestación backend)
- **Depende de:** [ADR-007](ADR-007-evidencia-ponderada-por-calidad.md) (peso por calidad), [ADR-006](ADR-006-oferta-vs-bloqueo.md)
- **Implementa:** fase 4 de [`4_PLAN_CORRECCION.md`](../4_PLAN_CORRECCION.md)

## Contexto

Los ADR 007 a 009 afinaron *cuánto pesa* cada evidencia y *quién puede escribirla*. Pero toda esa
precisión se calcula sobre conceptos que decide un puñado de heurísticas, y ahí había cuatro
problemas de entrada:

1. **Se inventaba un concepto.** `ConceptTagger` terminaba con `tags.append("general")` cuando no
   reconocía el ítem, y el projector repetía el patrón (`tags = tagged.concept_tags or ("general",)`).
   Ese "general" entraba a `mastery_by_concept` como cualquier otro concepto: engordaba el perfil,
   competía por el foco, aparecía en `weakest_concepts` y podía llegar al gate. Un cajón de sastre
   disfrazado de conocimiento.
2. **Las materias se cruzaban.** `desigualdad` en un quiz de álgebra es una inecuación; la heurística
   la etiquetaba como `desigualdad social`, un concepto de ciencias sociales. El alumno de
   Matemática acumulaba evidencia en una materia que nunca estudió.
3. **La pregunta no entraba en el foco.** La precedencia era misconceptions → errores → débiles →
   conceptos del documento, y el tema preguntado solo elegía el *estilo*. El prompt podía decir
   "foco: funciones" mientras el alumno preguntaba por derivadas.
4. **El detector solo entendía seis maneras de pedir ayuda.** "No logro captarlo", "no me entra" o
   "sigo sin entender" no disparaban nada, y el turno se atendía como si nadie hubiera pedido nada.

Además, una comprobación que cambió el alcance previsto: **los `concept_tags` del modelo ya eran la
fuente**. El prompt los exige, el adaptador los parsea, el tagger solo rellena huecos
(`if question.concept_tags: return question`) y Mongo los persiste. Lo que faltaba no era usarlos,
sino dejar de tapar sus huecos con un concepto falso y poder medir cuántos huecos hay.

## Decisión

### 1. No saber de qué es un ítem es un dato; inventarlo, no

- `ConceptTagger` devuelve la pregunta **sin etiquetas** cuando ni el modelo, ni las heurísticas, ni
  los conceptos del documento dicen nada. Se acabó `"general"`.
- El projector no le atribuye evidencia de concepto a un ítem sin etiquetar: el intento **sigue
  contando** para el mastery del documento, que es lo que sí se midió.
- Métrica nueva `laria_quiz_items{tagged=yes|no}`: la cobertura de etiquetado es observable. Si cae,
  el perfil se está quedando ciego y hay que mirar el prompt de generación, no el mastery.

### 2. Las heurísticas se acotan por área de conocimiento

- `domain/subject_areas.py`: `EXACTAS` y `SOCIALES`, derivadas de la materia del documento.
- Los patrones de `ConceptTagger` y `LearningSignalDetector` llevan área. `desigualdad` resuelve a
  `desigualdad` en Matemática y a `desigualdad social` en Historia.
- **Sin materia reconocida no se filtra nada**: es la opción segura para llamadas que no conocen el
  documento (mejor todas las heurísticas que ninguna).
- **Lo que NO se hace:** meter la materia en la *clave* del mastery (`algebra:desigualdad`). Eso
  exige migrar perfiles, el grafo de prerrequisitos, el catálogo de misconceptions y las
  recomendaciones, que hoy asumen clave plana. El cruce se corta en el origen —que es donde ocurría—
  y la clave sigue siendo una. `ConceptMastery.subject` sigue sin rellenarse: queda anotado como
  campo muerto, no como funcionalidad.

### 3. La pregunta lidera el foco

Era la decisión de producto que el plan de experiencia pedagógica dejó abierta. **Se decide que sí**,
con la regla más conservadora que arregla la contradicción:

- Los conceptos **que el material declara** y que la pregunta nombra encabezan el foco; las
  debilidades siguen ahí, detrás. No se inventan conceptos desde el texto libre.
- **Excepción, intacta:** con `SEQUENCE` (hueco medido y repetido en un prerrequisito) el turno
  sigue liderando con la base y el prompt explica por qué (ADR-006). Es la única desviación de foco
  permitida, y ahora es la única que existe.

### 4. El detector entiende cómo habla la gente

- Un solo paso de normalización (sin acentos, minúsculas) y patrones escritos en esa forma.
- Cobertura ampliada: confusión ("no logro…", "no me entra", "sigo sin entender", "me cuesta"),
  ayuda ("explícamelo más fácil", "paso a paso", "¿me podés ayudar?") y novato ("recién empiezo",
  "es la primera vez que lo veo").
- Subir la sensibilidad es seguro **ahora** y no antes: desde el ADR-007 una señal de auto-reporte
  es evidencia débil que no escribe expediente de errores ni fuerza andamiaje en el turno.

## Consecuencias

- Los perfiles dejan de acumular un concepto `general` que nunca significó nada. Los que ya lo
  tienen persistido lo conservan hasta que caduque por olvido; no se migra, porque distinguir qué
  evidencia hay debajo es imposible.
- Un quiz cuyos ítems no se pueden etiquetar deja de producir evidencia de concepto. Eso es una
  pérdida **aparente**: esa evidencia era ruido con nombre.
- El prompt del tutor ya no puede contradecirse: el foco que declara es el tema por el que le
  preguntaron, salvo cuando anuncia que empieza por la base.
- Más turnos se clasifican como CONFUSION/HELP. Con el peso del ADR-007 eso mueve el registro
  (estilo, modo) mucho antes que el nivel.

## Fuera de alcance

- **Detección semántica** (embeddings o modelo pequeño) en vez de regex. La normalización y la
  cobertura tapan los casos frecuentes; lo demás necesita medición antes que más heurística.
- **Materia en la clave del mastery**, y con ella `ConceptMastery.subject`.
- **Etiquetado del turno de chat**: los conceptos de una pregunta salen de las heurísticas; el
  turno no pide al modelo que etiquete su propia respuesta.
