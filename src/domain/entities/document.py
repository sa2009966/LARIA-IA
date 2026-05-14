from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Document:
    """Entidad pura de dominio. Sin dependencias externas."""
    id: Optional[int]
    owner_id: int
    filename: str
    content: str
    subject: str
    uploaded_at: datetime = field(default_factory=datetime.utcnow)
    analysis_result: Optional[str] = None

    def has_analysis(self) -> bool:
        return self.analysis_result is not None
