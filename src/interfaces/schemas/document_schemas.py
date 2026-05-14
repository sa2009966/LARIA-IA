from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class DocumentUploadRequest(BaseModel):
    filename: str
    content: str
    subject: str


class DocumentResponse(BaseModel):
    id: int
    owner_id: int
    filename: str
    subject: str
    uploaded_at: datetime
    analysis_result: Optional[str] = None

    model_config = {"from_attributes": True}


class QuestionRequest(BaseModel):
    question: str


class QuestionResponse(BaseModel):
    answer: str


class AnalysisResponse(BaseModel):
    document_id: int
    summary: str
    key_concepts: list[str]
    suggested_questions: list[str]
    model_used: str
