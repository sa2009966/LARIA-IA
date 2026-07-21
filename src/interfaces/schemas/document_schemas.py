from datetime import datetime
from typing import Annotated, Optional

from pydantic import BaseModel, Field


class DocumentUploadRequest(BaseModel):
    filename: Annotated[str, Field(min_length=1, max_length=255)]
    content: Annotated[str, Field(min_length=1, max_length=100_000, description="Texto completo del material")]
    subject: Annotated[str, Field(min_length=1, max_length=128)]


class DocumentResponse(BaseModel):
    id: str
    owner_id: str
    filename: str
    subject: str
    status: str
    uploaded_at: datetime
    has_analysis: bool
    error_message: Optional[str] = None

    model_config = {"from_attributes": True}


class QuestionRequest(BaseModel):
    question: Annotated[str, Field(min_length=1, max_length=4000)]


class QuestionResponse(BaseModel):
    answer: str


class AnalysisResponse(BaseModel):
    summary: str
    key_concepts: list[str]
    suggested_questions: list[str]
