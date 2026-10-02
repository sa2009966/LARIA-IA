# ADR-031: Nivelación calibrada: rúbrica de dificultad, sin repetir y ronda avanzada con modelo fuerte

- **Estado:** Aceptado · **Fecha:** 2026-10-02 · **Complementa:** ADR-016, ADR-017

## Contexto
Medido con un evaluador (gpt-4o) sobre 72 ítems de 5 temas, clasificando cada
pregunta por nivel cognitivo:
- 1 = recordar;
- 2 = aplicar en un paso;
- 3 = varios pasos o transferir.

Resultados:
- solo el 36 % de los ítems tenía la dificultad que decía tener;
- las "difíciles" medían 1,75 de nivel medio y las "medias", 1,40;
- un tercio de la ronda avanzada repetía preguntas de la base.

La nivelación sobreestimaba el nivel: era fácil salir "avanzado".

## Decisión
1. **Rúbrica explícita** en el prompt:
   - easy = reconocer o recordar;
   - medium = aplicar en un paso;
   - hard = varios pasos, combinar ideas, detectar un error o un caso nuevo.

   Además: una sola opción correcta y distractores sacados de errores típicos.
2. **No repetir.** Se pasan al modelo los enunciados de las nivelaciones y
   prácticas anteriores del mismo tema (los 30 más recientes). Si aun así repite
   alguno, se genera otra vez y se queda la versión que menos repite.
3. **La ronda avanzada usa el modelo fuerte** (`OPENAI_MODEL_STRONG`, gpt-4o).
   Son 8 preguntas, solo para quien ya pasó la base, y es la ronda que decide
   "avanzado". El modelo se inyecta en el servicio; el servicio no lee la
   configuración.

## Resultado medido (mismo evaluador, mismos 5 temas)

| | Antes | Solo rúbrica | Rúbrica + modelo fuerte en la avanzada |
|---|---|---|---|
| Dificultad correcta | 36 % | 57 % | **63 %** |
| Nivel medio de "hard" (meta 3) | 1,75 | 2,08 | **2,48** |
| Nivel medio de "medium" (meta 2) | 1,40 | 1,96 | 1,84 |
| Repetidas en la avanzada | 33 % | 30 % | **10 %** |
| Ambiguas | 1/72 | 3/70 | 5/70 |

## Pendiente
- Las "fáciles" siguen en ~1,3, que está bien. Las ambiguas subieron un poco
  (7 %), y el servidor no puede detectar equivalencias de significado.
- La calibración real necesita respuestas de estudiantes reales: qué porcentaje
  acierta cada ítem.
