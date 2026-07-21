"""Helpers compartidos para mapear DTOs/aggregados de quiz a schemas HTTP."""
from src.interfaces.schemas.quiz_schemas import QuizPublicResponse, QuizQuestionPublicItem


def quiz_to_public_response(quiz) -> QuizPublicResponse:
    return QuizPublicResponse(
        id=str(quiz.id),
        document_id=str(quiz.document_id),
        questions=[
            QuizQuestionPublicItem(
                index=q.index,
                text=q.text,
                options=q.options,
                difficulty=q.difficulty,
            )
            for q in quiz.questions
        ],
        total_points=quiz.total_points,
        created_at=quiz.created_at,
    )
