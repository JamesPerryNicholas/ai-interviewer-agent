"""Pydantic schemas for interview sessions and chat messages."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class InterviewStartRequest(BaseModel):
    """Resources used to create a new interview session."""

    resume_id: int = Field(gt=0)
    job_id: int = Field(gt=0)


class InterviewChatRequest(BaseModel):
    """A candidate answer sent to an active interview."""

    interview_id: int = Field(gt=0)
    message: str = Field(min_length=1, max_length=10_000)


class InterviewResponse(BaseModel):
    """Public interview session fields."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    resume_id: int
    job_id: int
    position: str | None = None
    status: str
    completed_questions: int = 0
    total_questions: int = 0
    start_time: datetime
    end_time: datetime | None = None


class MessageResponse(BaseModel):
    """A persisted interview message."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    interview_id: int
    role: Literal["user", "assistant"]
    content: str
    token_count: int | None = None
    created_at: datetime


class InterviewStartResponse(BaseModel):
    """Session plus the first assistant question."""

    interview: InterviewResponse
    first_message: MessageResponse


class InterviewChatResponse(BaseModel):
    """The assistant response after a candidate answer."""

    interview_id: int
    message: MessageResponse | None = None


class InterviewHistoryResponse(BaseModel):
    """An interview and all persisted messages in chronological order."""

    interview: InterviewResponse
    messages: list[MessageResponse]


class InterviewListItem(BaseModel):
    """Compact interview row used by the dashboard history list."""

    id: int
    position: str | None = None
    status: str
    start_time: datetime
    end_time: datetime | None = None
    report_id: int | None = None
    total_score: int | None = None
