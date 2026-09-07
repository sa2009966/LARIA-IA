from src.domain.services.quiz_quality import (
    answer_key_distribution,
    ensure_quiz_quality,
    is_answer_key_skewed,
    rebalance_answer_keys,
)
from src.domain.value_objects.question import Difficulty, QuizQuestion


def _q(correct: str, text: str = "P") -> QuizQuestion:
    return QuizQuestion(
        text=text,
        options={"A": "a", "B": "b", "C": "c", "D": "d"},
        correct_answer=correct,
        difficulty=Difficulty.EASY,
    )


class TestQuizQuality:
    def test_detecta_sesgo_todo_a(self):
        qs = [_q("A"), _q("A"), _q("A")]
        assert is_answer_key_skewed(qs) is True

    def test_reequilibra_claves(self):
        qs = [_q("A", "p1"), _q("A", "p2"), _q("A", "p3"), _q("A", "p4")]
        balanced = ensure_quiz_quality(qs)
        dist = answer_key_distribution(balanced)
        assert max(dist.values()) <= 2
        # El texto de la opción correcta se conserva (valor semántico).
        for original, fixed in zip(qs, balanced):
            assert fixed.options[fixed.correct_answer] == original.options[original.correct_answer]

    def test_sin_sesgo_no_cambia_claves(self):
        qs = [_q("A"), _q("B"), _q("C"), _q("D")]
        out = ensure_quiz_quality(qs)
        assert [q.correct_answer for q in out] == ["A", "B", "C", "D"]

    def test_rebalance_puro(self):
        qs = [_q("A"), _q("A")]
        out = rebalance_answer_keys(qs)
        assert out[0].correct_answer == "A"
        assert out[1].correct_answer != "A" or out[1].options[out[1].correct_answer] == "a"
