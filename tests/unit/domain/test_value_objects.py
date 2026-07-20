import pytest

from src.domain.value_objects.email import Email
from src.domain.value_objects.password import Password
from src.domain.value_objects.subject import Subject
from src.domain.value_objects.question import (
    Question, Difficulty, BloomLevel,
    QuizQuestion, Quiz,
)
from src.domain.value_objects.analysis_result import AnalysisResult


class TestEmail:
    def test_valid_email(self):
        email = Email("user@example.com")
        assert email.value == "user@example.com"

    def test_valid_email_with_dots(self):
        email = Email("user.name@example.co.uk")
        assert email.value == "user.name@example.co.uk"

    def test_valid_email_with_plus(self):
        email = Email("user+tag@example.com")
        assert email.value == "user+tag@example.com"

    def test_invalid_email_no_at(self):
        with pytest.raises(ValueError, match="Email invalido"):
            Email("userexample.com")

    def test_invalid_email_empty(self):
        with pytest.raises(ValueError, match="Email invalido"):
            Email("")

    def test_invalid_email_spaces(self):
        with pytest.raises(ValueError, match="Email invalido"):
            Email("user @example.com")

    def test_email_immutable(self):
        email = Email("user@example.com")
        with pytest.raises(Exception):
            email.value = "other@example.com"

    def test_email_equality(self):
        a = Email("user@example.com")
        b = Email("user@example.com")
        assert a == b
        assert hash(a) == hash(b)

    def test_email_str(self):
        email = Email("user@example.com")
        assert str(email) == "user@example.com"
        assert repr(email) == "Email(user@example.com)"


class TestPassword:
    def test_valid_password(self):
        pw = Password("securePass1")
        assert pw.value == "securePass1"

    def test_too_short_password(self):
        with pytest.raises(ValueError, match="at least 8"):
            Password("Ab1")

    def test_weak_password_all_lowercase(self):
        pw = Password("abcdefgh")
        assert pw.is_weak() is True

    def test_weak_password_no_digit(self):
        pw = Password("Abcdefgh")
        assert pw.is_weak() is True

    def test_strong_password(self):
        pw = Password("Abcdefgh1jkl")
        assert pw.is_weak() is False

    def test_password_str_hidden(self):
        pw = Password("securePass1")
        assert str(pw) == "****"
        assert repr(pw) == "Password(****)"

    def test_password_immutable(self):
        pw = Password("securePass1")
        with pytest.raises(Exception):
            pw.value = "changed"


class TestSubject:
    def test_valid_subject(self):
        subject = Subject("Matemática")
        assert subject.value == "Matemática"

    def test_valid_subject_spanish_alt(self):
        subject = Subject("Fisica")
        assert subject.value == "Fisica"

    def test_invalid_subject(self):
        with pytest.raises(ValueError, match="invalido"):
            Subject("Astrología")

    def test_empty_subject(self):
        with pytest.raises(ValueError):
            Subject("")

    def test_subject_str(self):
        s = Subject("Historia")
        assert str(s) == "Historia"

    def test_subject_immutable(self):
        s = Subject("Biología")
        with pytest.raises(Exception):
            s.value = "Física"


class TestQuestion:
    def test_create_question_default(self):
        q = Question("¿Qué es la fotosíntesis?")
        assert q.text == "¿Qué es la fotosíntesis?"
        assert q.difficulty == Difficulty.EASY
        assert q.bloom_level == BloomLevel.REMEMBER

    def test_create_question_with_difficulty(self):
        q = Question("Explica la relatividad", difficulty=Difficulty.HARD)
        assert q.difficulty == Difficulty.HARD
        assert q.bloom_level == BloomLevel.REMEMBER

    def test_create_question_with_bloom(self):
        q = Question("Crea un modelo", bloom_level=BloomLevel.CREATE)
        assert q.bloom_level == BloomLevel.CREATE

    def test_empty_question_text(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            Question("")

    def test_question_too_long(self):
        with pytest.raises(ValueError, match="4000"):
            Question("a" * 4001)

    def test_question_immutable(self):
        q = Question("Test")
        with pytest.raises(Exception):
            q.text = "Changed"


class TestQuizQuestion:
    def test_valid_quiz_question(self):
        qq = QuizQuestion(
            text="¿2+2?",
            options={"A": "3", "B": "4", "C": "5", "D": "6"},
            correct_answer="B"
        )
        assert qq.text == "¿2+2?"
        assert qq.correct_answer == "B"

    def test_correct_answer_not_in_options(self):
        with pytest.raises(ValueError, match="not in options"):
            QuizQuestion(
                text="Test",
                options={"A": "1", "B": "2"},
                correct_answer="C"
            )

    def test_less_than_two_options(self):
        with pytest.raises(ValueError, match="at least 2"):
            QuizQuestion(
                text="Test",
                options={"A": "1"},
                correct_answer="A"
            )

    def test_invalid_option_key(self):
        with pytest.raises(ValueError, match="single character"):
            QuizQuestion(
                text="Test",
                options={"AA": "1", "B": "2"},
                correct_answer="AA"
            )

    def test_quiz_question_immutable(self):
        qq = QuizQuestion(
            text="Test",
            options={"A": "1", "B": "2"},
            correct_answer="A"
        )
        with pytest.raises(Exception):
            qq.text = "Changed"


class TestQuiz:
    def test_empty_quiz(self):
        quiz = Quiz()
        assert quiz.total_points == 0
        assert quiz.total_questions == 0

    def test_quiz_with_questions(self):
        qq = QuizQuestion(
            text="Test",
            options={"A": "1", "B": "2"},
            correct_answer="A"
        )
        quiz = Quiz(questions=[qq, qq])
        assert quiz.total_questions == 2
        assert quiz.total_points == 20

    def test_quiz_immutable(self):
        qq = QuizQuestion(
            text="Test",
            options={"A": "1", "B": "2"},
            correct_answer="A"
        )
        quiz = Quiz(questions=[qq])
        with pytest.raises(Exception):
            quiz.questions = []


class TestAnalysisResult:
    def test_valid_analysis_result(self):
        result = AnalysisResult(
            summary="Resumen del documento",
            confidence_score=0.95
        )
        assert result.summary == "Resumen del documento"
        assert result.confidence_score == 0.95
        assert result.key_concepts == []
        assert result.suggested_questions == []

    def test_empty_summary(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            AnalysisResult(summary="")

    def test_summary_too_long(self):
        with pytest.raises(ValueError, match="10000"):
            AnalysisResult(summary="a" * 10001)

    def test_confidence_score_too_low(self):
        with pytest.raises(ValueError, match="between 0 and 1"):
            AnalysisResult(summary="Test", confidence_score=-0.1)

    def test_confidence_score_too_high(self):
        with pytest.raises(ValueError, match="between 0 and 1"):
            AnalysisResult(summary="Test", confidence_score=1.5)

    def test_confidence_score_valid_edge(self):
        result = AnalysisResult(summary="Test", confidence_score=0.0)
        assert result.confidence_score == 0.0
        result2 = AnalysisResult(summary="Test", confidence_score=1.0)
        assert result2.confidence_score == 1.0

    def test_sorted_concepts(self):
        result = AnalysisResult(
            summary="Test",
            key_concepts=[("bajo", 0.3), ("alto", 0.9), ("medio", 0.6)]
        )
        assert result.sorted_concepts == ["alto", "medio", "bajo"]

    def test_analysis_result_immutable(self):
        result = AnalysisResult(summary="Test")
        with pytest.raises(Exception):
            result.summary = "Changed"
