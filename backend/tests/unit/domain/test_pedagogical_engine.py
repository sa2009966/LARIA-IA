from uuid import uuid4

from src.domain.aggregates.student_profile import StudentProfile
from src.domain.concept_identity import canonicalize_concept
from src.domain.services.misconception_resolver import MisconceptionResolver
from src.domain.aggregates.tutor_session import SessionStep, TutorSession
from src.domain.services.cognitive_style import CognitiveStyle
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

    def test_mapped_misconception_vs_empty_profile_different_decision(self):
        doc = uuid4()
        question = "¿cómo despejo x en 2x=4?"
        engine = PedagogicalEngine()
        empty = StudentProfile.create(uuid4())
        mapped = StudentProfile.create(uuid4())
        alias = "confundir el signo al despejar"
        mapped.pedagogical_memory.remember_misconception(alias)
        d_empty = engine.select(empty, doc, TutorIntent.ASK, question=question)
        d_mapped = engine.select(mapped, doc, TutorIntent.ASK, question=question)
        assert (
            d_mapped.focus_concepts,
            d_mapped.mode,
            d_mapped.remediation_concepts,
        ) != (
            d_empty.focus_concepts,
            d_empty.mode,
            d_empty.remediation_concepts,
        )
        entry = MisconceptionResolver().resolve_entry(alias)
        assert entry is not None
        assert d_mapped.focus_concepts[0] in {
            entry.id,
            canonicalize_concept(entry.anchor_concept),
        }

    def test_mapped_misconception_outranks_generic_weak(self):
        doc = uuid4()
        profile = StudentProfile.create(uuid4())
        profile.record_concept_result("variable", 0.1, document_id=doc)
        alias = "el igual es hacer la operacion"
        profile.pedagogical_memory.remember_misconception(alias)
        decision = PedagogicalEngine().select(profile, doc, TutorIntent.ASK)
        entry = MisconceptionResolver().resolve_entry(alias)
        assert entry is not None
        mapped_keys = {entry.id, canonicalize_concept(entry.anchor_concept)}
        assert decision.focus_concepts[0] in mapped_keys
        assert decision.focus_concepts[0] != "variable"


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

    def test_duplicate_unmapped_misconception_skips_repeated_key(self):
        doc = uuid4()
        profile = StudentProfile.create(uuid4())
        key = canonicalize_concept("fotosintesis avanzada")
        profile.pedagogical_memory.frequent_misconceptions = [key, key, "   "]
        decision = PedagogicalEngine().select(profile, doc, TutorIntent.ASK)
        assert key in decision.focus_concepts

    def test_duplicate_mapped_aliases_deduplicate_focus(self):
        doc = uuid4()
        profile = StudentProfile.create(uuid4())
        profile.pedagogical_memory.remember_misconception("confundir el signo al despejar")
        profile.pedagogical_memory.remember_misconception("pasar el termino sin cambiar el signo")
        decision = PedagogicalEngine().select(profile, doc, TutorIntent.ASK)
        entry = MisconceptionResolver().resolve_entry("confundir el signo al despejar")
        assert entry is not None
        assert decision.focus_concepts[0] in {
            entry.id,
            canonicalize_concept(entry.anchor_concept),
        }
        assert "mapped_misconception=" in decision.evidence_summary

    def test_medium_mastery_selects_explain_mode(self):
        doc = uuid4()
        profile = StudentProfile.create(uuid4())
        profile.record_concept_result("variable", 0.55, document_id=doc)
        decision = PedagogicalEngine().select(profile, doc, TutorIntent.ASK)
        assert decision.mode == PedagogicalMode.EXPLAIN
        assert decision.target_difficulty in {Difficulty.MEDIUM, Difficulty.EASY}

    def test_practice_session_keeps_explain_even_with_high_mastery(self):
        doc = uuid4()
        student = uuid4()
        profile = StudentProfile.create(student)
        for _ in range(4):
            profile.record_concept_result("variable", 0.95, document_id=doc)
        session = TutorSession.start(student, doc)
        session.step = SessionStep.PRACTICE
        decision = PedagogicalEngine().select(profile, doc, TutorIntent.ASK, session=session)
        assert decision.mode == PedagogicalMode.EXPLAIN

    def test_analogy_style_and_memory_extend_objective(self):
        doc = uuid4()
        profile = StudentProfile.create(uuid4())
        for _ in range(4):
            profile.record_concept_result("variable", 0.95, document_id=doc)
        profile.pedagogical_memory.remember_analogy("como una balanza")
        decision = PedagogicalEngine().select(
            profile,
            doc,
            TutorIntent.ASK,
            question="explícame con una analogía",
        )
        assert decision.cognitive_style == CognitiveStyle.ANALOGY
        assert "analogías" in decision.objective.lower()
