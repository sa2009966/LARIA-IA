from uuid import uuid4

from src.domain.aggregates.student_profile import StudentProfile
from src.domain.services.learning_signal_detector import (
    LearningSignalDetector,
    LearningSignalKind,
)
from src.domain.services.pedagogical_engine import PedagogicalEngine, PedagogicalMode, TutorIntent
from src.domain.value_objects.question import Difficulty


class TestLearningSignalDetector:
    def test_novice(self):
        s = LearningSignalDetector().detect("No sé nada de álgebra, ¿qué es una variable?")
        assert s.kind == LearningSignalKind.NOVICE
        assert s.strength >= 0.8
        assert "variable" in s.concepts_hint

    def test_confusion(self):
        s = LearningSignalDetector().detect("No entiendo cómo despejar x")
        assert s.kind == LearningSignalKind.CONFUSION
        assert "resolver ecuación" in s.concepts_hint

    def test_none(self):
        s = LearningSignalDetector().detect("¿Cuál es la propiedad distributiva?")
        assert s.kind == LearningSignalKind.NONE
        assert "propiedad distributiva" in s.concepts_hint


class TestAskStruggleUpdatesProfile:
    def test_struggle_baja_mastery_y_engine_scaffold(self):
        doc = uuid4()
        profile = StudentProfile.create(uuid4())
        # Parecía experto por un quiz sesgado
        profile.record_quiz_result(doc, 1.0)
        assert profile.mastery_for(doc) == 1.0

        profile.record_ask_struggle(doc, strength=0.9, concepts=("variable",))
        assert profile.mastery_for(doc) < 0.6
        assert profile.total_struggle_signals == 1
        assert "variable" in profile.frequent_errors

        decision = PedagogicalEngine().select(profile, doc, TutorIntent.ASK)
        # Tras struggle fuerte, debería caer a scaffold/easy o al menos no hard socratic puro
        assert decision.target_difficulty in (Difficulty.EASY, Difficulty.MEDIUM)
        if profile.mastery_for(doc) < 0.4:
            assert decision.mode == PedagogicalMode.SCAFFOLD
