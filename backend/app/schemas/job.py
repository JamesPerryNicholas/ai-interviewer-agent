"""Pydantic schemas for job position APIs."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class JobPositionCreate(BaseModel):
    """Request body for saving one job description."""

    company: str = Field(min_length=1, max_length=150)
    position: str = Field(min_length=1, max_length=150)
    description: str = Field(min_length=1)


class JobPositionResponse(BaseModel):
    """Public job position response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    company: str
    position: str
    description: str
    created_at: datetime
