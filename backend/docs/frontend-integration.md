# Guía de integración para el cliente web

> Para quien desarrolla el frontend. Todo lo de aquí está verificado contra el backend real:
> las respuestas de ejemplo son capturas del flujo, no maquetas.
>
> Verificación ejecutable: [`scripts/smoke_frontend_contract.py`](../scripts/smoke_frontend_contract.py).

## Por qué esta guía

El cliente actual llama a OpenAI por su cuenta (`app/api/chat`) y **genera y califica los quizzes**
en sus propias rutas (`app/api/quizzes`). Eso tiene tres consecuencias medidas:

1. **Se paga el tutor dos veces y se muestra la peor respuesta.** `POST /chats/{id}/messages` ya
   genera la respuesta del tutor —con decisión pedagógica, perfil y evidencia— y después el cliente
   pide otra a `gpt-3.5-turbo` con el historial crudo, que es la que enseña.
2. **Las respuestas correctas viajan al navegador.** La ruta propia devuelve `correct_answer` y
   califica comparando contra lo que el propio cliente le manda: cualquiera saca 10/10.
3. **Nada llega al perfil.** Sin `POST /quizzes/{id}/attempts` no hay evidencia, así que
   `/learning/me/profile` —que la UI ya pinta— se queda vacío para siempre.

El backend ya hace las tres cosas bien. Lo que faltaba de nuestro lado era un endpoint para evaluar
desde el chat; ya existe (`POST /chats/{id}/quiz`), así que no queda ningún flujo sin cubrir.

## Los cinco cambios

| # | Quitar | Usar |
|---|--------|------|
| 1 | `app/api/chat/route.ts` | `POST /api/v1/chats/{id}/stream` (SSE) o `POST /api/v1/chats/{id}/messages` |
| 2 | `app/api/quizzes/route.ts` | `POST /api/v1/chats/{id}/quiz` |
| 3 | `app/api/quizzes/attempt/route.ts` | `POST /api/v1/quizzes/{id}/attempts` |
| 4 | Chats sin `document_id` | Vincular material al crear el chat, o `PUT /api/v1/chats/{id}` |
| 5 | Filtro `metadata.source !== "tutor"` | Renderizar el mensaje `assistant` y su `metadata` (envelope) |

Base: `https://laria-ia.onrender.com/api/v1`. Auth: `Authorization: Bearer <access_token>` en todo
salvo `/auth/*`.

## El flujo, paso a paso

### 1. Material primero

```http
POST /api/v1/documents/
{ "filename": "ecuaciones.txt", "content": "…", "subject": "Matemática" }
```

Archivos binarios (PDF, DOCX, XLSX, PPTX) van por `POST /api/v1/documents/upload` (multipart).
Después, `POST /api/v1/documents/{id}/analyze` devuelve `summary`, `key_concepts` y
`suggested_questions`.

### 2. Chat vinculado al material

```http
POST /api/v1/chats/
{ "title": "Dudas de álgebra", "document_id": "9008efa9-…" }
```

**Esto es lo que enciende el tutor.** Un chat sin `document_id` funciona, pero es conversación
libre: sin contexto del material, sin decisión pedagógica y sin evidencia. El envelope lo dice con
`payload.grounded`.

### 2.bis Nivelación: "quiero aprender X"

Cuando el estudiante dice que quiere aprender algo —**no hace falta que haya subido
nada**— el tutor puede nivelarlo antes de enseñarle. Son **rondas**: una básica y,
si la aprueba, una avanzada. Al final queda guardado su nivel en ese tema.

```
falla la ronda base            → básico
aprueba la base, falla la 2ª   → intermedio
aprueba las dos                → avanzado
```

**Pedir una ronda.** Siempre la misma llamada; el backend sabe cuál toca:

```http
POST /api/v1/quizzes/diagnostic
{ "topic": "ecuaciones" }
```

La primera vez devuelve la ronda **base**: 6 ítems, 4 fáciles y 2 medios. Si ya
superó lo básico, la **avanzada**: 8 ítems, 3 medios y 5 difíciles. **No mandes la
ronda**: el cliente no lleva estado.

```json
{
  "id": "…",
  "document_id": null,
  "topic": "ecuaciones lineales",
  "topic_label": "Ecuaciones",
  "questions": [ … ]
}
```

`topic` es la **clave** del tema: sin tildes a propósito, para que "Electrónica" y
"electronica" sean el mismo. **Para mostrar, usa `topic_label`**, que es lo que
escribió el estudiante con sus tildes.

**Responderla.** Como cualquier quiz, y la respuesta trae el veredicto:

```http
POST /api/v1/quizzes/{id}/attempts
{ "answers": { "0": "B", "1": "D", … } }
```

```json
{
  "score": 60, "total_points": 60,
  "placement": {
    "topic": "ecuaciones lineales",
    "topic_label": "Ecuaciones",
    "round": "base",
    "level": "intermedio",
    "passed": true,
    "has_next_round": true
  }
}
```

**`has_next_round` decide el siguiente paso.** Si es `true`, ofrece la siguiente
ronda llamando otra vez a `/diagnostic` con el mismo tema. Si es `false`, la
nivelación terminó y `level` es el veredicto. `placement` solo aparece en rondas de
nivelación; en un quiz sobre material viene `null`.

Cuatro cosas que respetar:

1. **Ofrecer, no imponer.** Un estudiante que solo quiere una respuesta rápida no
   tiene por qué nivelarse. El patrón: responderle *y además* proponer.
2. **`document_id` viene `null`** en todo lo que sale de una nivelación —el quiz,
   el intento y su entrada en el historial—. Si tu modelo lo asume presente, rompe.
3. **Muestra `topic_label`, identifica con `topic`.** `topic` es la clave
   canónica —"ecuaciones" pasa a "ecuaciones lineales", y sin tildes—; es con la
   que se guarda el nivel. `topic_label` es para pintar. En el perfil,
   `level_by_topic` y `topic_labels` comparten claves.
4. **No es un examen.** Quedar en `básico` no es suspender: es el dato que hace que
   el resto de la sesión se ajuste. Presentarlo así cambia cómo lo vive.

**Por qué importa:** sin nivelar, el motor necesita cinco turnos para empezar a
adaptarse y siete aciertos por concepto para dar algo por dominado.

### 3. Turno de tutoría

```http
POST /api/v1/chats/{chat_id}/messages
{ "role": "user", "content": "¿cómo resuelvo 2x + 3 = 7?" }
```

> **`role: "user"` no es "añadir un mensaje": es pedir un turno.** Dispara la llamada al modelo,
> escribe evidencia en el perfil del estudiante y reinicia su reloj de interacción —el mismo del que
> salen `long_explanation_abandonment` y `attention_span`—. Una nota decorativa ("📎 Subí el
> archivo") mandada así se convierte en un turno medido y sesga las señales sin que se note.
>
> **Para cualquier mensaje que no deba provocar respuesta, usa `role: "system"`.** Se guarda en el
> chat y no pasa nada más: ni modelo, ni evento, ni perfil tocado. Cómo lo pintes en la UI es cosa
> tuya; el `role` solo decide si hay turno.

Devuelve **el chat completo**: tu mensaje y el del tutor ya persistidos. El mensaje `assistant`
trae el envelope en `metadata`:

```json
{
  "type": "explanation",
  "emotion": "encouraging",
  "payload": {
    "content": "Restas 3 en ambos lados y divides entre 2.",
    "grounded": true,
    "intent": "general",
    "mode": "explain",
    "difficulty": "medium",
    "cognitive_style": "simple",
    "focus_concepts": ["variable", "ecuacion"],
    "session_step": "introduce",
    "practice_before_advance": false,
    "chunk_explanation": false
  }
}
```

No hace falta llamar a ningún modelo desde el cliente: ese texto **es** la respuesta del tutor.

**Con streaming** (recomendado para la UX de escritura):

```http
POST /api/v1/chats/{chat_id}/stream
{ "role": "user", "content": "…" }
```

Server-Sent Events en este orden: `thinking` → `token` (n veces) → `envelope` → `done`. El evento
`envelope` trae el mismo objeto de arriba; el mensaje queda persistido igual que en el path normal.

### 4. Evaluar lo que se estudió

```http
POST /api/v1/chats/{chat_id}/quiz?num_questions=5
```

Genera el cuestionario **sobre el documento vinculado al chat**. La respuesta no incluye las
respuestas correctas, a propósito:

```json
{
  "id": "40d8443a-…",
  "document_id": "9008efa9-…",
  "questions": [
    { "index": 0, "text": "Si 2x + 3 = 7, ¿cuánto vale x?",
      "options": { "A": "2", "B": "5", "C": "7", "D": "1" }, "difficulty": "medium" }
  ],
  "total_points": 10,
  "created_at": "2026-09-18T21:20:07Z"
}
```

Si el chat no tiene material vinculado responde **422** con un mensaje accionable. No es un fallo:
es que evaluar sin material sería corregir contra nada.

### 5. Enviar el intento (lo califica el servidor)

```http
POST /api/v1/quizzes/{quiz_id}/attempts
{ "answers": { "0": "A" } }
```

```json
{
  "attempt_id": "5a948d5e-…", "quiz_id": "40d8443a-…", "score": 10, "total_points": 10,
  "questions": [
    { "index": 0, "text": "…", "selected": "A", "correct_answer": "A", "is_correct": true }
  ],
  "completed_at": "2026-09-18T21:20:07Z"
}
```

Aquí —y solo aquí— aparecen las respuestas correctas: después de calificar. Ojo: `score` va en
**puntos**, no en aciertos.

### 6. El perfil se llena solo

```http
GET /api/v1/learning/me/profile
GET /api/v1/learning/me
```

Justo después del intento:

```json
[{ "concept_key": "variable", "attempts": 1, "mastery": 1.0,
   "effective_mastery": 0.93, "confidence": 0.08, "error_streak": 0 }]
```

`effective_mastery` es el mastery con curva de olvido: baja solo con el tiempo. Esa es la cifra a
mostrar como "lo que domina hoy". `/learning/me` añade historial y recomendaciones ya priorizadas.

## El envelope, para renderizar

> Contrato completo, con un ejemplo real por cada tipo y las reglas de degradación:
> [`envelope-contract.md`](envelope-contract.md). Aquí va solo el resumen.

| Campo | Valores | Qué hacer |
|-------|---------|-----------|
| `type` | `answer`, `explanation`, `hint`, `quiz`, `celebration`, `error` | Elegir componente. `hint` es andamiaje (destacar), `celebration` es un hito real: el estudiante acaba de dominar un concepto y se reconoce **una sola vez** |
| `emotion` | `calm`, `encouraging`, `patient`, `celebratory` | Tono del avatar/UI |
| `payload.grounded` | `true`/`false` | `false` ⇒ es chat libre: no prometas tutoría adaptativa; buen sitio para invitar a subir material |
| `payload.celebrated_concept` | string (solo con `type: celebration`) | Qué concepto se logró |
| `payload.mode` / `difficulty` / `cognitive_style` | | Metadatos de la decisión; útiles para depurar o mostrar el "por qué" |
| `payload.chunk_explanation`, `practice_before_advance` | bool | Orquestación sugerida: trocear la explicación, pedir práctica antes de avanzar |

El envelope es **determinista**: lo decide el dominio, no el modelo.

## Errores

| Código | Significado | Qué mostrar |
|--------|-------------|-------------|
| `401` | Token ausente, inválido o usuario inactivo | Reautenticar |
| `404` | No existe **o** no es tuyo (ownership) | "No encontrado", sin filtrar cuál de los dos |
| `422` | Validación, o quiz sin material vinculado | El `detail` viene listo para mostrar |
| `429` | Rate limit (5–30 req/min según ruta) | Reintentar con backoff; `Retry-After` en la cabecera |
| `502` | Falló el proveedor de IA | "No pude generar esto ahora"; reintentable |
| `503` | `/ready` degradado | El backend está sin base de datos |

## Antes de integrar, dos avisos operativos

- **Arranque en frío:** el plan free de Render duerme el servicio; el primer request tras inactividad
  puede tardar ~20-25 s. Necesitas un estado de carga honesto y un timeout generoso en el primer
  intento de cada sesión.
- **Persistencia:** hasta que se complete la fase 1 del [plan de corrección](4_PLAN_CORRECCION.md),
  el despliegue corre en memoria y los datos se borran en cada reinicio. No es tu integración: es
  configuración nuestra.

## Comprobarlo tú mismo

```bash
python backend/scripts/smoke_frontend_contract.py --base-url https://laria-ia.onrender.com
```

Recorre este mismo flujo e imprime el mastery antes y después del intento. Si termina con
*"El lazo está cerrado"*, la integración que acabas de leer funciona de punta a punta.

Catálogo completo de endpoints: [`endpoints.md`](endpoints.md).
