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

Y dos datos corregidos: el grafo semilla tiene **19 conceptos** (no ~23), y la suite son **838 tests**
(753 era la cifra de hace dos semanas).

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

## Fase D — Encender la adaptación

1. **Decidir control-flow**, que hoy se emite sin consumidor: `chunk_explanation` es presentación y
   se queda en el envelope; `practice_before_advance` es secuencia pedagógica y sube al backend (si
   está activo y el `session_step` va a avanzar, se fuerza un turno de práctica) **o se borra del
   payload**. Emitir algo que nadie consume es deuda disfrazada de feature.
2. `ADAPT_SHADOW_MODE=false`.

**Cerrado cuando:** existen tests sobre el **prompt compuesto** —no solo sobre la política— y pasan
con el modo sombra apagado. El criterio viejo ("los tests pasan") ya se cumplía sin haber hecho nada.

---

## Fase E — Datos que hacen visible el motor · *depende de A*

1. **Poblar el grafo** de la materia de la demo. Hoy son 19 conceptos de álgebra, cálculo y física:
   con otra materia, `PrerequisiteGate` no dispara nunca y medio motor es invisible. Media jornada,
   la mejor relación coste/impacto del plan.
2. **`scripts/seed_demo_profiles.py`** — no existe nada parecido. `min_samples_for_adaptation=5`, así
   que una cuenta nueva **no adapta**: la demo necesita cuentas con historial y conceptos en los
   cuatro estados (dominado, débil, olvidado, bloqueado por prerrequisito).
3. Ejecutar `scripts/migrate_preferred_style.py --apply` y, si hay documentos antiguos,
   `scripts/migrate_document_blobs.py --apply`.

**Cerrado cuando:** una pregunta de la materia de demo dispara `OFFER` o `SEQUENCE` de forma
observable, y al entrar con una cuenta semilla la adaptación ya está activa.

---

## Fase F — Ruta de aprendizaje de punta a punta · *depende de E*

Ejercitar `RecommendationEngine` con los perfiles semilla. Tiene lógica fina —prioriza por brecha de
olvido, penaliza baja confianza, multiplica ×1.2 si el concepto bloquea un prerrequisito— y **nunca
se ha ejercitado con un perfil realista**: hoy son 8 referencias en un solo archivo de tests. Lo que
va a aparecer son recomendaciones repetidas, mensajes redundantes y prioridades que no ordenan como
esperas.

**Cerrado cuando:** una cuenta semilla produce al menos tres recomendaciones priorizadas, variadas y
defendibles en voz alta.

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
