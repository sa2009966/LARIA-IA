# ADR-018: El tutor recuerda la conversación, pero no decide con ella

- **Estado:** Aceptado
- **Fecha:** 2026-09-25
- **Rama de origen:** `feature/backend`
- **Decisores:** Equipo LARIA (orquestación backend)
- **Se apoya en:** invariante 4 del repo (un turno es una observación), [ADR-011](ADR-011-calidad-de-la-evidencia.md)

## Contexto

Los mensajes de cada chat se guardan en la base desde el principio (`chats`, un
documento por conversación con sus mensajes). Pero el router llamaba al tutor así:

```python
response = await tutor.answer(
    document_id=chat.document_id,
    question=body.content,       # solo el mensaje actual
    student_id=UUID(current_user_id),
)
```

El historial estaba a una línea y **nadie se lo pasaba al modelo**. Cada turno se
respondía como si fuera el primero. En una prueba contra producción:

> **Estudiante:** Me llamo Alex y quiero aprender historia de Roma
> **Estudiante:** ¿Cómo me llamo y qué tema quería aprender?
> **Tutor:** No tengo acceso a información personal sobre ti.

Y era más grave desde el ADR-017, porque el tutor empezó a *preguntar* ("¿qué parte
te interesa?"). La respuesta del estudiante —"las guerras"— llegaba sola y sin
referente.

## Decisión

### 1. El tutor recibe la conversación reciente

El router toma el historial **antes** de añadir el mensaje actual y lo pasa al
tutor. Viaja por los dos caminos (con material y sin él) y por las dos formas de
respuesta (normal y streaming), hasta el prompt, donde va como transcripción antes
de la pregunta actual.

### 2. Da continuidad al lenguaje; no decide la pedagogía

Esta es la decisión que importa. El historial **no entra en la pregunta**: viaja
aparte y solo lo lee el modelo al redactar.

Si entrara en la pregunta, pasaría por la detección de señales y de conceptos. Un
"no entiendo" de hace tres turnos se volvería a contar como señal de dificultad en
este turno, en el siguiente y en todos los demás. El perfil registraría una
dificultad que el estudiante ya superó. Es exactamente lo que prohíbe la invariante
4: un turno es **una** observación.

La pedagogía se sigue decidiendo con la evidencia. La conversación solo sirve para
saber a qué se refiere el estudiante.

### 3. Tiene tope

Los 8 últimos mensajes, 4000 caracteres en total y 700 por mensaje. Si no cabe, se
sacrifica lo más antiguo: para dar continuidad importa lo último que se dijo. Sin
tope, un chat largo se comería el presupuesto de tokens de cada respuesta.

### 4. Solo diálogo

Entran los mensajes del estudiante y del tutor. Los `system` —notas como "📎 Subí
el archivo" y avisos de error— quedan fuera: un "no pude generar una respuesta" en
la memoria solo confundiría al modelo.

### 5. La conversación forma parte de la clave de caché

El caché de respuestas usa como clave un hash del prompt, y el historial ya está
dentro del prompt. Así "las guerras" hablando de Roma y "las guerras" hablando de
Grecia no comparten respuesta cacheada.

## Consecuencias

- El tutor puede sostener un diálogo: recordar el nombre, el tema, lo ya explicado,
  y entender respuestas cortas a sus propias preguntas.
- Cada turno cuesta más tokens de entrada, hasta ~1000 más con el tope actual.
- El caché acierta menos. Antes, la misma pregunta aislada se servía cacheada en
  cualquier chat; ahora solo si la conversación previa es igual. Es correcto: la
  respuesta cacheada muchas veces no era la adecuada para esa conversación.

## Fuera de alcance

- **Memoria entre chats.** Lo que el tutor sabe del estudiante entre conversaciones
  es el perfil —mastery, nivel, señales—, no el texto de chats anteriores.
- **Resumir conversaciones largas** en vez de truncarlas. Con el tope actual no
  hace falta; si los chats crecen mucho, es el siguiente paso.
