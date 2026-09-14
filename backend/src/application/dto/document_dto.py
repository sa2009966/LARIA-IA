from dataclasses import dataclass
from datetime import datetime
from uuid import UUID
from typing import Optional


@dataclass
class UploadDocumentDTO:
    filename: str
    content: str
    subject: str


@dataclass
class DocumentDTO:
    id: UUID
    owner_id: UUID
    filename: str
    subject: str
    status: str
    uploaded_at: datetime
    has_analysis: bool
    error_message: Optional[str] = None


@dataclass
class DocumentListDTO:
    documents: list[DocumentDTO]
    total: int
