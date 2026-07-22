from typing import Optional
from uuid import UUID

from src.domain.aggregates.student_profile import DocumentMastery, StudentProfile
from src.domain.ports.repositories import StudentProfileRepository


def _copy_mastery(src: dict[UUID, DocumentMastery]) -> dict[UUID, DocumentMastery]:
    return {
        k: DocumentMastery(
            document_id=v.document_id,
            attempts=v.attempts,
            mastery=v.mastery,
            last_score_ratio=v.last_score_ratio,
            incorrect_streak=v.incorrect_streak,
            struggle_signals=v.struggle_signals,
        )
        for k, v in src.items()
    }


class InMemoryStudentProfileRepository(StudentProfileRepository):

    def __init__(self) -> None:
        self._profiles: dict[UUID, StudentProfile] = {}

    async def find_by_student(self, student_id: UUID) -> Optional[StudentProfile]:
        profile = self._profiles.get(student_id)
        if profile is None:
            return None
        return StudentProfile(
            student_id=profile.student_id,
            mastery_by_document=_copy_mastery(profile.mastery_by_document),
            frequent_errors=list(profile.frequent_errors),
            pace=profile.pace,
            total_attempts=profile.total_attempts,
            total_struggle_signals=profile.total_struggle_signals,
            updated_at=profile.updated_at,
        )

    async def save(self, profile: StudentProfile) -> None:
        self._profiles[profile.student_id] = StudentProfile(
            student_id=profile.student_id,
            mastery_by_document=_copy_mastery(profile.mastery_by_document),
            frequent_errors=list(profile.frequent_errors),
            pace=profile.pace,
            total_attempts=profile.total_attempts,
            total_struggle_signals=profile.total_struggle_signals,
            updated_at=profile.updated_at,
        )
