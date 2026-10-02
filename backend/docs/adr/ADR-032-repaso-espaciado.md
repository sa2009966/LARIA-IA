# ADR-032: Repaso espaciado: la clase actúa sobre el olvido

- **Estado:** Aceptado · **Fecha:** 2026-10-02 · **Complementa:** ADR-003 (olvido), ADR-028 (clase)

## Contexto
El mastery efectivo ya decaía con el tiempo (curva de Ebbinghaus, vida media
de 14 días), pero nada actuaba sobre eso. Un concepto superado en clase quedaba
"superado" para siempre, aunque el perfil dijera que se había olvidado.

## Decisión
- **`TeachingPolicy.due_review`.** Busca un concepto ya superado en la clase, con
  evidencia medida, cuyo mastery efectivo haya caído por debajo de 0,5.
  Devuelve el más olvidado.
- **El repaso va primero.** Si hay uno pendiente, el siguiente paso de la clase
  es ese repaso (variante `review`: repaso breve, ejemplo distinto y preguntas
  medias) antes de seguir con lo nuevo.
- **Una ruta completada se reabre** al pedir `/lesson` si el olvido bajó algo:
  - el motivo se le dice al estudiante ("Hace un tiempo que no practicas «X»: lo
    repasamos");
  - el concepto sale de `passed_concepts` y vuelve a superarse como cualquier
    otro.

## Además, en la clase (ADR-028)
- **Títulos con tildes:** el nombre de cada concepto del grafo se recupera de la
  semilla ("Número entero", no "Numero entero").
- **Doble envío de una comprobación** (doble clic, dos pestañas): si el quiz ya
  tiene un intento, el segundo envío responde 409 y no cuenta como otra
  evidencia.
