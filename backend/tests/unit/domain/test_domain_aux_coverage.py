"""Cobertura ramas pendientes de dominio pedagógico auxiliar."""
from __future__ import annotations

from uuid import uuid4

from src.domain.aggregates.student_profile import PedagogicalMemory, StudentProfile
from src.domain.ports.embodiment import AffectState
from src.domain.services.affect_policy import AffectPolicy
from src.domain.services.cognitive_style import CognitiveStyle, CognitiveStyleSelector
from src.domain.services.learning_signal_detector import LearningSignal, LearningSignalKind
from src.domain.services.model_router import LlmTask, ModelRouter
from src.domain.services.pedagogical_engine import PedagogicalDecision, PedagogicalMode
from src.domain.services.cognitive_style import CognitiveStyle as CS
from src.domain.value_objects.question import Difficulty


def test_affect_policy_scaffold_and_socratic():
    policy = AffectPolicy()
    decision_scaffold = PedagogicalDecision(
        mode=PedagogicalMode.SCAFFOLD,
        target_difficulty=Difficulty.MEDIUM,
        focus_concepts=(),
        anti_spoiler=True,
        objective="o",
        evidence_summary="e",
        cognitive_style=CS.SIMPLE,
    )
    assert policy.select(None, decision_scaffold) == AffectState.PATIENT

    decision_socratic = PedagogicalDecision(
        mode=PedagogicalMode.SOCRATIC,
        target_difficulty=Difficulty.MEDIUM,
        focus_concepts=(),
        anti_spoiler=True,
        objective="o",
        evidence_summary="e",
        cognitive_style=CS.SIMPLE,
    )
    assert policy.select(None, decision_socratic) == AffectState.CALM


def test_affect_policy_slow_pace_encouraging():
    student = uuid4()
    profile = StudentProfile.create(student)
    profile.pace = "slow"
    assert AffectPolicy().select(profile, None) == AffectState.ENCOURAGING


def test_cognitive_style_from_signals_and_profile():
    selector = CognitiveStyleSelector()
    signal = LearningSignal(kind=LearningSignalKind.NOVICE, strength=0.8, concepts_hint=())
    assert selector.select(None, signal=signal) == CognitiveStyle.SIMPLE

    help_signal = LearningSignal(kind=LearningSignalKind.HELP, strength=0.9, concepts_hint=())
    assert selector.select(None, signal=help_signal) == CognitiveStyle.STEP_BY_STEP

    assert selector.select(None, question="explícame con un diagrama visual") == CognitiveStyle.VISUAL

    student = uuid4()
    profile = StudentProfile.create(student)
    profile.pedagogical_memory = PedagogicalMemory(preferred_explanation_style="technical")
    profile.pace = "fast"
    profile.total_attempts = 5
    assert selector.select(profile) == CognitiveStyle.TECHNICAL

    slow = StudentProfile.create(uuid4())
    slow.pedagogical_memory = PedagogicalMemory(preferred_explanation_style="")
    slow.pace = "slow"
    assert selector.select(slow) == CognitiveStyle.STEP_BY_STEP

    struggle = StudentProfile.create(uuid4())
    struggle.pedagogical_memory = PedagogicalMemory(preferred_explanation_style="")
    struggle.total_struggle_signals = 4
    assert selector.select(struggle) == CognitiveStyle.STEP_BY_STEP

    confusion = LearningSignal(kind=LearningSignalKind.CONFUSION, strength=0.7, concepts_hint=())
    assert selector.select(None, signal=confusion) == CognitiveStyle.SIMPLE


def test_model_router_quiz_and_ask_branches():
    router = ModelRouter(default_model="mini", strong_model="strong")
    assert router.select(LlmTask.QUIZ, None).model == "mini"

    decision = PedagogicalDecision(
        mode=PedagogicalMode.EXPLAIN,
        target_difficulty=Difficulty.HARD,
        focus_concepts=(),
        anti_spoiler=True,
        objective="o",
        evidence_summary="e",
        cognitive_style=CS.SIMPLE,
        blocked_by_prereq=True,
    )
    assert router.select(LlmTask.QUIZ, decision).reason == "quiz_remediation"
    assert router.select(LlmTask.ASK, decision).reason == "prereq_scaffold"

    socratic = PedagogicalDecision(
        mode=PedagogicalMode.SOCRATIC,
        target_difficulty=Difficulty.HARD,
        focus_concepts=(),
        anti_spoiler=True,
        objective="o",
        evidence_summary="e",
        cognitive_style=CS.SIMPLE,
    )
    assert router.select(LlmTask.ASK, socratic).model == "strong"
    assert router.select(LlmTask.ASK, None).reason == "ask_default"
    assert router.select(LlmTask.ANALYZE, None, json_retry=True).model == "strong"
