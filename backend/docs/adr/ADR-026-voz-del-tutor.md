# ADR-026: Voz del tutor, a elección del estudiante

- **Estado:** Aceptado
- **Fecha:** 2026-09-30
- **Rama de origen:** `feature/backend`
- **Decisores:** Equipo LARIA (orquestación backend)
- **Concreta:** [ADR-002](ADR-002-embodiment-adapter.md) (voz como adaptador)

## Contexto

Se pidió que LARIA lea en voz alta lo que va escribiendo, con una opción
visible: "leer en voz" o "solo texto". ADR-002 ya preveía la voz como un
adaptador detrás de `TextToSpeechPort`, con un stub nulo.

## Decisión

- **`POST /speech {text, emotion}` → `audio/mpeg` en streaming.** Recibe un trozo
  de la respuesta, una o dos frases, tal como se escribió. El cliente trocea la
  respuesta según llega por el stream y encadena los audios: mientras suena una
  frase se genera la siguiente. Medido: primer audio a ~2 s por frase con
  `gpt-4o-mini-tts`.
- **Texto hablable** (`speakable_text`, dominio). Quita el markdown y convierte
  las fórmulas simples en palabras: "1 sobre 2", "x al cuadrado", "raíz de 16".
  Donde la voz no puede describir bien, avisa: "la fórmula que ves en pantalla",
  "te dejo el código en pantalla", "te dejo un esquema en pantalla".
- **El tono sale de `emotion`**, la `AffectState` que ya decide la política
  afectiva (calma, ánimo, paciencia, celebración). La voz no inventa emociones.
- **Voz:** `coral`, en español latino neutro, con dicción de clase. Modelo y voz
  se configuran (`TTS_MODEL`, `TTS_VOICE`).
- **Coste y abuso:** hace falta sesión, 60 peticiones por minuto por usuario y
  1200 caracteres hablables por petición. Solo se genera audio cuando el
  estudiante eligió escuchar.
- **Fallos:** el primer trozo se pide antes de responder. Si el proveedor falla,
  el cliente recibe un 503 con JSON y no un audio cortado; el texto sigue en
  pantalla. `TTS_ENABLED=false` lo apaga; `GET /speech/config` lo dice.
- **Privacidad:** nunca se graba la voz del estudiante. A OpenAI solo va el texto
  de las respuestas que se piden escuchar. La política lo dice.

## Fuera de alcance

- **Dictado en el servidor** (voz → texto). El navegador ya dicta. Procesar audio
  del estudiante, con menores de por medio, es otra decisión de privacidad.
- **Caché de audio.** Hoy el cliente guarda el audio de cada mensaje en la
  sesión. Guardarlo en R2 tiene sentido si "volver a escuchar" se usa mucho.
