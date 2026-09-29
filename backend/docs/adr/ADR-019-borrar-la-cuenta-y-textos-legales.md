# ADR-019: Borrar la cuenta de verdad, y textos legales escritos desde el backend

- **Estado:** Aceptado
- **Fecha:** 2026-09-28
- **Rama de origen:** `feature/backend`
- **Decisores:** Equipo LARIA (orquestación backend)
- **Matiza:** invariante 1 del repo (el perfil tiene un solo escritor)

## Contexto

Al escribir la política de privacidad había que responder a una pregunta
concreta: si un estudiante pide borrar su cuenta, ¿se borran sus datos? No se
borraban. El único `DELETE /users/{id}` era de administrador y solo marcaba la
cuenta como inactiva. Perfil, chats, documentos, originales en R2, intentos e
interacciones se quedaban para siempre.

Eso deja dos opciones malas para el texto legal: prometer un borrado que no existe
o decir que no se pueden borrar los datos. La mayoría de las leyes de datos
personales de la región reconocen el derecho a la supresión.

## Decisión

### 1. `DELETE /users/me` borra la cuenta y todo lo de esa persona

Documentos (por su propio servicio, que ya borraba en cascada sus quizzes,
intentos, interacciones, sesiones y el original en R2), nivelaciones y todo lo que
no cuelga de un documento, chats, rutas de aprendizaje, el perfil, los eventos
antiguos del outbox y, al final, el usuario.

- **Pide la contraseña** aunque la petición ya lleve token: un token robado no
  debe bastar para destruir una cuenta. Límite de 5 intentos por minuto, para que
  no sirva para adivinarla.
- **La cuenta se borra la última.** Si algo falla a mitad, la persona puede volver
  a entrar y repetirlo; cada paso borra lo que encuentre, así que repetir es seguro.

### 2. Segunda excepción a la invariante 1

El perfil lo escribe solo el projector. Borrar la cuenta lo borra desde
`AccountService`. Es deliberado, como la excepción de `DocumentService.delete`:
no escribe evidencia, la elimina junto con la persona.

### 3. Los textos legales los escribe el backend

Términos, privacidad y cookies viven en `src/interfaces/legal/*.md` y se sirven
en `GET /legal/{slug}`. El cliente solo los pinta.

Motivo: describen lo que el backend hace con los datos —qué guarda, en qué
proveedor, cuánto tiempo, cómo se borra—. Escritos en el frontend, podrían
contradecir al sistema sin que nadie lo notara. Aquí hay tests que fallan si el
sistema deja de cumplir lo que el texto afirma: que el servidor no instala
cookies y que el borrado de cuenta existe.

### 4. Lo que el código no sabe queda marcado

Responsable, contacto, país, edad mínima y la cláusula de responsabilidad van
como `[[COMPLETAR: …]]`. El endpoint los enumera en `pendiente` y devuelve
`completo: false` hasta que no quede ninguno. Publicar un texto legal con huecos
es peor que no publicarlo.

## Consecuencias

- Un estudiante puede ejercer su derecho a borrar sin depender de nadie.
- Lo que no se borra se dice: las respuestas en caché caducan solas en un máximo
  de 7 días, y los registros del proveedor de alojamiento no contienen el
  contenido de los mensajes.
- **Pendiente, fuera de este ADR:** registrar qué versión de los términos aceptó
  cada persona al registrarse, y la política de menores (hoy el registro no pide
  la edad).

## Nota

Estos textos son un borrador fiel al sistema, **no asesoramiento legal**. Antes de
publicarlos debe revisarlos alguien con conocimiento de la legislación aplicable.
