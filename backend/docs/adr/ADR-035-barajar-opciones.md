# ADR-035: Las opciones de todo quiz se barajan al azar

- **Estado:** Aceptado · **Fecha:** 2026-10-02 · **Sustituye:** el reequilibrio de `quiz_quality`

## Contexto
- En las clases la respuesta correcta era casi siempre la B: el modelo tiene
  sesgo de posición y las comprobaciones no pasaban por ningún reequilibrio.
- Los demás quizzes solo se reequilibraban si una letra superaba el 60 %, y con
  una rotación predecible: la 1.ª pregunta no se movía, la 2.ª un lugar…
- Un estudiante puede aprenderse la letra en vez del concepto, y entonces la
  evidencia no mide nada.

## Decisión
- `ensure_quiz_quality` baraja **siempre** las opciones de cada pregunta con
  `random.SystemRandom` y reasigna A, B, C… y la correcta.
- Se aplica en la comprobación de la clase, la nivelación, la práctica y el quiz
  sobre un documento.
- **Excepción:** las preguntas con opciones que hablan de otras ("todas las
  anteriores", "A y B") no se barajan.
- **Verificado:** en 400 preguntas con la correcta en B, ninguna letra pasa del
  35 % tras barajar, y el texto correcto se conserva siempre.
