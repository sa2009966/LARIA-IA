# ADR-034: Cómo seguir después de completar una ruta

- **Estado:** Aceptado · **Fecha:** 2026-10-02 · **Complementa:** ADR-028

## Contexto
Al completar una ruta, la clase decía "¡Ruta completada!" y nada más.

## Decisión
`GET /learning/paths/{id}/next` devuelve hasta 3 sugerencias, sin temas ya
completados:

| Tipo | Cuándo | Qué propone |
|---|---|---|
| `level_up` | Si el nivel guardado del tema no es "avanzado" | El mismo tema, con una nivelación nueva |
| `advance` | Si el tema está en el grafo curricular | Los temas que se construyen sobre él (`successors_of`). Es determinista |
| `related` | Si el tema no está en el grafo | 3 temas que propone el modelo, una sola vez, guardados en la ruta (`next_topics`) |

`needs_placement` dice si hace falta nivelarse antes.
