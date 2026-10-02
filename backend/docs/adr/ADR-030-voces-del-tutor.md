# ADR-030: El estudiante elige la voz del tutor

- **Estado:** Aceptado · **Fecha:** 2026-10-02 · **Complementa:** ADR-026

## Decisión
- **Seis voces** de OpenAI, comprobadas una a una con `gpt-4o-mini-tts`:

  | Timbre | Voces |
  |---|---|
  | Masculino | `cedar` (Cedro), `ash` (Fresno), `onyx` (Ónix) |
  | Femenino | `marin` (Marina), `coral` (Coral), `nova` (Nova) |

  El género es una etiqueta para elegir: OpenAI no clasifica sus voces.
- **`GET /speech/voices`** devuelve el catálogo, la voz por defecto (`coral`),
  la elegida y una frase de muestra.
- **`PUT /speech/voice {voice | null}`** guarda la elección en el perfil. Viaja
  por evento y la escribe el projector (invariante 1), así que acompaña al
  estudiante en cualquier dispositivo.
- **`POST /speech`** acepta `voice` para una petición concreta (la vista
  previa). Sin ella usa la elegida y, si no hay, la de por defecto.
- Las políticas de uso de OpenAI exigen avisar al usuario de que la voz es
  generada por IA. La interfaz debe decirlo junto al selector.
