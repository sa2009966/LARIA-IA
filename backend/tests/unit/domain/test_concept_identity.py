"""Una sola clave canónica entre tagger, perfil y gate de prerrequisitos."""
from uuid import uuid4

from src.domain.aggregates.student_profile import (
    HIGH_LATENCY_THRESHOLD_MS,
    EvidenceKind,
    EvidenceSample,
    StudentProfile,
)
from src.domain.concept_identity import canonicalize_concept
from src.domain.services.concept_tagger import ConceptTagger
from src.domain.services.prerequisite_graph import PrerequisiteGate
from src.domain.value_objects.question import Difficulty, QuizQuestion


def test_canonicalize_folds_accents_case_and_spaces():
    assert canonicalize_concept("Ecuación") == canonicalize_concept("ecuacion")
    assert canonicalize_concept("ecuación") == canonicalize_concept("  ECUACION  ")
    assert canonicalize_concept("expresión  algebraica") == "expresion algebraica"


def test_tagger_profile_and_gate_share_keys():
    tagger = ConceptTagger()
    tagged = tagger.tag_question(
        QuizQuestion(
            text="¿Cómo se resuelve una ecuación 2x=4?",
            options={"A": "dividir", "B": "sumar", "C": "ignorar", "D": "restar"},
            correct_answer="A",
            difficulty=Difficulty.EASY,
        )
    )
    assert tagged.concept_tags
    key = tagged.concept_tags[0]
    assert key == canonicalize_concept("ecuación")

    profile = StudentProfile.create(uuid4())
    profile.record_concept_result("Ecuación", 0.9)
    assert profile.concept_mastery_for("ecuacion") == profile.concept_mastery_for("ecuación")
    assert key in profile.mastery_by_concept

    gate = PrerequisiteGate()
    result = gate.evaluate("ecuación", profile)
    assert result.target == canonicalize_concept("ecuación")
    assert result.target in profile.mastery_by_concept


def test_high_latency_lowers_mastery_vs_fast_ask():
    doc = uuid4()
    fast = StudentProfile.create(uuid4())
    slow = StudentProfile.create(uuid4())
    fast.record_ask_struggle(
        doc, strength=0.5, concepts=("variable",), latency_ms=200.0
    )
    slow.record_ask_struggle(
        doc,
        strength=0.5,
        concepts=("variable",),
        latency_ms=HIGH_LATENCY_THRESHOLD_MS + 4000.0,
    )
    assert slow.concept_mastery_for("variable") < fast.concept_mastery_for("variable")
    cm = slow.mastery_by_concept["variable"]
    assert cm.latency_ms_ema >= HIGH_LATENCY_THRESHOLD_MS
    assert cm.evidence_count > fast.mastery_by_concept["variable"].evidence_count


def test_below_threshold_does_not_add_high_latency_sample():
    doc = uuid4()
    profile = StudentProfile.create(uuid4())
    profile.record_ask_struggle(
        doc, strength=0.5, concepts=("variable",), latency_ms=500.0
    )
    cm = profile.mastery_by_concept["variable"]
    # Solo ASK_STRUGGLE: un evidence_count
    assert cm.evidence_count == 1
    profile.record_concept_evidence(
        "variable",
        EvidenceSample(kind=EvidenceKind.HIGH_LATENCY, score_ratio=0.5, latency_ms=12000),
    )
    assert profile.mastery_by_concept["variable"].evidence_count == 2
