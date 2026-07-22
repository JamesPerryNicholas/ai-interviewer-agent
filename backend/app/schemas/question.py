"""Pydantic schemas for generated interview questions."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class GenerateQuestionsRequest(BaseModel):
    """Request body for generating questions from a resume and job."""

    resume_id: int = Field(gt=0)
    job_id: int = Field(gt=0)


class GeneratedQuestion(BaseModel):
    """Validated model output before it is persisted."""

    question: str = Field(min_length=1)
    category: str = Field(min_length=1, max_length=80)
    difficulty: str = Field(min_length=1, max_length=30)


class QuestionResponse(GeneratedQuestion):
    """Persisted interview question response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int
    answer: str | None = None
    created_at: datetime
