"""Pydantic schemas for interview evaluation reports."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.interview import InterviewResponse


class AnswerEvaluationPayload(BaseModel):
    """Hidden per-answer evaluation returned only when the interview ends."""

    score: int = Field(ge=0, le=100)
    analysis: str = Field(min_length=1)


class EvaluationPayload(BaseModel):
    """Strict JSON shape expected from the evaluation model."""

    total_score: int = Field(ge=0, le=100)
    technical_score: int = Field(ge=0, le=100)
    communication_score: int = Field(ge=0, le=100)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    answer_evaluations: list[AnswerEvaluationPayload] = Field(default_factory=list)


class AnswerEvaluationResponse(BaseModel):
    """Per-answer details exposed inside the final report."""

    id: int
    question_id: int | None = None
    question: str | None = None
    answer: str
    score: int | None = None
    analysis: str | None = None
    created_at: datetime


class EvaluationReportResponse(EvaluationPayload):
    """Public evaluation report fields."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    interview_id: int
    created_at: datetime
    answers: list[AnswerEvaluationResponse] = Field(default_factory=list)


class InterviewFinishResponse(BaseModel):
    """Interview state and report returned after finishing a session."""

    interview: InterviewResponse
    report: EvaluationReportResponse
