from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Document:
    """Entidad pura de dominio. Sin dependencias externas."""
    id: Optional[int]
    owner_id: int
    filename: str
    content: str
    subject: str
    uploaded_at: datetime = field(default_factory=_utc_now)
    analysis_result: Optional[str] = None

    def has_analysis(self) -> bool:
        return self.analysis_result is not None
