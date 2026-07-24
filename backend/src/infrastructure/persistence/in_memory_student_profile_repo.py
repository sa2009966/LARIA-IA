from src.domain.aggregates.student_profile import ConceptMastery, DocumentMastery, StudentProfile
from typing import Optional
from uuid import UUID

from src.domain.exceptions import ConcurrencyError
from src.domain.ports.repositories import StudentProfileRepository


def _copy_concepts(src: dict[str, ConceptMastery]) -> dict[str, ConceptMastery]:
    return {
        k: ConceptMastery(
            concept_key=v.concept_key,
            attempts=v.attempts,
            mastery=v.mastery,
            last_score_ratio=v.last_score_ratio,
            document_ids=list(v.document_ids),
        )
        for k, v in src.items()
    }


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
            mastery_by_concept=_copy_concepts(profile.mastery_by_concept),
            frequent_errors=list(profile.frequent_errors),
            pace=profile.pace,
            total_attempts=profile.total_attempts,
            total_struggle_signals=profile.total_struggle_signals,
            updated_at=profile.updated_at,
            version=profile.version,
        )

    async def save(self, profile: StudentProfile) -> None:
        existing = self._profiles.get(profile.student_id)
        expected = int(profile.version)
        if existing is not None and existing.version != expected:
            raise ConcurrencyError("StudentProfile concurrent update")
        if existing is None and expected != 0:
            raise ConcurrencyError("StudentProfile concurrent update")
        new_version = expected + 1
        stored = StudentProfile(
            student_id=profile.student_id,
            mastery_by_document=_copy_mastery(profile.mastery_by_document),
            mastery_by_concept=_copy_concepts(profile.mastery_by_concept),
            frequent_errors=list(profile.frequent_errors),
            pace=profile.pace,
            total_attempts=profile.total_attempts,
            total_struggle_signals=profile.total_struggle_signals,
            updated_at=profile.updated_at,
            version=new_version,
        )
        self._profiles[profile.student_id] = stored
        profile.version = new_version
