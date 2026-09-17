# ADR-005: Grafo de prerrequisitos como agregado curado y persistido

- **Estado:** Aceptado
- **Fecha:** 2026-09-14
- **Rama de origen:** `feature/backend`
- **Decisores:** Equipo LARIA (orquestación backend)
- **Depende de:** [ADR-004](ADR-004-adaptacion-por-senales.md) (core adaptativo cerrado, shadow mode)
- **Implementa:** feature #1 de `docs/2_ROADMAP_FEATURES.md`

## Contexto

El roadmap describe el sistema como "un GPS excelente sin mapa de carreteras" y pide construir el
grafo de prerrequisitos. La auditoría del código matiza ese diagnóstico: **el grafo ya existe**, pero
en una forma que no sostiene la feature.

Estado antes de este ADR (`domain/services/prerequisite_graph.py`):

- Las aristas viven **hardcodeadas** en un `dict` del módulo (`_DEFAULT_EDGES`, ~20 conceptos).
- `get_pedagogical_engine()` no está cacheado ⇒ se construye un `PrerequisiteGraph` nuevo **por
  request**. Las aristas que añade `extend_with_document_concepts()` se descartan al terminar: la
  auto-ampliación no persiste nada y solo afecta a la decisión en curso.
- **No hay procedencia**: una arista curricular revisada y una inferida del orden de un PDF son
  indistinguibles, y ambas pueden **bloquear** a un estudiante.
- **No hay invariante DAG** en escritura. `extend_with_document_concepts` puede crear un ciclo; solo
  se defiende al recorrer, con un `set` de visitados.
- La remediación toma `missing[:4]` en orden DFS: no necesariamente la **causa raíz** upstream.

Así que el trabajo no es "construir un grafo", es **promover el que hay** a algo con ciclo de vida,
procedencia y garantías. Esto cambia el alcance, no la prioridad.

---

## Decisión 1 — Agregado propio, no metadata en el concepto

`ConceptGraph` es un agregado (`domain/aggregates/concept_graph.py`), no una lista
`prerequisites: list[concept_id]` colgada de cada concepto.

**Motivo:** el grafo tiene su propio ciclo de vida — curación docente, aprobación de sugerencias,
versionado — independiente de los conceptos que conecta. Como metadata distribuida, la invariante
DAG no tendría dónde vivir: validar un ciclo exige ver el grafo completo, no un nodo.

Persistencia: un documento por grafo (`concept_graphs`), con bloqueo optimista por `version` igual
que `StudentProfile`. Hoy existe un único grafo, `graph_id="default"`; el campo deja la puerta a
grafos por materia o por institución sin migración.

**Consecuencia:** las semillas curriculares pasan de literal de módulo a **datos sembrados**
(`domain/catalog/prerequisite_seeds.py` → agregado). El dominio deja de tener un currículum dentro.

## Decisión 2 — Procedencia explícita: solo lo curado bloquea

Cada arista lleva `source`:

| Procedencia | Origen | ¿Puede bloquear al estudiante? |
|---|---|---|
| `CURATED` | Docente/curador, o semilla curricular revisada | **Sí** |
| `INFERRED` | Correlación / orden de aparición en un documento | **No, nunca** |

Las inferidas se guardan como **sugerencias** con `confidence`, se exponen para aprobación
(`suggestions()`) y solo gatean tras `approve()`, que las convierte en `CURATED`.

**Motivo:** es la recomendación híbrida del roadmap con un guardarraíl real. Una arista inferida del
orden de un PDF bloqueando el avance de un estudiante es un falso positivo con coste pedagógico
directo: le niega contenido por una correlación de maquetación. Inferir es barato; bloquear no.

Esto degrada a propósito `extend_with_document_concepts`: el orden de un documento ahora produce
sugerencias, no verdad.

## Decisión 3 — Invariante DAG validada en escritura

`curate()` y `suggest()` rechazan cualquier arista que cierre un ciclo
(`CyclicPrerequisiteError`), comprobando si el concepto ya es prerrequisito transitivo de su futuro
prerrequisito. `suggest()` descarta el ciclo en silencio (es una sugerencia automática, no una orden
del usuario); `curate()` levanta excepción (es una acción deliberada y merece saberse).

**Motivo:** un ciclo no es solo un problema de recorrido, es un currículum imposible: "para aprender
A necesitas B, para B necesitas A" deja al estudiante sin ninguna entrada. Defenderse al recorrer
esconde el dato corrupto; rechazar en escritura lo impide.

## Decisión 4 — La remediación apunta a la causa raíz, no al primer hueco

`PrerequisiteGate` ya no devuelve los primeros N prerrequisitos que faltan. Devuelve los **más
upstream**: los huecos que no tienen, a su vez, ningún prerrequisito con mastery insuficiente.

Ejemplo: si falla `matrices` y faltan `variable`, `ecuación` y `ecuaciones lineales`, remediar
`ecuaciones lineales` es tratar el síntoma. La raíz es `variable`. Eso es exactamente la diferencia
entre tutor reactivo y tutor diagnóstico que el roadmap pone como tesis de la feature.

## Decisión 5 — El motor lee, el servicio escribe

`PedagogicalEngine.select()` es sincrónico y puro: recibe el grafo ya cargado como parámetro y
**no lo muta**. Cargar y guardar (incluidas las sugerencias derivadas de un documento) es
responsabilidad de la capa de aplicación, que es async y tiene acceso al repositorio.

**Motivo:** hoy el motor mutaba un grafo que se tiraba al acabar el request — trabajo perdido que
además parecía persistir. Separar lectura de escritura hace visible quién puede cambiar el grafo.

---

## Consecuencias

- El grafo es editable sin desplegar código, y auditable: cada arista dice de dónde viene.
- Un estudiante nunca queda bloqueado por una arista que ningún humano aprobó.
- La remediación ataca la causa raíz, que es la promesa de la feature.
- Coste: una lectura del grafo por turno de tutoría (un documento pequeño, cacheable más adelante).
- `PrerequisiteGraph` (servicio con el dict hardcodeado) desaparece; `PrerequisiteGate` pasa a
  operar sobre el agregado.

## Fuera de alcance de este ADR

- Endpoints de curación docente (CRUD de aristas) y el dashboard del roadmap #6: la API se añade
  sobre este agregado, no lo condiciona.
- Inferencia de aristas por correlación de mastery: aquí solo queda la vía `INFERRED` abierta y el
  flujo de aprobación. El detector estadístico es trabajo aparte.
- Caché del grafo. Se mide primero si la lectura por turno molesta.
