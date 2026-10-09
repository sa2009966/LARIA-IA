# ADR-042: La prueba de paso es de la ruta, no una nivelación nueva

- **Estado:** Aceptado · **Fecha:** 2026-10-09 · **Corrige:** ADR-037 (rutas por tramos)

## Contexto
Hubo un informe de error con dos pruebas: "Teléfonos y sus procesadores" y "Programación".
- **Frontend:** "Hacer la prueba de paso" llevaba a la nivelación inicial
  (`/nivelacion?tema=`), que muestra el campo de tema editable. Si se escribía otro
  tema, nacía otra ruta.
- **Backend:** la prueba de paso era la nivelación genérica del tema
  (`plan_diagnostic`). Las preguntas salían del tema en general o de su grafo, no de los
  módulos estudiados en la ruta.

## Decisión
- **`POST /learning/paths/{id}/passage-test`** genera la prueba de paso de ESA ruta.
  No pide tema ni crea rutas.
  - Solo existe con un tramo terminado y otro por delante (`completed` y `next_tier`);
    si no, responde **409**.
  - Mide los módulos del tramo que terminó: `plan_passage_test` toma sus conceptos y
    `studied` lleva sus títulos y hasta 2 ideas clave por módulo.
  - El prompt de la nivelación dice que es una prueba de paso y que pregunte solo sobre
    lo estudiado.
- **Sigue siendo una ronda de nivelación del mismo tema**, con la ronda que toca a su
  nivel (`round_for`): base desde básico y avanzada desde intermedio.
  - Su veredicto sube el nivel por el camino de siempre (el projector).
  - La siguiente `/lesson` abre el tramo (ADR-037).
- **Los ítems se etiquetan con los conceptos de los módulos**, así que la evidencia llega
  a esa ruta.
- **Si no la supera**, la evidencia baja el dominio de lo que falló. Si un concepto queda
  por debajo del umbral, la ruta lo repasa (ADR-032), y la prueba se puede repetir.

## Verificado
- `tests/api/test_prueba_de_paso_e2e.py`:
  - mide los módulos del tramo con la ronda de su nivel;
  - si la supera, abre el tramo en la misma ruta y no crea otra;
  - si la falla, repasa;
  - responde 409 sin tramo terminado o con la ruta completa, y 404 si la ruta es ajena.
- Con el modelo real, "Teléfonos y sus procesadores" (arquitectura, núcleos, RAM,
  almacenamiento, GPU): las 6 preguntas se refieren a esos módulos (ARM, big.LITTLE, RAM,
  UFS, GPU).

## Consecuencias
- El cliente deja de mandar la prueba de paso a `/nivelacion`. Muestra este quiz en la
  clase y responde con `POST /quizzes/{id}/attempts`.
- **Lo que no usa:** el historial del chat. La clase guiada no es un chat, y sus
  explicaciones no se guardan por módulo (solo la última). El contexto son los módulos,
  sus ideas clave y la evidencia del perfil.
