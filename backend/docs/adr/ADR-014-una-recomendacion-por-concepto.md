# ADR-014: Una recomendación por concepto, y lo que bloquea se dice

- **Estado:** Aceptado
- **Fecha:** 2026-09-23
- **Rama de origen:** `feature/backend`
- **Decisores:** Equipo LARIA (orquestación backend)
- **Modifica el contrato de salida de:** [ADR-003](ADR-003-mastery-forgetting-prereqs.md) (`RecommendationEngine`)
- **Implementa:** fase F de [`5_PLAN_MOTOR_ADAPTATIVO.md`](../5_PLAN_MOTOR_ADAPTATIVO.md)

## Contexto

`RecommendationEngine` tenía lógica fina —prioriza por brecha de olvido, penaliza
baja confianza, multiplica ×1.2 si el concepto bloquea un prerrequisito— y **nunca
se había ejercitado con un perfil realista**: ocho referencias en un solo archivo
de tests, todas con perfiles de dos o tres conceptos construidos a mano.

Al correrlo contra las cuentas semilla de la fase E salió esto (captura real, no
maqueta):

```
=== carla_demo (10 recomendaciones) ===
   1.79  forgotten        Repasa antes de que se olvide: funciones.
   1.79  forgotten        Repasa antes de que se olvide: grafica de funciones.
   1.79  forgotten        Repasa antes de que se olvide: funcion lineal.
   0.98  review_priority  Prioridad de repaso: funciones.
   0.93  review_concept   Repasa: funciones.
   0.81  review_priority  Prioridad de repaso: funcion lineal.
   0.81  review_priority  Prioridad de repaso: grafica de funciones.
   0.77  review_concept   Repasa: funcion lineal.
   0.77  review_concept   Repasa: grafica de funciones.
   0.55  study_time       Tiempo sugerido de estudio hoy: ~81 minutos.
```

Diez recomendaciones sobre **tres conceptos**. Y `bruno_demo` —el estudiante que
el gate manda secuenciar porque falla el orden de las operaciones— recibía dos
filas, ninguna de las cuales mencionaba que estaba bloqueado.

## Decisión

### 1. La deduplicación es por concepto, no por `(kind, concepto, documento)`

Un concepto aparece **una vez**, con su recomendación de mayor prioridad. Las
recomendaciones sin concepto (documento, tiempo de estudio) siguen distinguiéndose
por `(kind, documento)`.

`forgotten`, `review_priority` y `review_concept` no eran tres recomendaciones:
eran tres redacciones del mismo dato. Con la clave anterior, las tres competían por
el tope de diez y dejaban fuera la variedad —`mastered`, `next_topic`, el nivel de
documento— que es lo que hace útil una lista.

### 2. `review_concept` deja de emitirse

Es `review_priority` con otra redacción y prioridad ×0.95, así que con la clave
nueva perdía siempre. Emitir una rama inalcanzable es deuda disfrazada de opción.
El `kind` sigue siendo válido en el contrato; simplemente ya no se produce.

### 3. Lo que un concepto bloquea se dice, no se multiplica en silencio

Un concepto débil que impide avanzar valía `×1.2` de prioridad y **ningún mensaje**.
Ahora emite `kind="unblock"`, nombrando hasta dos conceptos que desbloquea:

> *"Repasa jerarquia de operaciones: es lo que te está frenando en resolver ecuacion."*

Es la misma regla que el ADR-006 fijó para el gate —nunca desviar en silencio—
aplicada al plan de estudio. A un estudiante al que se le pide repasar algo que no
preguntó se le debe la razón.

### 4. Lo que bloquea se busca **hacia adelante en el grafo**

`_is_blocking_prereq` recorría `profile.mastery_by_concept`, así que un hueco solo
contaba como bloqueante si el concepto bloqueado **ya tenía evidencia**. Eso
excluye justamente el caso que importa: quien falla el orden de las operaciones
todavía no ha intentado despejar una ecuación — por eso está bloqueado.

Ahora se consultan los sucesores del concepto en el grafo. Es la información para
la que existe el grafo, y el motor no la estaba usando.

### 5. El tiempo sugerido se calcula sobre la lista final

Se sumaba antes de deduplicar, contando el mismo concepto varias veces. La cifra
que veía el estudiante estaba inflada por duplicados.

## Consecuencias

- La lista baja de 10 filas a 3–6 en los perfiles semilla, y **eso es la mejora**:
  son conceptos distintos en vez de repeticiones. `bruno_demo` pasa de dos filas
  redundantes a una que explica su bloqueo.
- `unblock` es un `kind` nuevo. Los clientes deben tratar valores desconocidos con
  un caso por defecto, como ya exige el contrato del envelope.
- Buscar sucesores cuesta una evaluación de gate por sucesor. Medido sobre los
  perfiles semilla con el grafo de 57 conceptos: 2–22 ms por lista completa.
- Depende del grafo: un currículum somero hace que `unblock` casi nunca se emita.
  Esta decisión y el enriquecimiento del grafo (fase E) se sostienen mutuamente.

## Fuera de alcance

- **Redactar las recomendaciones con el LLM.** Son plantillas deterministas a
  propósito, por la misma razón que el ADR-013: auditables y sin que nadie tenga
  que revisar qué se inventó el modelo sobre el estudiante.
- **Ordenar por currículum** en vez de por prioridad numérica. Hoy tres conceptos
  olvidados con la misma brecha empatan y el desempate es arbitrario. Se nota poco
  y arreglarlo pide decidir qué es "antes" en un DAG.
