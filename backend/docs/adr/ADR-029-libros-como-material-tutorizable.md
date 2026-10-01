# ADR-029: Libros como material tutorizable

- **Estado:** Aceptado
- **Fecha:** 2026-10-01
- **Rama de origen:** `feature/backend`
- **Decisores:** Equipo LARIA (orquestación backend)

## Contexto

"Subir un libro y volverlo contenido tutorizable" fallaba en tres puntos.
Los tres se verificaron contra el modelo real.

1. **Análisis.** Se mandaba el texto entero en una llamada. Un libro de unas 700
   páginas daba 301 204 tokens contra un máximo de 128 000:
   `context_length_exceeded`, y el estudiante veía "El servicio de IA no está
   disponible".
2. **Contexto del tutor.** Se tomaban los párrafos con el concepto LITERAL o, si
   no había coincidencia, los tres primeros. Además, muchos PDF no separan
   párrafos con línea en blanco, así que el "párrafo" era el libro entero
   recortado a 2500 caracteres. Una duda del capítulo 16 recibía la portada.
3. **Conceptos sesgados.** Tras arreglar (1), la lista de conceptos quedó
   dominada por el capítulo 1. El motor decide el foco con esa lista, así que
   el tutor añadía "volviendo a la célula…" a una pregunta sobre Mendel, y el
   quiz salía con 5 de 6 preguntas del capítulo 1.

## Decisión

- **Análisis por secciones** cuando el texto pasa de 300 000 caracteres:
  - hasta 16 secciones cortadas en saltos de línea; un resto pequeño se une a la
    anterior;
  - cada sección se analiza en paralelo (4 a la vez), con resumen y conceptos;
  - una síntesis final combina todo;
  - una sección que falla no tumba el análisis.
- **Conceptos que cubren todas las secciones:**
  - se ofrecen al modelo por turnos (el 1.º de cada sección, luego el 2.º…), no
    por frecuencia global;
  - el código garantiza al menos el concepto principal de cada sección, aunque
    el modelo vuelva a sesgarse;
  - hasta 40 conceptos por libro.
- **Contexto por relevancia**, determinista y sin llamadas al modelo:
  - el texto se trocea en fragmentos de unos 900 caracteres, haya o no párrafos;
  - cada fragmento se puntúa por las palabras de la pregunta y del foco, pesadas
    por lo raras que son en el documento ("capítulo", que aparece en cada
    página, no decide);
  - se toman los mejores en el orden del documento;
  - el índice de fragmentos se cachea por documento;
  - presupuesto: 5000 caracteres para responder; 8000 para un quiz, repartidos
    por todo el documento si no hay foco.

## Verificación

- Tests: secciones, síntesis, sección fallida, cobertura de secciones, troceo
  sin líneas en blanco, que la pregunta trae su capítulo y no el principio,
  reparto para el quiz.
- Contra el modelo real, un libro de 984 000 caracteres:
  - se analizó en 20 s, con conceptos de los 4 bloques del libro;
  - "¿Qué dicen las leyes de Mendel?" se respondió con el capítulo 16, sin
    desviarse;
  - el quiz de 6 preguntas cubrió célula, fotosíntesis, Mendel y Darwin.

## Límites

- **Costo:** un libro de ~1 M de caracteres son ~17 llamadas en el análisis (una
  sola vez por documento).
- **El análisis es síncrono:** el cliente espera unos 20-30 s con un libro
  grande.
- **Recuperación léxica, sin embeddings:** una pregunta con palabras muy
  distintas a las del libro puede no encontrar su fragmento.
- **PDF escaneados:** siguen sin leerse; es la fase de imágenes, pendiente.
