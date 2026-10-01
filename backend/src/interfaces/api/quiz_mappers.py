"""Helpers compartidos para mapear DTOs/aggregados de quiz a schemas HTTP."""
from src.interfaces.schemas.quiz_schemas import QuizPublicResponse, QuizQuestionPublicItem


def quiz_to_public_response(quiz) -> QuizPublicResponse:
    return QuizPublicResponse(
        id=str(quiz.id),
        document_id=str(quiz.document_id) if quiz.document_id else None,
        topic=getattr(quiz, "topic", None),
        topic_label=getattr(quiz, "topic_label", None),
        questions=[
            QuizQuestionPublicItem(
                # DTO (trae `index`) o agregado (posición en la lista): los dos sirven.
                index=getattr(q, "index", i),
                text=q.text,
                options=q.options,
                difficulty=getattr(q.difficulty, "value", q.difficulty),
            )
            for i, q in enumerate(quiz.questions)
        ],
        total_points=quiz.total_points,
        created_at=quiz.created_at,
    )
