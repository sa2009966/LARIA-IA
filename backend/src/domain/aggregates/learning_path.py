from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID, uuid4

from src.domain.concept_identity import canonicalize_concept
from src.domain.value_objects.question import Difficulty


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


ModuleStatus = Literal["locked", "available", "in_progress", "completed"]


@dataclass
class LearningModule:
    """Unidad de la ruta de aprendizaje con estado y progreso propio."""

    id: UUID = field(default_factory=uuid4)
    title: str = ""
    concept: str = ""
    difficulty: Difficulty = Difficulty.EASY
    prerequisites: list[str] = field(default_factory=list)
    status: ModuleStatus = "locked"
    mastery: float = 0.0
    position: int = 0


@dataclass
class LearningPathAggregate:
    """Ruta de aprendizaje de un estudiante sobre una materia/tema.

    Es un grafo ordenado de módulos (conceptos) encadenados por prerrequisitos.
    LARIA desbloquea módulos según el mastery previo y puertas de prerrequisito.
    """

    id: UUID = field(default_factory=uuid4)
    owner_id: UUID = field(default_factory=uuid4)
    subject: str = ""
    title: str = ""
    modules: list[LearningModule] = field(default_factory=list)
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)

    @staticmethod
    def create(
        owner_id: UUID,
        subject: str,
        title: str | None = None,
        modules: list[dict] | None = None,
    ) -> "LearningPathAggregate":
        subject = (subject or "").strip()
        if not subject:
            raise ValueError("La materia no puede estar vacía")
        path = LearningPathAggregate(
            owner_id=owner_id,
            subject=subject,
            title=(title or "Ruta de aprendizaje").strip(),
        )
        for i, m in enumerate(modules or []):
            concept = canonicalize_concept(m.get("concept", "") or "")
            if not concept:
                continue
            diff = m.get("difficulty", Difficulty.EASY)
            if isinstance(diff, str):
                diff = Difficulty(diff)
            path.modules.append(
                LearningModule(
                    title=m.get("title", "").strip() or concept,
                    concept=concept,
                    difficulty=diff,
                    prerequisites=[canonicalize_concept(p) for p in m.get("prerequisites", []) if p],
                    status="available" if i == 0 else "locked",
                    position=i,
                )
            )
        # Abrir el primer módulo que no tenga prerequisitos satisficible:
        # si todos están locked, desbloquear el primero con prerequisitos vacíos.
        if path.modules and all(m.status == "locked" for m in path.modules):
            first = next((m for m in path.modules if not m.prerequisites), path.modules[0])
            first.status = "available"
        return path

    def _module_by_concept(self, concept: str) -> LearningModule | None:
        key = canonicalize_concept(concept)
        return next((m for m in self.modules if m.concept == key), None)

    def record_mastery(self, concept: str, mastery: float) -> None:
        """Actualiza el mastery de un módulo y desbloquea los que dependen de él."""
        mod = self._module_by_concept(concept)
        if mod is None:
            return
        mod.mastery = max(0.0, min(1.0, mastery))
        if mastery >= 0.7:
            mod.status = "completed"
        elif mastery > 0.0:
            mod.status = "in_progress"
        self._unlock_dependents()
        self.updated_at = _utc_now()

    def _unlock_dependents(self) -> None:
        for mod in self.modules:
            if mod.status == "completed":
                continue
            if not mod.prerequisites:
                continue
            # Un módulo se desbloquea si TODOS sus prerrequisitos están completados.
            prereqs_done = all(
                (self._module_by_concept(p) is not None and self._module_by_concept(p).status == "completed")
                for p in mod.prerequisites
            )
            if prereqs_done and mod.status == "locked":
                mod.status = "available"

    @property
    def progress(self) -> float:
        if not self.modules:
            return 0.0
        return sum(1 for m in self.modules if m.status == "completed") / len(self.modules)

    def is_owned_by(self, user_id: UUID) -> bool:
        return self.owner_id == user_id
