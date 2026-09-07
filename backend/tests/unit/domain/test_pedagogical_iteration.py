"""Tests del motor pedagógico: mastery multi-señal, olvido, prerreqs, recs, router."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from src.domain.aggregates.student_profile import (
    EvidenceKind,
    EvidenceSample,
    StudentProfile,
)
from src.domain.concept_identity import canonicalize_concept
from src.domain.services.cognitive_style import CognitiveStyle, CognitiveStyleSelector
from src.domain.services.difficulty_calculator import DifficultyCalculator, DifficultySignals
from src.domain.services.model_router import LlmTask, ModelRouter
from src.domain.services.pedagogical_engine import (
    PedagogicalEngine,
    PedagogicalMode,
    TutorIntent,
)
from src.domain.services.prerequisite_graph import PrerequisiteGate, PrerequisiteGraph
from src.domain.services.recommendation_engine import RecommendationEngine
from src.domain.value_objects.question import Difficulty


class TestMultiSignalMastery:
    def test_help_request_reduces_credit(self):
        profile = StudentProfile.create(uuid4())
        profile.record_concept_evidence(
            "ecuación",
            EvidenceSample(kind=EvidenceKind.SUCCESS, score_ratio=1.0),
        )
        high = profile.concept_mastery_for("ecuación")
        profile.record_concept_evidence(
            "ecuación",
            EvidenceSample(kind=EvidenceKind.HELP_REQUEST, score_ratio=1.0, help_level=0.8),
        )
        eq = canonicalize_concept("ecuación")
        assert profile.mastery_by_concept[eq].help_requests >= 1
        assert profile.concept_mastery_for("ecuación") < high

    def test_repeated_error_increases_streak(self):
        profile = StudentProfile.create(uuid4())
        for _ in range(3):
            profile.record_concept_evidence(
                "variable",
                EvidenceSample(kind=EvidenceKind.REPEATED_ERROR, score_ratio=0.0),
            )
        assert profile.mastery_by_concept["variable"].error_streak >= 2
        assert profile.concept_mastery_for("variable") < 0.3


class TestForgettingCurve:
    def test_effective_mastery_decays_over_time(self):
        profile = StudentProfile.create(uuid4())
        profile.record_concept_result("matrices", 0.95)
        cm = profile.mastery_by_concept["matrices"]
        cm.last_practiced_at = datetime.now(timezone.utc) - timedelta(days=28)
        cm.half_life_days = 14.0
        stored = cm.mastery
        effective = cm.effective_mastery()
        assert effective < stored
        assert cm.forgetting_gap() > 0.1
        assert "matrices" in profile.forgotten_concepts(min_gap=0.1)


class TestPrerequisites:
    def test_integrals_blocked_without_derivatives(self):
        gate = PrerequisiteGate()
        profile = StudentProfile.create(uuid4())
        profile.record_concept_result("integrales", 0.2)
        result = gate.evaluate("integrales", profile)
        assert result.blocked
        assert "derivadas" in result.missing_prereqs or "funciones" in result.missing_prereqs

    def test_engine_redirects_to_remediation(self):
        profile = StudentProfile.create(uuid4())
        doc = uuid4()
        # Fuerza foco en integrales sin bases
        profile.record_concept_result("integrales", 0.2, document_id=doc)
        engine = PedagogicalEngine()
        decision = engine.select(
            profile,
            doc,
            TutorIntent.ASK,
            document_concepts=("integrales", "derivadas", "funciones"),
        )
        assert decision.blocked_by_prereq or decision.mode == PedagogicalMode.SCAFFOLD
        assert decision.target_difficulty == Difficulty.EASY

    def test_advanced_topic_weak_prereq_blocks_and_focuses_base(self):
        profile = StudentProfile.create(uuid4())
        doc = uuid4()
        profile.record_concept_result("integrales", 0.2, document_id=doc)
        decision = PedagogicalEngine().select(
            profile,
            doc,
            TutorIntent.ASK,
            document_concepts=("funciones", "derivadas", "integrales"),
        )
        assert decision.blocked_by_prereq is True
        assert decision.focus_concepts[0] in {
            "funciones",
            "derivadas",
            "variable",
            "expresion algebraica",
        }
        assert decision.focus_concepts[0] != "integrales"
        assert decision.mode == PedagogicalMode.SCAFFOLD
        assert decision.target_difficulty == Difficulty.EASY


class TestCognitiveAndDifficulty:
    def test_style_from_question(self):
        style = CognitiveStyleSelector().select(None, question="explícame con una analogía")
        assert style == CognitiveStyle.ANALOGY

    def test_difficulty_zone(self):
        calc = DifficultyCalculator()
        easy = calc.calculate(
            DifficultySignals(0.2, 0.1, -0.1, 0.8, pace="slow")
        )
        hard = calc.calculate(
            DifficultySignals(0.9, 0.9, 0.2, 0.0, pace="fast")
        )
        assert easy == Difficulty.EASY
        assert hard == Difficulty.HARD


class TestRecommendations:
    def test_builds_forgotten_and_priority(self):
        profile = StudentProfile.create(uuid4())
        profile.record_concept_result("variable", 0.9)
        profile.mastery_by_concept["variable"].last_practiced_at = (
            datetime.now(timezone.utc) - timedelta(days=40)
        )
        profile.record_concept_result("ecuación", 0.2)
        recs = RecommendationEngine().build(profile)
        kinds = {r.kind for r in recs}
        assert "forgotten" in kinds or "review_priority" in kinds or "review_concept" in kinds
        assert any(r.suggested_minutes for r in recs)

    def test_next_topic_uses_public_successors_not_private_edges(self):
        profile = StudentProfile.create(uuid4())
        profile.record_concept_result("variable", 0.6)
        recs = RecommendationEngine().build(profile)
        next_topics = [r for r in recs if r.kind == "next_topic"]
        assert next_topics
        graph = PrerequisiteGraph()
        canon = graph.canonicalize("variable")
        assert next_topics[0].concept in graph.successors_of(canon)

    def test_find_ready_successor_does_not_touch_private_edges(self):
        import inspect

        src = inspect.getsource(RecommendationEngine._find_ready_successor)
        assert "successors_of" in src
        assert "_edges" not in src

    def test_next_topic_skips_when_prereq_gate_blocked(self):
        profile = StudentProfile.create(uuid4())
        profile.record_concept_result("integrales", 0.55)
        recs = RecommendationEngine().build(profile)
        assert not any(r.kind == "next_topic" and r.concept == "integrales" for r in recs)

    def test_mastered_concepts_recommendation(self):
        profile = StudentProfile.create(uuid4())
        for _ in range(8):
            profile.record_concept_result("variable", 0.95)
        assert profile.mastered_concepts(limit=1)
        recs = RecommendationEngine().build(profile)
        mastered = [r for r in recs if r.kind == "mastered"]
        assert mastered
        assert mastered[0].concept == "variable"

    def test_weak_document_suggests_review_and_easier_quiz(self):
        doc = uuid4()
        profile = StudentProfile.create(uuid4())
        profile.record_quiz_result(doc, 0.2)
        recs = RecommendationEngine().build(profile)
        kinds = {r.kind for r in recs}
        assert "review" in kinds
        assert "easier_quiz" in kinds
        assert any(r.document_id == doc for r in recs if r.kind == "review")

    def test_moderate_document_suggests_guided_explain(self):
        doc = uuid4()
        profile = StudentProfile.create(uuid4())
        profile.record_quiz_result(doc, 0.55)
        recs = RecommendationEngine().build(profile)
        guided = [r for r in recs if r.kind == "guided_explain"]
        assert guided
        assert guided[0].document_id == doc


class TestModelRouter:
    def test_default_for_analyze(self):
        router = ModelRouter(default_model="gpt-4o-mini", strong_model="gpt-4o")
        choice = router.select(LlmTask.ANALYZE)
        assert choice.model == "gpt-4o-mini"

    def test_escalates_on_struggle(self):
        router = ModelRouter(default_model="gpt-4o-mini", strong_model="gpt-4o")
        from src.domain.services.pedagogical_engine import PedagogicalDecision
        from src.domain.services.cognitive_style import CognitiveStyle

        decision = PedagogicalDecision(
            mode=PedagogicalMode.EXPLAIN,
            target_difficulty=Difficulty.MEDIUM,
            focus_concepts=("x",),
            anti_spoiler=True,
            objective="o",
            evidence_summary="e",
            cognitive_style=CognitiveStyle.SIMPLE,
        )
        choice = router.select(LlmTask.ASK, decision, struggle_signals=5)
        assert choice.model == "gpt-4o"
