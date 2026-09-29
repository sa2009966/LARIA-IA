# ADR-015: Ofrecer práctica es forma, no orquestación — y se enciende la adaptación

- **Estado:** Aceptado
- **Fecha:** 2026-09-23
- **Rama de origen:** `feature/backend`
- **Decisores:** Equipo LARIA (orquestación backend)
- **Modifica:** [ADR-004 · Decisión 3](ADR-004-adaptacion-por-senales.md) (las dos familias de parámetros)
- **Se apoya en:** [ADR-006](ADR-006-oferta-vs-bloqueo.md) (ofrecer, no bloquear)
- **Implementa:** fase D de [`5_PLAN_MOTOR_ADAPTATIVO.md`](../5_PLAN_MOTOR_ADAPTATIVO.md)

## Contexto

El ADR-004 repartió los parámetros de adaptación en dos familias: **prompt-shaping**
(texto aditivo al system prompt) y **control-flow** (orquestación alrededor de la
generación). La segunda familia tenía dos miembros, `practice_before_advance` y
`chunk_explanation`, y un problema: **nadie los consumía**. Se calculaban, se
serializaban en el envelope y ahí morían. Ni el backend actuaba sobre ellos ni el
cliente los leía.

Eso bloqueaba encender la adaptación. No se puede apagar el modo sombra dejando
dentro del contrato dos campos que prometen un comportamiento que no ocurre.

La salida obvia era implementar la orquestación: si `practice_before_advance` está
activo y el `session_step` va a avanzar, forzar un turno de práctica. **Y ahí está
el problema**, que solo se ve al escribirlo: forzar un turno de práctica antes de
dejar avanzar **es bloquear**. El ADR-006 ya decidió, para el gate de
prerrequisitos, que este sistema ofrece y no bloquea, porque bloquear con evidencia
imperfecta le quita al estudiante la respuesta que vino a buscar. No hay razón para
que la política de adaptación —que corre sobre señales *más* débiles que la
evidencia del gate— tenga licencia para hacer lo que al gate se le negó.

## Decisión

### 1. `practice_before_advance` pasa a prompt-shaping, como oferta

El parámetro no desaparece: cambia de familia y de forma. En vez de orquestar un
turno, añade una frase al prompt:

> *"Cierra ofreciendo un ejercicio breve para practicar antes de avanzar."*

El estudiante **recibe su respuesta** y además la invitación a practicar. Eso
implementa la intención de la señal (`practice_seeking`: pide ejercicios) sin
secuestrar el turno, y tiene un consumidor real desde el primer día.

La señal que lo dispara, su umbral y su explicación no cambian. Lo único que cambia
es dónde se aplica.

### 2. `chunk_explanation` se queda en control-flow, y se documenta como pista de cliente

Trocear una explicación es una decisión de **render**: el backend no puede trocear
lo que ya escribió, y en streaming los tokens ya salen por partes. Solo quien pinta
puede aplicarlo. Sigue viajando en `payload` y el contrato ahora dice explícitamente
que es una pista para el cliente, no algo que el servidor haya hecho.

Es la diferencia honesta con el caso anterior: `chunk_explanation` no tiene
consumidor **todavía**, pero su consumidor correcto es el cliente y está
documentado. `practice_before_advance` no tenía consumidor correcto en ninguna parte.

### 3. Un turno que ya es práctica no ofrece práctica

`compose_plan` veta `practice_before_advance` cuando `decision.mode == PRACTICE`:
el turno entero ya es el ejercicio. Sexta regla de la tabla de precedencia, con la
misma lógica que las cinco anteriores — la pedagogía decide el fondo, la adaptación
la forma, y cuando la forma repite el fondo no es énfasis, es ruido.

### 4. `ADAPT_SHADOW_MODE` pasa a `False` por defecto

La adaptación llega al prompt y `payload.explanation` se le muestra al estudiante.
La variable **se conserva**: ponerla a `True` devuelve al modo sombra —señales
computadas, prompt intacto— sin desplegar código. Es el interruptor de emergencia,
y hay un test que falla si alguien cablea la adaptación de forma que ya no se pueda
apagar.

## Consecuencias

- El prompt de un estudiante que pide ejercicios, capturado tras el cambio:

  > *"Responde con extensión moderada. Incluye 1 ejemplo(s) concreto(s). Haz como
  > mucho una pregunta de verificación al final. **Cierra ofreciendo un ejercicio
  > breve para practicar antes de avanzar.**"*

  Y lo que se le dice al estudiante: *"Te propongo un ejercicio antes de seguir
  porque es lo que sueles pedir, y no acorto la explicación porque estamos
  construyendo la base."*

- **`ControlFlowParameters` queda con un solo campo.** Es un resultado, no un
  descuido: al mirar de cerca, casi nada de lo que parecía orquestación lo era.

- `payload.practice_before_advance` **sigue emitiéndose con el mismo nombre**, pero
  cambia de significado: antes era una orden pendiente de ejecutar; ahora informa de
  algo **ya aplicado en el prompt**, para que la UI pueda destacar el ejercicio. El
  contrato lo dice.

- Aparecen tests sobre el **prompt compuesto**, que no existían. El criterio viejo
  de la fase D —"los tests pasan con el modo sombra apagado"— se cumplía sin haber
  hecho nada, porque ningún test miraba la cadena que se manda al modelo.

## Fuera de alcance

- **Implementar el troceado en el backend.** No se puede sin cambiar el contrato de
  streaming, y el cliente lo resuelve mejor.
- **Que el tutor secuencie turnos de práctica.** Es la orquestación que se descarta
  aquí. Si algún día se quiere, necesita su propio ADR y una razón para contradecir
  al ADR-006.
