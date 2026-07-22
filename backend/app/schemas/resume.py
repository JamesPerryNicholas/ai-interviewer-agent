"""Pydantic v2 schemas for resume APIs."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ResumeCreate(BaseModel):
    """Internal resume data shape used when creating a database record."""

    user_id: int
    original_filename: str
    file_url: str
    content: str
    extracted_info: dict[str, Any] | None = None


class ResumeAnalysisResponse(BaseModel):
    """Validated structured capability profile returned by the LLM."""

    skills: list[str] = Field(default_factory=list)
    projects: list[str] = Field(default_factory=list)
    experience: str = ""
    level: str = "unknown"
    suggestions: list[str] = Field(default_factory=list)


class ResumeResponse(BaseModel):
    """Public resume response including the extracted plain text."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    original_filename: str
    file_url: str
    content: str
    created_at: datetime
    extracted_info: ResumeAnalysisResponse | None = None
