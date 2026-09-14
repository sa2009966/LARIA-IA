from src.domain.ports.embodiment import AffectState
from src.domain.services.cognitive_style import CognitiveStyle
from src.domain.services.pedagogical_engine import (
    PedagogicalDecision,
    PedagogicalMode,
)
from src.domain.services.response_envelope import (
    ResponseEnvelope,
    envelope_type_for_mode,
)
from src.domain.value_objects.question import Difficulty


def _decision(mode=PedagogicalMode.SOCRATIC):
    return PedagogicalDecision(
        mode=mode,
        target_difficulty=Difficulty.MEDIUM,
        focus_concepts=("grafos",),
        anti_spoiler=True,
        objective="Profundizar",
        evidence_summary="doc_mastery=0.8",
        cognitive_style=CognitiveStyle.STEP_BY_STEP,
        session_step="practice",
    )


class TestResponseEnvelope:

    def test_to_dict_includes_type_emotion(self):
        env = ResponseEnvelope(type="answer", emotion=AffectState.CALM, payload={"content": "x"})
        d = env.to_dict()
        assert d["type"] == "answer"
        assert d["emotion"] == "calm"
        assert d["payload"] == {"content": "x"}

    def test_from_decision_no_decision(self):
        env = ResponseEnvelope.from_decision(None, "answer", AffectState.ENCOURAGING, content="hola")
        assert env.payload == {"content": "hola"}
        assert "mode" not in env.payload

    def test_from_decision_includes_pedagogy(self):
        env = ResponseEnvelope.from_decision(
            _decision(), "answer", AffectState.PATIENT, content="x"
        )
        assert env.payload["mode"] == "socratic"
        assert env.payload["difficulty"] == "medium"
        assert env.payload["cognitive_style"] == "step_by_step"
        assert env.payload["focus_concepts"] == ["grafos"]
        assert env.payload["content"] == "x"

    def test_from_decision_extra_merged(self):
        env = ResponseEnvelope.from_decision(None, "quiz", AffectState.CALM, extra={"intent": "quiz"})
        assert env.payload["intent"] == "quiz"

    def test_envelope_type_for_mode_none(self):
        assert envelope_type_for_mode(None) == "answer"

    def test_envelope_type_for_mode_mapping(self):
        assert envelope_type_for_mode(PedagogicalMode.EXPLAIN) == "explanation"
        assert envelope_type_for_mode(PedagogicalMode.SOCRATIC) == "answer"
        assert envelope_type_for_mode(PedagogicalMode.SCAFFOLD) == "hint"
        assert envelope_type_for_mode(PedagogicalMode.PRACTICE) == "quiz"
