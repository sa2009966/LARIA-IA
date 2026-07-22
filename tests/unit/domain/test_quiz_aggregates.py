from uuid import uuid4

import pytest

from src.domain.aggregates.quiz_aggregate import QuizAggregate
from src.domain.aggregates.quiz_attempt_aggregate import QuizAttemptAggregate
from src.domain.aggregates.tutor_interaction import TutorInteractionAggregate
from src.domain.value_objects.question import Difficulty, QuizQuestion


def _sample_questions() -> list[QuizQuestion]:
    return [
        QuizQuestion(
            text="¿2+2?",
            options={"A": "3", "B": "4", "C": "5", "D": "6"},
            correct_answer="B",
            difficulty=Difficulty.EASY,
        ),
        QuizQuestion(
            text="¿Capital de Francia?",
            options={"A": "Madrid", "B": "Roma", "C": "París", "D": "Berlín"},
            correct_answer="C",
            difficulty=Difficulty.MEDIUM,
        ),
    ]


class TestQuizAggregate:
    def test_create_emite_evento(self):
        doc_id, owner_id = uuid4(), uuid4()
        quiz = QuizAggregate.create(doc_id, owner_id, _sample_questions())
        assert quiz.document_id == doc_id
        assert quiz.owner_id == owner_id
        assert len(quiz.questions) == 2
        assert quiz.total_points == 20
        assert quiz.events[0].event_type == "QuizGeneratedEvent"
        assert quiz.events[0].num_questions == 2

    def test_create_vacio_falla(self):
        with pytest.raises(ValueError, match="al menos una pregunta"):
            QuizAggregate.create(uuid4(), uuid4(), [])

    def test_grade_todo_correcto(self):
        quiz = QuizAggregate.create(uuid4(), uuid4(), _sample_questions())
        grade = quiz.grade({0: "B", 1: "C"})
        assert grade.score == 20
        assert grade.total_points == 20
        assert grade.per_question_correct == (True, True)
        assert grade.correct_count == 2

    def test_grade_parcial(self):
        quiz = QuizAggregate.create(uuid4(), uuid4(), _sample_questions())
        grade = quiz.grade({0: "B", 1: "A"})
        assert grade.score == 10
        assert grade.per_question_correct == (True, False)

    def test_grade_incompleto_rechazado(self):
        quiz = QuizAggregate.create(uuid4(), uuid4(), _sample_questions())
        with pytest.raises(ValueError, match="intento incompleto"):
            quiz.grade({0: "B"})

    def test_grade_sin_respuestas_falla(self):
        quiz = QuizAggregate.create(uuid4(), uuid4(), _sample_questions())
        with pytest.raises(ValueError, match="intento incompleto"):
            quiz.grade({})

    def test_grade_indice_invalido(self):
        quiz = QuizAggregate.create(uuid4(), uuid4(), _sample_questions())
        with pytest.raises(ValueError, match="intento incompleto|Índice"):
            quiz.grade({5: "A"})

    def test_grade_opcion_invalida(self):
        quiz = QuizAggregate.create(uuid4(), uuid4(), _sample_questions())
        with pytest.raises(ValueError, match="no válida"):
            quiz.grade({0: "Z", 1: "C"})

    def test_normaliza_difficulty_string(self):
        qs = [
            QuizQuestion(
                text="P",
                options={"A": "1", "B": "2"},
                correct_answer="A",
                difficulty="hard",
            )
        ]
        quiz = QuizAggregate.create(uuid4(), uuid4(), qs)
        assert quiz.questions[0].difficulty == Difficulty.HARD


class TestQuizAttemptAggregate:
    def test_create_emite_evento(self):
        quiz = QuizAggregate.create(uuid4(), uuid4(), _sample_questions())
        grade = quiz.grade({0: "B", 1: "C"})
        student = uuid4()
        attempt = QuizAttemptAggregate.create(
            quiz_id=quiz.id,
            document_id=quiz.document_id,
            student_id=student,
            answers={0: "B", 1: "C"},
            grade=grade,
        )
        assert attempt.score == 20
        assert attempt.events[0].event_type == "QuizAttemptCompletedEvent"
        assert attempt.events[0].student_id == student
        assert attempt.events[0].score == 20
        assert attempt.events[0].total == 20


class TestTutorInteractionAggregate:
    def test_create_ok(self):
        inter = TutorInteractionAggregate.create(
            student_id=uuid4(),
            document_id=uuid4(),
            question="  ¿Qué es?  ",
            answer="  Una explicación.  ",
        )
        assert inter.question == "¿Qué es?"
        assert inter.answer == "Una explicación."

    def test_create_pregunta_vacia(self):
        with pytest.raises(ValueError, match="pregunta"):
            TutorInteractionAggregate.create(uuid4(), uuid4(), "  ", "resp")

    def test_create_respuesta_vacia(self):
        with pytest.raises(ValueError, match="respuesta"):
            TutorInteractionAggregate.create(uuid4(), uuid4(), "preg", "")
