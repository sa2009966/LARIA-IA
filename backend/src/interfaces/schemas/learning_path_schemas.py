from datetime import datetime
from typing import Annotated, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field

ModuleStatus = Literal["locked", "available", "in_progress", "completed"]


class ModuleCreateItem(BaseModel):
    title: Annotated[str, Field(max_length=200)] = ""
    concept: Annotated[str, Field(min_length=1, max_length=200)]
    difficulty: Literal["easy", "medium", "hard"] = "easy"
    prerequisites: list[str] = []


class LearningPathCreateRequest(BaseModel):
    subject: Annotated[str, Field(min_length=1, max_length=128)]
    title: Annotated[Optional[str], Field(max_length=200)] = None
    modules: list[ModuleCreateItem] = []


class LearningModuleResponse(BaseModel):
    id: str
    title: str
    concept: str
    difficulty: str = "easy"
    prerequisites: list[str] = []
    status: ModuleStatus = "locked"
    mastery: float = 0.0
    position: int = 0


class LearningPathResponse(BaseModel):
    id: str
    subject: str
    title: str
    modules: list[LearningModuleResponse] = []
    progress: float = 0.0
    created_at: datetime
    updated_at: datetime


class LearningPathListResponse(BaseModel):
    paths: list[LearningPathResponse]


class ModuleMasteryRequest(BaseModel):
    mastery: Annotated[float, Field(ge=0.0, le=1.0)]
