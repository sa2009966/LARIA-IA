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
        assert "resolver ecuacion" in s.concepts_hint

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
        # La señal queda registrada como evidencia DÉBIL del concepto...
        cm = profile.mastery_by_concept["variable"]
        assert cm.weak_evidence_count == 1
        assert cm.measured_evidence_count == 0
        # ...y no como un error ni como un malentendido: preguntar no es fallar
        # (ADR-007). Antes, un ask escribía el expediente de errores y el motor
        # lo leía como "aquí falló", desviando el foco de lo preguntado.
        assert "variable" not in profile.frequent_errors
        assert "variable" not in profile.pedagogical_memory.frequent_misconceptions

        decision = PedagogicalEngine().select(profile, doc, TutorIntent.ASK)
        # Tras struggle fuerte, debería caer a scaffold/easy o al menos no hard socratic puro
        assert decision.target_difficulty in (Difficulty.EASY, Difficulty.MEDIUM)
        if profile.mastery_for(doc) < 0.4:
            assert decision.mode == PedagogicalMode.SCAFFOLD
