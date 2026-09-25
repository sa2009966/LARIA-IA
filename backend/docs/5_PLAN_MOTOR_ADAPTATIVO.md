# Plan — que el motor adapte, lo explique y se vea

> **Objetivo:** pasar de "el sistema mide bien" a "el sistema adapta, dice por qué, y se nota".
>
> **Alcance:** backend. El cliente web lo lleva otra persona; aquí solo entra lo que hay que
> entregarle. Sucede a [`4_PLAN_CORRECCION.md`](4_PLAN_CORRECCION.md), cuyas fases 2, 3 y 4 están
> cerradas.
>
> **Fecha:** 2026-09-22.

## Lo que ya no hay que hacer (verificado hoy contra el código)

| Se daba por pendiente | Estado real |
|---|---|
| Ciclo de quiz completo (generar → responder → evidencia) | **Hecho.** `POST /chats/{id}/quiz` + `tests/api/test_chat_evidence_loop_e2e.py` |
| `updateMany` de `preferred_explanation_style` | **Escrito.** `scripts/migrate_preferred_style.py` |
| Arrancar un primer despliegue | **Existe** y está al día; le falta la base de datos |
| "Los tests pasan con `ADAPT_SHADOW_MODE=False`" como criterio | **Ya se cumplía** antes de tocar nada. No probaba nada: ningún test cubría el prompt adaptado |

Y dos datos corregidos: el grafo semilla tenía **19 conceptos** (no ~23) —hoy son 57, ver fase E— y
la suite son **838 tests** (753 era la cifra de hace dos semanas).

---

## Fase A — Persistencia · *bloquea C, E y F* — **tuya**

Sin esto, las cuentas semilla se borran en cada spin-down y medir es imposible. Media jornada de
dashboard, el código lleva una semana listo.

1. Atlas + Upstash con la tabla de variables de [`deploy-render.md`](deploy-render.md).
2. R2 para los archivos originales (`ORIGINAL_STORAGE=r2`), verificado con `scripts/check_r2.py`.
3. `scripts/verify_deployment.py --expect-mongodb --expect-redis` en verde, y la prueba de
   persistencia en dos tiempos (`--register` → redeploy → `--login`).

**Cerrado cuando:** un usuario registrado sobrevive a un redeploy.

> **Sobre mudar las bases a un servidor propio:** la presión de los 512 MB la causaban los archivos,
> y esos se van a R2. Migrar *solo* las bases deja Mongo y Redis expuestos a internet (blanco
> automático nº 1) sin poder cerrar el firewall, porque Render free no tiene IP de salida fija.
> Si se usa el servidor, se usa entero —app + Mongo + Redis en Compose tras un proxy con TLS—, que
> es lo que [`production-checklist.md`](production-checklist.md) llama producción real, y **después
> de la demo**. Requisito innegociable: alguien que haga backups.

---

## Fase B — Arbitraje motor ↔ política — ✅ **hecha**

> Entregado: [ADR-004 · Decisión 5](adr/ADR-004-adaptacion-por-senales.md) con la tabla de
> precedencia, `domain/services/plan_composer.py` (función pura), cableado en `prepare_pedagogy` y
> 15 tests en `tests/unit/domain/test_plan_composer.py` — uno por fila de la tabla, más el que
> comprueba que el prompt real deja de contradecirse y el que falla si alguien descablea el
> arbitraje.

El problema que resolvía: `prepare_pedagogy` calculaba la decisión pedagógica y los parámetros de
adaptación **en paralelo**, y `TutorPolicy` los concatenaba sin comprobar que fueran coherentes:

```python
system = f"{system} {adaptation.to_prompt_fragment()}"
```

No es teórico. Con señales reales que producen `explanation_length=short` y
`socratic_question_rate=high`, un turno `SCAFFOLD` genera este prompt:

> *"Usa andamiaje: pista → ejemplo parcial → invitación a completar. Reduce carga cognitiva; un paso
> a la vez."* … *"Responde de forma breve: ve al grano, evita preámbulos. Guía sobre todo con
> preguntas; deja que el estudiante concluya."*

Andamiaje gradual, ve al grano y guía con preguntas, a la vez. Concatenado, eso no es andamiaje.
(Ese prompt es una captura real, reproducida con señales reales antes del arreglo.)

**La regla:** la pedagogía decide el fondo, la adaptación decide la forma, y cuando la forma
contradice al fondo **gana el fondo**.

1. Tabla de precedencia en el ADR-004 como **Decisión 5** (primero la tabla; el código sin tabla es
   adivinación).
2. `domain/services/plan_composer.py`: función pura `PedagogicalDecision + AdaptationParameters →
   parámetros efectivos + lista de vetos`.
3. Cablearlo en `prepare_pedagogy`, de modo que streaming y no-streaming consuman lo mismo.

**Cerrado cuando:** existe un test que falla si un turno `SCAFFOLD` acepta `explanation_length=short`.

---

## Fase C — Explicabilidad (`payload.explanation`) — ✅ **hecha**

> Entregado: [ADR-013](adr/ADR-013-decir-por-que.md),
> `domain/services/adaptation_explainer.py` (puro), `payload.explanation` en el envelope y 14 tests.
> La regla que lo mantiene honesto: en modo sombra la frase **no** se le muestra al estudiante —se
> registra en el log— porque prometer una adaptación que no llega al prompt es mentir.

Derivar una frase en lenguaje natural desde los parámetros efectivos y las señales que los
dispararon: *"te doy más ejemplos porque los has pedido varias veces"*.

Va **antes** de encender la adaptación, y no por estética: es el instrumento de depuración de la fase
D. Cuando algo salga raro con el modo sombra apagado, esta frase dice si falló la señal, la política
o el arbitraje. Sin ella se adivina contra un LLM.

Los vetos que devuelve el composer (fase B) son la mitad del insumo: *"no acorté la explicación
porque estabas andamiando"* es explicabilidad de primera.

**Cerrado cuando:** dos cuentas con historial distinto producen dos frases distintas y correctas.

---

## Fase D — Encender la adaptación — ✅ **hecha**

> Entregado: [ADR-015](adr/ADR-015-ofrecer-practica-no-orquestarla.md), `ADAPT_SHADOW_MODE=False`
> por defecto y 8 tests en `tests/unit/domain/test_prompt_compuesto.py`.

La decisión de producto que bloqueaba la fase se resolvió sola al intentar escribirla. Implementar
`practice_before_advance` como orquestación significa **forzar un turno de práctica antes de dejar
avanzar**, y eso es bloquear — exactamente lo que el [ADR-006](adr/ADR-006-oferta-vs-bloqueo.md) le
negó al gate de prerrequisitos. No hay razón para que la política de adaptación, que corre sobre
señales *más débiles* que la evidencia del gate, tenga licencia para hacer lo que al gate se le negó.

Así que el parámetro cambia de familia: pasa a prompt-shaping y **ofrece** en vez de orquestar.

> *"Cierra ofreciendo un ejercicio breve para practicar antes de avanzar."*

El estudiante recibe su respuesta **y** la invitación. `chunk_explanation` se queda en control-flow y
el contrato ahora dice lo que es: una pista para quien pinta, porque el backend no puede trocear lo
que ya escribió.

`ControlFlowParameters` queda con un solo campo. Es un resultado, no un descuido: casi nada de lo que
parecía orquestación lo era.

**Cerrado:** existen tests sobre el prompt compuesto, que antes no existían. El criterio viejo ("los
tests pasan con el modo sombra apagado") se cumplía sin haber hecho nada, porque ninguno miraba la
cadena que se manda al modelo. Ahora hay uno que falla si alguien cablea la adaptación de forma que
ya no se pueda apagar por variable de entorno.

---

## Fase E — Datos que hacen visible el motor — código hecho; falta correrlo contra la base

> Entregado: el grafo enriquecido (**19 → 57 conceptos**, 30 → 94 aristas),
> [`scripts/seed_demo_profiles.py`](../scripts/seed_demo_profiles.py) y 17 tests entre
> `tests/unit/domain/test_semilla_curricular.py` y `tests/scripts/`. Falta el paso 3, que **depende
> de la fase A**: sin Mongo no hay nada que migrar ni dónde sembrar.

### 1. El grafo — hecho

Tenía 19 conceptos y una sola raíz de tres niveles, así que el gate casi nunca escalaba por encima de
`INTEGRATE`: la evidencia del alumno rara vez caía sobre un prerrequisito declarado. Ahora son 57
conceptos y 94 aristas, con la columna vertebral del **álgebra escolar** —la materia de la demo— y
las ramas de cálculo y física que ya existían.

Tres criterios, escritos en el propio archivo de semillas:

1. Una arista es una afirmación pedagógica defendible en voz alta, no completitud temática.
2. **Una sola raíz** (`número entero`), para que `root_causes()` converja siempre a una base concreta.
3. Lo **procedimental** depende de la aritmética; lo conceptual, no. `resolver ecuación` necesita
   `jerarquía de operaciones` porque ahí es donde el alumno falla; `variable` no.

Dos huecos concretos que esto cierra:

- `ConceptTagger` etiquetaba ítems como `operaciones` y `constante`, conceptos **que el grafo no
  conocía**: esa evidencia se medía y no podía gatear nada. Hay un test que falla si vuelve a pasar.
- Un alias guardado con tilde (`"límites"`) nunca se encontraba, porque la búsqueda usa la clave
  plegada. `ConceptGraph` ahora pliega las claves al entrar, así que la semilla no necesita duplicar
  cada alias acentuado.

### 2. Las cuentas semilla — hecho

`min_samples_for_adaptation=5` y `has_decision_evidence` hacen —correctamente— que una cuenta nueva
**no adapte nada**. Una demo con cuentas nuevas enseña un tutor genérico.

El guion siembra tres cuentas **por eventos de dominio, a través del projector real**: el mastery, las
rachas y las señales los calcula el mismo código que corre en producción, así que los números de la
demo son los que el sistema produciría de verdad. Única excepción, marcada en el código: el estado
"olvidado" exige que haya pasado tiempo, y el tiempo no se emite como evento — se retrasa
`last_practiced_at` y nada más; el decaimiento lo sigue calculando el dominio.

| Cuenta | Qué hace visible | Lo que produce hoy |
|---|---|---|
| `ana_demo` | dominado + débil, adaptación por impaciencia | `short` + 3 ejemplos: *"Voy al grano porque las explicaciones largas se te hacen cuesta arriba…"* |
| `bruno_demo` | **bloqueado por prerrequisito** | `SEQUENCE` liderando con `jerarquía de operaciones`, y práctica antes de avanzar |
| `carla_demo` | **olvidado** (dominó hace 45 días) | `OFFER`, `long` + socrático `high`: *"…te pregunto más de lo que te cuento porque sueles llegar tú a la respuesta"* |

Un hallazgo de calibración del que nadie se había dado cuenta: la confianza de un concepto sube
**0,08 por observación** y `mastered_concepts` exige 0,55, así que **un concepto no cuenta como
dominado hasta el séptimo acierto calificado**. Con quizzes de cinco ítems, una demo corta no
enseñaría ni un concepto dominado ni una sola celebración. Está anotado en el guion, que repite ítems
para cruzar el umbral; si el umbral es el equivocado, es una decisión de producto, no un bug.

### 3. Migraciones — pendiente, depende de A

`scripts/migrate_preferred_style.py --apply` y, si hay documentos antiguos,
`scripts/migrate_document_blobs.py --apply`.

**Cerrado cuando:** `python scripts/seed_demo_profiles.py --apply` corre contra la base real y al
entrar con `ana_demo` la adaptación ya está activa.

### Lo que el grafo profundo dejó al descubierto

Con tres niveles, la causa raíz de un hueco era informativa. Con ocho, y un estudiante **sin nada
medido**, `root_causes()` devuelve siempre la raíz global: `INTEGRATE` acaba diciendo *"apoya la
explicación en número entero"* para cualquier pregunta y cualquier alumno. Un valor constante no
informa de nada.

Para `SEQUENCE` —fallo medido y repetido— atacar la raíz sigue siendo correcto y es lo que hace
bruno_demo legible. La propuesta sería **distinguir por acción**: raíz para `SEQUENCE` y `OFFER`;
prerrequisito *inmediato* para `INTEGRATE`. Toca la Decisión 4 del ADR-005, así que pide su propio
ADR y no se ha hecho aquí.

---

## Fase F — Ruta de aprendizaje de punta a punta — ✅ **hecha**

> Entregado: [ADR-014](adr/ADR-014-una-recomendacion-por-concepto.md), el motor corregido y 10 tests
> en `tests/unit/domain/test_recomendaciones.py`.

Apareció exactamente lo que se predijo, y se comprobó ejecutándolo contra las cuentas de la fase E:
`carla_demo` recibía **diez recomendaciones sobre tres conceptos** —`forgotten`, `review_priority` y
`review_concept` son tres redacciones del mismo dato— y `bruno_demo`, el estudiante que el gate manda
secuenciar, recibía dos filas sin que ninguna mencionara que estaba bloqueado.

Cuatro correcciones, razonadas en el ADR-014:

1. **Deduplicar por concepto**, no por `(kind, concepto, documento)`. Un concepto, una fila.
2. **`review_concept` deja de emitirse**: con la clave nueva perdía siempre.
3. **`unblock`**: lo que un concepto bloquea se dice en vez de valer un `×1.2` mudo —
   *"Repasa jerarquia de operaciones: es lo que te está frenando en resolver ecuacion"*.
4. **Buscar lo bloqueado hacia adelante en el grafo.** Antes se recorría `mastery_by_concept`, así
   que un hueco solo contaba como bloqueante si el concepto bloqueado ya tenía evidencia — que es
   justo lo que no pasa cuando el alumno aún no ha llegado ahí. El caso típico se perdía entero.

La lista baja de 10 filas a 3–6, y esa es la mejora: son conceptos distintos en vez de repeticiones.

**Cerrado cuando:** ~~una cuenta semilla produce al menos tres recomendaciones priorizadas, variadas
y defendibles en voz alta.~~ Cumplido para las tres cuentas.

---

## Fase G — Verificación en el entorno desplegado

No es una fase de días: es correr lo que ya existe contra el entorno real.

```bash
python backend/scripts/smoke_frontend_contract.py --base-url <url>
```

Recorre registro → material → chat vinculado → turno → SSE → quiz → intento → perfil, e imprime el
mastery antes y después. Aparecen aquí: CORS, streaming tras proxy, arranque en frío, latencia de
OpenAI y cuentas semilla que solo existían en local.

**Cerrado cuando:** el script termina con *"El lazo está cerrado"* contra el despliegue.

---

## Fase H — Mudanza al servidor propio (después de la demo)

App + Mongo + Redis en Compose, nada expuesto salvo HTTPS, backups programados. El backend no cambia:
son dos cadenas de conexión. Ver la nota de la fase A.

---

## Orden y dependencias

```
A (persistencia) ─────┬──► E (datos) ──► F (ruta) ──► G (verificación)
                      │
B (arbitraje) ──► C (explicabilidad) ──► D (encender) ──┘
```

B y C no dependen de A: son dominio puro y se pueden hacer mientras la infraestructura espera.
**E, F y G sí**: sin persistencia, las semillas se evaporan.

## Fuera del código

- Reunión con el asesor sobre el Gantt: RAG vectorial y scraping figuran como entregables y no
  existen. [`gantt-compliance.md`](gantt-compliance.md) ya tiene redactada la opción de renombrarlos
  a *"contexto documental / grounding"*, que es lo que el sistema sí hace.
- Medio domingo libre en la segunda semana. La caída de rendimiento de catorce días seguidos se paga
  justo en la semana de integración.
