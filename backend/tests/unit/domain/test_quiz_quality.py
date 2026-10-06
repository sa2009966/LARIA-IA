import pytest
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
        # Desde ADR-035 se baraja al azar: con 4 preguntas, que una letra salga 3 veces
        # pasa un 20 % de las veces (este test fallaba así). Lo que se protege es que no
        # haya sesgo de letra: con 400 preguntas todas en "A", ninguna letra pasa del 35 %.
        qs = [_q("A", f"p{i}") for i in range(400)]
        balanced = ensure_quiz_quality(qs)
        dist = answer_key_distribution(balanced)
        assert max(dist.values()) <= 140
        # El texto de la opción correcta se conserva (valor semántico).
        for original, fixed in zip(qs, balanced):
            assert fixed.options[fixed.correct_answer] == original.options[original.correct_answer]

    def test_barajar_conserva_el_significado(self):
        """Antes se dejaban las claves tal cual si no había sesgo > 60 %. Ahora
        siempre se barajan; lo que no puede cambiar es QUÉ texto es el correcto."""
        qs = [_q("A"), _q("B"), _q("C"), _q("D")]
        out = ensure_quiz_quality(qs)
        for antes, despues in zip(qs, out):
            assert despues.options[despues.correct_answer] == antes.options[antes.correct_answer]
            assert sorted(despues.options.values()) == sorted(antes.options.values())

    def test_rebalance_puro(self):
        qs = [_q("A"), _q("A")]
        out = rebalance_answer_keys(qs)
        assert out[0].correct_answer == "A"
        assert out[1].correct_answer != "A" or out[1].options[out[1].correct_answer] == "a"


def test_la_correcta_ya_no_cae_siempre_en_la_misma_letra():
    """Las clases devolvían la correcta casi siempre en la B. 400 preguntas con la
    correcta en B → tras barajar, ninguna letra pasa del 35 % (lo esperado es 25 %)."""
    from collections import Counter

    from src.domain.value_objects.question import QuizQuestion

    qs = [QuizQuestion(text=f"P{i}", options={"A": "a", "B": "b", "C": "c", "D": "d"}, correct_answer="B")
          for i in range(400)]
    out = ensure_quiz_quality(qs)

    reparto = Counter(q.correct_answer for q in out)
    assert max(reparto.values()) / len(out) < 0.35, reparto
    assert all(q.options[q.correct_answer] == "b" for q in out), "el significado no cambia"


def test_las_opciones_que_hablan_de_otras_no_se_barajan():
    from src.domain.value_objects.question import QuizQuestion

    q = QuizQuestion(text="?", options={"A": "uno", "B": "dos", "C": "A y B", "D": "Ninguna de las anteriores"},
                     correct_answer="C")

    assert ensure_quiz_quality([q])[0].options == q.options


@pytest.mark.asyncio
async def test_la_comprobacion_de_la_clase_tambien_se_baraja(monkeypatch):
    """La comprobación de la clase se guarda barajada: con un azar que invierte el
    orden, la correcta que el modelo puso en B termina en otra letra."""
    from unittest.mock import AsyncMock
    from uuid import uuid4

    from src.application.services.teaching_service import TeachingService
    from src.domain.aggregates.learning_path import LearningPathAggregate, LessonVariant
    from src.domain.ports.lesson_generator import Lesson
    from src.domain.services import quiz_quality
    from src.domain.value_objects.question import QuizQuestion

    class Invierte:
        def shuffle(self, x):
            x.reverse()

    monkeypatch.setattr(quiz_quality, "_RNG", Invierte())
    path = LearningPathAggregate.create_for_topic(uuid4(), "t", "T", [{"concept": "t"}])
    path.start_teaching("t", LessonVariant.INTRODUCE)
    paths, quizzes, gen = AsyncMock(), AsyncMock(), AsyncMock()
    paths.find_by_id.return_value = path
    gen.generate_lesson.return_value = Lesson(
        explanation="x" * 50, example="y" * 30, example_summary="y",
        check=tuple(QuizQuestion(text=f"P{i}", options={"A": "a", "B": "b", "C": "c", "D": "d"},
                                 correct_answer="B", concept_tags=("t",)) for i in range(2)),
    )
    perfiles = AsyncMock()
    perfiles.find_by_student.return_value = None
    servicio = TeachingService(paths, perfiles, quizzes, AsyncMock(), gen, AsyncMock())

    paso = await servicio.lesson(path.owner_id, path.id)

    assert all(q.correct_answer == "C" and q.options["C"] == "b" for q in paso.check.questions)
