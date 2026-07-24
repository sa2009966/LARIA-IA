from uuid import uuid4

from src.domain.aggregates.student_profile import StudentProfile
from src.domain.services.pedagogical_engine import (
    PedagogicalEngine,
    PedagogicalMode,
    TutorIntent,
)
from src.domain.services.tutor_policy import TutorPolicy
from src.domain.value_objects.question import Difficulty


class TestStudentProfile:
    def test_record_quiz_updates_mastery(self):
        student = uuid4()
        doc = uuid4()
        profile = StudentProfile.create(student)
        profile.record_quiz_result(doc, 1.0)
        profile.record_quiz_result(doc, 0.0)
        assert profile.mastery_for(doc) < 1.0
        assert profile.mastery_for(doc) > 0.0
        assert profile.total_attempts == 2

    def test_weak_profile_pace_slow(self):
        profile = StudentProfile.create(uuid4())
        for _ in range(3):
            profile.record_quiz_result(uuid4(), 0.2)
        assert profile.pace == "slow"


class TestPedagogicalEngine:
    def test_weak_profile_scaffold_easy(self):
        doc = uuid4()
        profile = StudentProfile.create(uuid4())
        profile.record_quiz_result(doc, 0.2)
        decision = PedagogicalEngine().select(profile, doc, TutorIntent.ASK)
        assert decision.mode == PedagogicalMode.SCAFFOLD
        assert decision.target_difficulty == Difficulty.EASY

    def test_strong_profile_socratic_hard(self):
        doc = uuid4()
        profile = StudentProfile.create(uuid4())
        for _ in range(3):
            profile.record_quiz_result(doc, 0.95)
        decision = PedagogicalEngine().select(profile, doc, TutorIntent.ASK)
        assert decision.mode == PedagogicalMode.SOCRATIC
        assert decision.target_difficulty == Difficulty.HARD

    def test_two_students_different_strategies(self):
        doc = uuid4()
        weak = StudentProfile.create(uuid4())
        weak.record_quiz_result(doc, 0.1)
        strong = StudentProfile.create(uuid4())
        for _ in range(3):
            strong.record_quiz_result(doc, 0.95)
        engine = PedagogicalEngine()
        d_weak = engine.select(weak, doc, TutorIntent.ASK)
        d_strong = engine.select(strong, doc, TutorIntent.ASK)
        assert d_weak.mode != d_strong.mode
        assert d_weak.target_difficulty != d_strong.target_difficulty


class TestTutorPolicyWithDecision:
    def test_system_prompt_includes_mode(self):
        doc = uuid4()
        profile = StudentProfile.create(uuid4())
        profile.record_quiz_result(doc, 0.2)
        decision = PedagogicalEngine().select(profile, doc, TutorIntent.ASK)
        prompt = TutorPolicy().answer_question("ctx", "¿qué?", decision)
        assert "scaffold" in prompt.system
        assert "anti" in prompt.system.lower() or "Nunca reveles" in prompt.system

    def test_quiz_prompt_targets_difficulty(self):
        doc = uuid4()
        profile = StudentProfile.create(uuid4())
        for _ in range(3):
            profile.record_quiz_result(doc, 0.95)
        decision = PedagogicalEngine().select(profile, doc, TutorIntent.QUIZ)
        prompt = TutorPolicy().generate_quiz("texto", 3, decision)
        assert "hard" in prompt.system
