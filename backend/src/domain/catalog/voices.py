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
