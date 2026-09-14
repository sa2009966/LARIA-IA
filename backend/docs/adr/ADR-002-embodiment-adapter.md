# ADR-002: Embodiment como adaptador; pedagogía no depende de hardware

- **Estado:** Aceptado
- **Fecha:** 2026-07-22
- **Decisores:** Orquestador LARIA

## Contexto

Existe interés futuro en un cuerpo físico (voz, gesto, “emociones” proyectadas).
Si se construye antes del tutor adaptativo, se obtiene un robot que conversa mal
con cariño: presencia sin pedagogía.

## Decisión

- Embodiment es un **bounded context ligero** detrás de puertos:
  `SpeechToTextPort`, `TextToSpeechPort`, `PresencePort`,
  `DeviceCommandPort`, `SensorInputPort`.
- La política afectiva (`AffectPolicy`) deriva estados discretos
  (`calm | encouraging | patient | celebratory`) del perfil/decisión pedagógica,
  **no** de un LLM inventando humor.
- Adaptadores actuales: stubs (`NullSpeechToText`, `NullTextToSpeech`, `LogOnlyPresence`,
  `NullDeviceCommand`, `NullSensorInput`) con timeout (`asyncio.wait_for`) y métricas
  `speech_latency` / `command_failed` / `device_errors` / `embodiment_degraded` /
  `device_command_timeout` / `forbidden_command_blocked` / `safety_interlock`.
- Modo degradado (stub): actuadores info se saltan; motion permanece bloqueado en stub;
  ESTOP siempre acusa. Fallos del dispositivo se tragan y no propagan al tutor.
- Feature flag `EMBODIMENT_ENABLED=false` por defecto: el arranque y el motor
  pedagógico son idénticos al comportamiento sin cuerpo.
- **Contrato:** los endpoints pedagógicos (`/ask`, quiz, profile) **no** invocan
  STT/TTS/Presence/Device en el camino crítico; embodiment es opt-in y fallible.
- **Fuera de alcance ahora:** drivers reales (Whisper, TTS, ROS/serial, cámara).

## Riesgos documentados

1. **Latencia** voz↔API vs turnos educativos.
2. **Privacidad**: audio es PII sensible.
3. Emoción simulada ≠ estado afectivo real del estudiante (no mentir pedagógicamente).
4. Fallo del cuerpo **no** debe tumbar el motor pedagógico (hexagonal).

## Consecuencias

- El tutor adaptativo (perfil → motor → policy → LLM) permanece independiente.
- Embodiment se puede enchufar después sin reescribir dominio educativo.
- Cero dependencia de micrófono/altavoz en este ciclo.
