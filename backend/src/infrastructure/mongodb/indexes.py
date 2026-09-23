"""Índices Mongo para colecciones calientes (arranque)."""
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.infrastructure.mongodb.database import get_database


async def ensure_all_indexes(database: AsyncIOMotorDatabase | None = None) -> None:
    db = database or await get_database()
    await db.users.create_index("email", unique=True)
    await db.users.create_index("username", unique=True)
    await db.documents.create_index("owner_id")
    await db.quizzes.create_index("document_id")
    await db.quizzes.create_index("owner_id")
    await db.quiz_attempts.create_index("student_id")
    await db.quiz_attempts.create_index("document_id")
    await db.tutor_interactions.create_index("student_id")
    await db.tutor_interactions.create_index("document_id")
    await db.tutor_sessions.create_index("document_id")
    await db.tutor_sessions.create_index(
        [("student_id", 1), ("document_id", 1)],
        unique=True,
    )
    await db.event_outbox.create_index("processed_at")
    await db.event_outbox.create_index([("processed_at", 1), ("created_at", 1)])
    # Sostiene la reclamación atómica del worker: pendientes, sin reclamar (o
    # con reclamación caducada), en orden de llegada.
    await db.event_outbox.create_index(
        [("processed_at", 1), ("claimed_at", 1), ("created_at", 1)]
    )
    await db.chats.create_index("owner_id")
    await db.chats.create_index("updated_at")
    await db.learning_paths.create_index("owner_id")
    # El grafo se busca por _id (graph_id); el índice sirve a la vista de
    # curación, que lista grafos por recencia de edición.
    await db.concept_graphs.create_index("updated_at")
