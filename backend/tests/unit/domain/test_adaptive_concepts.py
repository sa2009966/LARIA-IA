from uuid import uuid4

from src.domain.aggregates.student_profile import StudentProfile
from src.domain.aggregates.tutor_session import SessionStep, TutorSession
from src.domain.services.concept_tagger import ConceptTagger
from src.domain.services.context_selector import ContextSelector
from src.domain.services.pedagogical_engine import (
    PedagogicalEngine,
    PedagogicalMode,
    TutorIntent,
)
from src.domain.value_objects.question import Difficulty, QuizQuestion
from src.domain.aggregates.document_aggregate import DocumentAggregate


class TestConceptTagger:
    def test_tags_variable_question(self):
        q = QuizQuestion(
            text="¿Qué es una variable en álgebra?",
            options={"A": "x", "B": "2", "C": "+", "D": "="},
            correct_answer="A",
        )
        tagged = ConceptTagger().tag_question(q)
        assert "variable" in tagged.concept_tags


class TestConceptMasteryProjection:
    def test_item_failures_update_concepts(self):
        profile = StudentProfile.create(uuid4())
        doc = uuid4()
        profile.record_quiz_result(
            document_id=doc,
            score_ratio=0.0,
            missed_concepts=("variable", "ecuacion"),
            concept_results=(("variable", 0.0), ("ecuacion", 0.0), ("distributiva", 1.0)),
        )
        assert profile.concept_mastery_for("variable") == 0.0
        assert profile.concept_mastery_for("distributiva") == 1.0
        assert profile.weakest_concepts(limit=1)[0] in ("variable", "ecuacion")


class TestEngineFocusByConcept:
    def test_two_profiles_different_focus(self):
        doc = uuid4()
        weak_eq = StudentProfile.create(uuid4())
        weak_eq.record_concept_result("ecuacion", 0.1, document_id=doc)
        weak_eq.record_concept_result("variable", 0.9, document_id=doc)
        weak_eq.record_quiz_result(doc, 0.5)

        weak_var = StudentProfile.create(uuid4())
        weak_var.record_concept_result("variable", 0.1, document_id=doc)
        weak_var.record_concept_result("ecuacion", 0.9, document_id=doc)
        weak_var.record_quiz_result(doc, 0.5)

        engine = PedagogicalEngine()
        d1 = engine.select(weak_eq, doc, TutorIntent.ASK)
        d2 = engine.select(weak_var, doc, TutorIntent.ASK)
        assert d1.focus_concepts[0] != d2.focus_concepts[0]
        assert "ecuacion" in d1.focus_concepts
        assert "variable" in d2.focus_concepts


class TestTutorSessionMultiTurn:
    def test_second_ask_advances_to_hint(self):
        s = TutorSession.start(uuid4(), uuid4(), focus_concepts=("variable",))
        s.record_ask(hint_summary="pista 1", focus=("variable",))
        assert s.step == SessionStep.HINT
        s.record_ask(hint_summary="pista 2")
        assert s.step == SessionStep.PRACTICE
        assert len(s.hints_given) == 2

        engine = PedagogicalEngine()
        profile = StudentProfile.create(s.student_id)
        profile.record_concept_result("variable", 0.2, document_id=s.document_id)
        d = engine.select(profile, s.document_id, TutorIntent.ASK, session=s)
        assert "pista" in d.objective.lower() or d.mode == PedagogicalMode.SCAFFOLD


class TestContextSelector:
    def test_focus_filters_paragraphs(self):
        owner = uuid4()
        content = (
            "Sección variables\n\n"
            "Una variable es una letra como x.\n\n"
            "Sección historia\n\n"
            "La revolución francesa ocurrió en 1789."
        )
        doc = DocumentAggregate.upload(owner, "t.txt", content, "Matemática")
        ctx = ContextSelector().select(doc, ("variable",), max_chars=2000)
        assert "variable" in ctx.lower() or "letra" in ctx.lower()
        assert "1789" not in ctx
