# ADR-039: Los tramos intermedio y avanzado se investigan en internet

- **Estado:** Aceptado · **Fecha:** 2026-10-05 · **Amplía:** ADR-037 (rutas por tramos)

## Contexto
- Con los tramos (ADR-037), el temario intermedio y avanzado salía solo de lo que el
  modelo recordaba. A veces quedaba vago ("Proyectos de investigación") y no había
  forma de saber de dónde salía.
- Pidiendo el temario en JSON con búsqueda web, el modelo **inventaba URLs**
  (`https://www.uteg.edu.ec/.../Algebra-Intermedia.pdf`) y no hacía ni una cita real.

## Decisión
- **Solo se investigan los tramos `intermedio` y `avanzado`.** El básico lo cubre bien
  el modelo. Aplica al abrir un tramo y al crear una ruta para quien ya llega con ese nivel.
- **Paso 1: investigar.** `gpt-4o` (`OPENAI_MODEL_RESEARCH`) usa la herramienta
  `web_search` obligatoria (`tool_choice: required`) y responde en prosa, citando.
- **Paso 2: estructurar.** El modelo barato convierte la investigación en un temario
  JSON de 5 a 8 subtemas, cada uno con 3 a 5 ideas clave y sus fuentes **por número**.
- **Las fuentes salen solo de la búsqueda:** las citas `url_citation` y las fuentes
  consultadas.
  - Un número que no está en la lista se descarta.
  - Sin fuentes no hay temario investigado.
  - Se quitan los `utm_*` y los sitios de contenido subido por usuarios o foros:
    Reddit, Scribd, Studocu, Brainly, redes sociales…
- **Caché global** por (tema canónico, nivel), en la colección `curriculum_research`:
  se investiga una vez para todos los estudiantes. Lo que una ruta ya tiene se
  descarta al validar.
- **Si la búsqueda falla o no aporta nada nuevo**, el temario sale del modelo, como
  antes (ADR-037). Un fallo no se cachea.
- Cada módulo guarda `key_points` y `sources`. La lección recibe las ideas clave y se
  apoya en ellas (`LessonRequest.key_points`). La API las muestra en cada módulo.
- Copyright: no se copia contenido de las páginas. Se guardan ideas clave redactadas
  y enlaces, y la clase muestra las fuentes.
- A la búsqueda solo va el nombre del tema y del nivel, nunca datos del estudiante.

## Verificado
- Con la API real (2026-10-05):
  - "Ecuaciones de segundo grado", intermedio: 7 módulos con 8 fuentes (UNAM, Khan
    Academy, programas oficiales) en 20 s.
  - "Programación en Python", avanzado: 7 módulos (programación funcional,
    metaprogramación, concurrencia, testing…) con fuentes de la UOC y otros cursos,
    en 16 s.
- Tests:
  - `tests/unit/infrastructure/test_web_researcher.py`: fuentes verificadas, números
    inválidos, la forma de las dos llamadas, sin fuentes, rechazo del proveedor, la
    caché y la lección.
  - `tests/api/test_temario_investigado_e2e.py`: el tramo con fuentes, la caché entre
    estudiantes y el respaldo del modelo.

## Consecuencias
- **Latencia:** abrir un tramo intermedio o avanzado que nadie investigó antes tarda
  de 15 a 25 s más (la búsqueda más la lección). Las siguientes veces sale de la caché.
- **Costo:** unos 18 000 tokens de gpt-4o y una búsqueda web por tema y nivel, una
  sola vez para todos.
- El temario cacheado no caduca. Si se quiere refrescar, se borra el documento de
  `curriculum_research`.
- `WEB_RESEARCH_ENABLED=false` lo apaga sin desplegar código.
