"""Ramas de PedagogicalMemory y StudentProfile."""
from __future__ import annotations

from uuid import uuid4

from src.domain.aggregates.student_profile import PedagogicalMemory, StudentProfile


def test_pedagogical_memory_remember_helpers():
    mem = PedagogicalMemory()
    mem.remember_misconception("")
    mem.remember_misconception("signo al despejar")
    mem.remember_misconception("signo al despejar")
    assert mem.frequent_misconceptions[0] == "signo al despejar"

    mem.remember_example("")
    mem.remember_example("ejemplo útil")
    mem.remember_example("ejemplo útil")
    assert mem.successful_examples[0] == "ejemplo útil"

    mem.remember_analogy("")
    mem.remember_analogy("como un balde")
    mem.remember_analogy("como un balde")
    assert mem.successful_analogies[0] == "como un balde"


def test_student_profile_record_paths():
    student = uuid4()
    doc = uuid4()
    profile = StudentProfile.create(student)
    profile.record_quiz_result(doc, 0.2)
    profile.record_quiz_result(doc, 0.9)
    profile.record_ask_struggle(doc, strength=0.8, concepts=("algebra",), help_level=0.5)
    profile.record_high_latency(doc, latency_ms=9000.0, concepts=("algebra",))
    profile.record_concept_result("algebra", score_ratio=0.6, document_id=doc)
    assert profile.total_attempts >= 2
    assert profile.total_struggle_signals >= 1
