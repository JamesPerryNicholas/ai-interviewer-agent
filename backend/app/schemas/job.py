"""Pydantic schemas for job position APIs."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.config import settings


class JobPositionCreate(BaseModel):
    """Request body for saving one job description."""

    company: str = Field(min_length=1, max_length=150)
    position: str = Field(min_length=1, max_length=150)
    description: str = Field(min_length=1)

    @field_validator("description")
    @classmethod
    def validate_description_size(cls, value: str) -> str:
        if len(value) > settings.max_job_description_chars:
            raise ValueError(
                f"岗位描述不能超过 {settings.max_job_description_chars} 个字符"
            )
        return value


class JobPositionResponse(BaseModel):
    """Public job position response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    company: str
    position: str
    description: str
    created_at: datetime
