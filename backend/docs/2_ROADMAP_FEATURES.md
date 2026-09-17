# Roadmap de features — Integración de valor

> **Depende del cierre de los 4 puntos críticos** (ver documento `1_CIERRE_PUNTOS_CRITICOS.md`).
> Ninguna feature de este documento se construye antes de que el core adaptativo esté cerrado y en
> shadow mode. Este documento asume ese trabajo ya hecho.

## Tesis de producto

El sistema tiene una **asimetría**: es fuerte modelando al alumno (9 señales cognitivas, mastery,
evidencia proyectada desde eventos) y débil modelando el conocimiento (lista plana de conceptos sin
estructura). Es un GPS excelente sin mapa de carreteras.

Consecuencia para el roadmap: **lo que más valor desbloquea es dar estructura al conocimiento, no
añadir más señales del alumno.** Ya hay suficiente señal; falta contra qué proyectarla.

## Orden por apalancamiento (no solo por esfuerzo)

| Prioridad | Feature | Qué desbloquea | Reutiliza |
|-----------|---------|----------------|-----------|
| 1 ✅ | Grafo de prerrequisitos | Tutor diagnóstico (no reactivo) | `StudentProfile.mastery` |
| 2 | Repetición espaciada | Retención / re-engagement | `mastery` por concepto |
| 3 | Detección de misconceptions | Diagnóstico fino del error | quizzes + `error_persistence` |
| 4 | Explicabilidad pedagógica | Confianza + metacognición | bandas + señales existentes |
| 5 | "Por qué me equivoqué" | Cierre del lazo del error | misconceptions (#3) |
| 6 | Dashboard docente/tutor | Transparencia + valor percibido | perfil + mastery + evidencia |
| 7 | Calibración de confianza | Metacognición + resuelve entanglement | confianza declarada vs acierto |
| — | Grabaciones de clase | (frenar hasta validar core) | STT real (alto costo) |

---

## 1. Grafo de prerrequisitos entre conceptos — ✅ implementado

> **Corrección de la premisa.** Este documento asumía "lista plana de conceptos sin estructura". La
> auditoría del código mostró que el grafo **ya existía** (`_DEFAULT_EDGES` en
> `domain/services/prerequisite_graph.py`), pero hardcodeado en el módulo, reconstruido por request
> (`get_pedagogical_engine()` no estaba cacheado ⇒ las aristas auto-añadidas se descartaban al
> terminar), sin procedencia y sin invariante DAG. El trabajo fue **promoverlo**, no crearlo. Esto
> cambió el alcance, no la prioridad.
>
> Cerrado en [ADR-005](adr/ADR-005-grafo-prerrequisitos-curado.md): agregado `ConceptGraph`
> persistido y versionado, procedencia `CURATED`/`INFERRED` (solo lo curado puede bloquear a un
> estudiante), DAG validado en escritura y remediación dirigida a la **causa raíz** upstream.
> Pendiente y fuera de ese ADR: endpoints de curación docente y el detector estadístico de aristas
> inferidas.

**La pieza que cambia la categoría del producto.** Sin él, el tutor es reactivo: responde lo que
preguntan. Con él, es diagnóstico: cuando alguien falla en X, el sistema sabe que el hueco real puede
estar en el prerrequisito W, y remedia la causa, no el síntoma. Convierte el modelo del alumno en algo
*accionable*.

**Decisiones de diseño a resolver antes de codear:**

- **Representación:** ¿agregado nuevo `ConceptGraph` vs. metadata (`prerequisites: list[concept_id]`)
  en el concepto? Recomendación inicial: agregado propio, porque el grafo tendrá su propio ciclo de
  vida (edición docente, versiones) independiente de los conceptos.
- **Origen de las aristas:** tres fuentes posibles —
  1. **Docente/curador** las define (alta calidad, no escala).
  2. **Inferidas** desde correlaciones de mastery (escala, ruidosas).
  3. **Híbrido:** el sistema propone aristas por correlación, un humano las aprueba.
  Recomendación: empezar por (1) para un dominio piloto y usar (2) como sugerencia, nunca como verdad
  automática.
- **Consulta desde `PedagogicalEngine`:** ante un fallo en X, recorrer prerrequisitos de X con mastery
  bajo y priorizar remediar el prerrequisito más upstream con mastery insuficiente.
- **Guardarraíl:** el grafo debe ser un DAG (sin ciclos); validar en escritura.

**Si solo se hiciera una feature este trimestre, sería esta.**

---

## 2. Repetición espaciada

**La que da retención casi gratis.** Los productos educativos mueren por abandono, no por mala
pedagogía. Un scheduler que trae de vuelta al alumno justo antes de olvidar ("hoy toca repasar 3
conceptos") es re-engagement legítimo *y* pedagógicamente correcto.

**Diseño:**

- Algoritmo tipo **SM-2** (o variante) sobre `mastery` por concepto: cada concepto tiene un intervalo
  de repaso que crece con aciertos y se reinicia con fallos.
- Nuevo campo por concepto en el modelo del alumno: `next_review_at`, `interval`, `ease`.
- Punto de entrada: un endpoint / vista "repaso de hoy" que devuelve los conceptos vencidos.
- Sinergia con el grafo (#1): priorizar repaso de conceptos que son prerrequisito de otros.

Bajo esfuerzo sobre lo existente, impacto directo en negocio (retención). **Antes que las
grabaciones.**

---

## 3. Detección de misconceptions

Convierte errores en diagnóstico. Hoy `error_persistence` dice *que* alguien falla; el **distractor
concreto** que elige en un quiz dice *qué* malentiende, y los malentendidos vienen en patrones
conocidos por materia.

**Diseño:**

- Etiquetar los distractores de cada quiz con la misconception que representan.
- Clusterizar las elecciones del alumno para detectar patrones recurrentes.
- Salida: "confunde causalidad con correlación" en vez de "practica más".
- Alimenta directamente la feature #5.

---

## 4. Explicabilidad pedagógica (por qué te enseño así)

Ya hay transparencia *técnica* (endpoint de borrado, bandas neutras) pero no transparencia
*pedagógica*. Mostrar al alumno "te doy más ejemplos porque en los últimos temas te ayudaron a
acertar" aumenta confianza y desarrolla metacognición.

**Diseño:**

- Derivar una explicación en lenguaje natural desde las señales que dispararon cada
  `AdaptationParameter` activo.
- Barato: las bandas y señales ya existen; es una capa de presentación sobre `AdaptivePolicy`.
- Diferenciador de producto en un mercado nervioso sobre IA opaca en educación.

---

## 5. "Por qué me equivoqué" (no solo correcto/incorrecto)

Contraparte de #4 aplicada al contenido: cerrar el lazo del error con una explicación dirigida al
malentendido específico, no un genérico.

**Diseño:**

- Se apoya en #3 (misconceptions): la explicación del error usa la misconception detectada.
- Integrable en el flujo de quiz existente.

---

## 6. Dashboard docente/tutor

El perfil cognitivo (bandas neutras) + mastery + evidencia cruda ya es un dashboard esperando existir,
y de paso cumple el guardarraíl de transparencia del blueprint.

**Diseño:**

- Vista de solo lectura sobre datos ya proyectados. Sin lógica de dominio nueva.
- Mostrar bandas (no etiquetas), trayectoria de mastery, conceptos débiles, aristas del grafo con
  huecos.
- Bajo esfuerzo, alto valor percibido (especialmente en venta a instituciones).

---

## 7. Calibración de confianza

Comparar confianza declarada vs. acierto real y devolver esa metacognición al alumno.

**Doble valor:**

- Feature de producto (metacognición).
- Es la **fuente ortogonal** que resuelve el Punto 4 del documento de cierre: permite adaptar por
  confianza sin entanglement con `clarification_rate`.

---

## Lo que se frena: grabaciones de clase

No por mala idea, sino porque es un **producto distinto** disfrazado de feature: pipeline de STT real,
PII, retención de audio, costos de infra recurrentes — todo antes de validar que el core adaptativo
mejora resultados.

**Decisión:** dejar explícitamente para después de que el lazo de outcomes demuestre que la adaptación
funciona. Construir grabaciones ahora es apostar recursos a que el problema es "falta contenido" cuando
probablemente el problema es "aún no sabemos si personalizar sirve".

---

## Secuencia recomendada

1. ✅ Cerrar los 4 puntos críticos (documento 1) + core adaptativo en shadow mode — ADR-004.
2. ✅ **Grafo de prerrequisitos** (#1) — ADR-005.
3. **Repetición espaciada** (#2) — retención, sinergia con el grafo. ← *siguiente*
4. **Misconceptions** (#3) → **"por qué me equivoqué"** (#5) — diagnóstico fino del error.
5. **Explicabilidad** (#4) + **Dashboard** (#6) — capas de presentación, bajo esfuerzo.
6. **Calibración de confianza** (#7) — cuando se quiera adaptar por confianza.
7. **Grabaciones** — solo tras validar el core con datos de outcome.

---

## Próximo entregable sugerido

Aterrizar el **grafo de prerrequisitos** en concreto antes de que el modelo genere nada:
representación (agregado vs. metadata), origen de las aristas (docente / inferido / híbrido) y cómo el
`PedagogicalEngine` lo consulta para remediar el prerrequisito y no el síntoma. Es la feature con más
apalancamiento y la que más decisiones de diseño arrastra.
