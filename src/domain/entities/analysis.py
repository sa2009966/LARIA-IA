from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Analysis:
    """Entidad pura que representa el resultado de un análisis de IA."""
    id: Optional[int]
    document_id: int
    summary: str
    key_concepts: list[str]
    suggested_questions: list[str]
    model_used: str
    created_at: datetime = field(default_factory=datetime.utcnow)
