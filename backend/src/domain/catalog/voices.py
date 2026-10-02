"""Voces del tutor que el estudiante puede elegir (ADR-030).

Tres de timbre masculino y tres de timbre femenino entre las voces de OpenAI que
funcionan con el modelo configurado (comprobadas una a una). El género es una
etiqueta para elegir, no una propiedad del proveedor: OpenAI no las clasifica.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class TutorVoice:
    id: str
    label: str
    gender: Literal["masculina", "femenina"]
    description: str


VOICES: tuple[TutorVoice, ...] = (
    TutorVoice("cedar", "Cedro", "masculina", "Grave y serena, la más natural."),
    TutorVoice("ash", "Fresno", "masculina", "Cercana y clara."),
    TutorVoice("onyx", "Ónix", "masculina", "Profunda y pausada."),
    TutorVoice("marin", "Marina", "femenina", "Cálida y natural, la más fluida."),
    TutorVoice("coral", "Coral", "femenina", "Amable y expresiva."),
    TutorVoice("nova", "Nova", "femenina", "Joven y enérgica."),
)

#: Voz si el estudiante no eligió ninguna.
DEFAULT_VOICE = "coral"


def is_voice(voice_id: str | None) -> bool:
    return any(v.id == voice_id for v in VOICES)


def voice_gender(voice_id: str | None) -> Literal["masculina", "femenina"]:
    """Género de la voz; la de por defecto si no se reconoce."""
    v = next((x for x in VOICES if x.id == voice_id), None) or next(x for x in VOICES if x.id == DEFAULT_VOICE)
    return v.gender


def persona_for(voice_choice: str | None) -> Literal["masculina", "femenina"]:
    """Cómo habla LARIA de sí misma: con el género de la voz que se oye (ADR-030).

    Con una voz masculina diciendo "soy tu tutora" sonaba incoherente. Sin voz
    elegida manda la de por defecto, porque es la que suena.
    """
    return voice_gender(voice_choice or DEFAULT_VOICE)


#: Frase de muestra según el género de la voz.
SAMPLE_TEXTS = {
    "femenina": "Hola, soy LARIA, tu tutora de Plenum. Así sonará mi voz en tus clases.",
    "masculina": "Hola, soy LARIA, tu tutor de Plenum. Así sonará mi voz en tus clases.",
}
