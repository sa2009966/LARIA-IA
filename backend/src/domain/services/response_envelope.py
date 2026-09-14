"""Envoltura de respuesta del tutor: tipo + emoción + payload.

Estructura mínima que viaja en el `metadata` del mensaje assistant para que
React sepa QUÉ renderizar (respuesta, quiz, hint, celebración) y CÓMO
expresarse el avatar (emoción). Deterministica: la emoción se deriva del
perfil/decisión, no del LLM.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from src.domain.ports.embodiment import AffectState
from src.domain.services.cognitive_style import CognitiveStyle
from src.domain.services.pedagogical_engine import PedagogicalDecision, PedagogicalMode


# Tipo de componente/acción que el cliente debe renderizar.
EnvelopeType = Literal[
    "answer",  # respuesta normal (MessageBubble)
    "hint",  # pista/andamiaje (borde naranja)
    "quiz",  # genera quiz (QuizCard)
    "explanation",  # explica un concepto (MessageBubble ampliada)
    "celebration",  # logro/checkpoint (CelebrationModal)
    "error",  # fallo del proveedor
]


@dataclass(frozen=True)
class ResponseEnvelope:
    type: EnvelopeType
    emotion: AffectState
    payload: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def from_decision(
        decision: PedagogicalDecision | None,
        intent_type: EnvelopeType,
        affect: AffectState,
        content: str = "",
        extra: dict[str, Any] | None = None,
    ) -> "ResponseEnvelope":
        payload: dict[str, Any] = {"content": content} if content else {}
        if extra:
            payload.update(extra)
        if decision is not None:
            payload.update(
                {
                    "mode": decision.mode.value,
                    "difficulty": decision.target_difficulty.value,
                    "cognitive_style": decision.cognitive_style.value,
                    "focus_concepts": list(decision.focus_concepts),
                    "session_step": decision.session_step,
                }
            )
        return ResponseEnvelope(
            type=intent_type,
            emotion=affect,
            payload=payload,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "emotion": self.emotion.value,
            "payload": self.payload,
        }


def envelope_type_for_mode(mode: PedagogicalMode | None) -> EnvelopeType:
    """Mapea el modo pedagógico a un tipo de envelope para el cliente."""
    if mode is None:
        return "answer"
    return {
        PedagogicalMode.EXPLAIN: "explanation",
        PedagogicalMode.SOCRATIC: "answer",
        PedagogicalMode.SCAFFOLD: "hint",
        PedagogicalMode.PRACTICE: "quiz",
    }[mode]
