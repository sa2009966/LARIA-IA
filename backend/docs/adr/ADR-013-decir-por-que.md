# ADR-013: Decir por qué — la adaptación se explica o no existe

- **Estado:** Aceptado
- **Fecha:** 2026-09-22
- **Rama de origen:** `feature/backend`
- **Decisores:** Equipo LARIA (orquestación backend)
- **Depende de:** [ADR-004 · Decisión 5](ADR-004-adaptacion-por-senales.md) (arbitraje)
- **Implementa:** P5 del plan de experiencia pedagógica · fase C de [`5_PLAN_MOTOR_ADAPTATIVO.md`](../5_PLAN_MOTOR_ADAPTATIVO.md)

## Contexto

El sistema adapta la forma de la respuesta —largo, ejemplos, cuánto pregunta— a partir de señales de
conducta, y hasta ahora no lo decía. Eso tiene dos costes, uno para el estudiante y otro para
nosotros:

- **Para el estudiante:** una adaptación que no se explica es indistinguible de la arbitrariedad, o
  peor, de un juicio. "¿Por qué a mí me responde corto?" no tiene respuesta visible.
- **Para nosotros:** cuando se apague el modo sombra y una respuesta salga rara, la pregunta será
  "¿falló la señal, la política o el arbitraje?". Sin una frase que lo diga, se depura adivinando
  contra un LLM.

Por eso esta fase va **antes** de encender la adaptación, y no después como adorno.

## Decisión

`domain/services/adaptation_explainer.py`: función pura que recibe los parámetros **efectivos** (ya
arbitrados), las señales del perfil y los vetos del composer, y devuelve una frase en lenguaje
natural. Viaja en `payload.explanation` del envelope.

Cuatro reglas la mantienen honesta:

### 1. Solo se explica lo que se aplicó

La frase se construye desde los parámetros efectivos, no desde lo que la política pidió. Y en **modo
sombra** —donde el fragmento no llega al prompt— `payload.explanation` va **vacío**: prometerle al
estudiante "te doy más ejemplos" mientras el prompt no lo pide sería mentirle.

La explicación sí se **registra** siempre (`adaptacion_explicada aplicada=false texto=…`), porque su
otra función es depurar, y ahí la queremos desde el primer día.

### 2. Se nombra la conducta, no la métrica

*"Voy al grano porque las explicaciones largas se te hacen cuesta arriba"*, no *"tu
`long_explanation_abandonment` es 0.91"*. El estudiante no tiene por qué conocer nuestras métricas, y
un número sin contexto sobre uno mismo asusta más que informa.

### 3. Sin señal no se afirma la causa

Si un parámetro tiene valor no-default pero no hay señal que lo respalde, **no se genera frase**. Es
la misma regla que el ADR-007 aplicó al mastery: sin evidencia no se afirma nada. A un estudiante sin
historial no se le inventa un porqué; se le devuelve cadena vacía y la UI no muestra nada.

### 4. Como mucho dos motivos

El tutor explica, no rinde cuentas. Con seis señales activas la frase tendría seis cláusulas y nadie
la leería. Se cortan a dos y se unen con "y".

### Los vetos son la mitad interesante

Lo que el arbitraje **impidió** explica tanto como lo que la política pidió: *"no acorto la
explicación porque estamos construyendo la base"* le dice al estudiante que hay una decisión
pedagógica detrás, no una preferencia de estilo. Por eso `compose_plan` devuelve los vetos: no era
telemetría, era la materia prima de esta frase.

## Consecuencias

- El envelope gana `payload.explanation`, opcional como todo lo demás: ausente si no hubo nada que
  adaptar o si la adaptación no se aplica.
- Las frases son plantillas fijas, no generadas por el modelo. Determinista y auditable: el mismo
  perfil produce la misma explicación, y nadie tiene que revisar qué "se inventó" el LLM sobre el
  estudiante.
- Añadir una señal nueva a la política obliga a añadirle su frase, o la adaptación quedará muda para
  ese caso. Es deliberado: el coste de adaptar sin poder explicarlo sube.

## Fuera de alcance

- **Explicar la decisión pedagógica** (por qué `SCAFFOLD`, por qué este foco). Es otra frase, con
  otra materia prima —evidencia, no señales—, y toca el terreno delicado de hablarle al estudiante de
  sus carencias, que el ADR-006 cerró a propósito.
- **Traducción**: las frases están en español, como el resto del producto.
