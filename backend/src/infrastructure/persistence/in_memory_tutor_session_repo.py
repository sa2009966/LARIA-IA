from typing import Optional
from uuid import UUID

from src.domain.aggregates.tutor_session import TutorSession
from src.domain.exceptions import ConcurrencyError
from src.domain.ports.repositories import TutorSessionRepository


class InMemoryTutorSessionRepository(TutorSessionRepository):

    def __init__(self) -> None:
        self._sessions: dict[tuple[UUID, UUID], TutorSession] = {}

    async def find_by_student_document(
        self, student_id: UUID, document_id: UUID
    ) -> Optional[TutorSession]:
        session = self._sessions.get((student_id, document_id))
        if session is None:
            return None
        return TutorSession(
            id=session.id,
            student_id=session.student_id,
            document_id=session.document_id,
            step=session.step,
            objective=session.objective,
            focus_concepts=list(session.focus_concepts),
            hints_given=list(session.hints_given),
            turns=session.turns,
            updated_at=session.updated_at,
            version=session.version,
        )

    async def save(self, session: TutorSession) -> None:
        key = (session.student_id, session.document_id)
        existing = self._sessions.get(key)
        expected = int(session.version)
        if existing is not None and existing.version != expected:
            raise ConcurrencyError("TutorSession concurrent update")
        if existing is None and expected != 0:
            raise ConcurrencyError("TutorSession concurrent update")
        new_version = expected + 1
        stored = TutorSession(
            id=session.id,
            student_id=session.student_id,
            document_id=session.document_id,
            step=session.step,
            objective=session.objective,
            focus_concepts=list(session.focus_concepts),
            hints_given=list(session.hints_given),
            turns=session.turns,
            updated_at=session.updated_at,
            version=new_version,
        )
        self._sessions[key] = stored
        session.version = new_version

    async def delete_by_document(self, document_id: UUID) -> int:
        keys = [k for k in self._sessions if k[1] == document_id]
        for k in keys:
            del self._sessions[k]
        return len(keys)
