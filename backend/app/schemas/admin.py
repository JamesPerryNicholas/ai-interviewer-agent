"""Administrator console request and response schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AdminLoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=128)


class AdminResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    created_at: datetime


class AdminTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    admin: AdminResponse


class AdminCreateUserRequest(BaseModel):
    username: str | None = Field(default=None, min_length=3, max_length=30)
    password: str | None = Field(default=None, min_length=8, max_length=128)


class AdminCreatedUserResponse(BaseModel):
    id: int
    username: str
    password: str
    email: str
    created_at: datetime


class AdminUserListItem(BaseModel):
    id: int
    username: str
    email: str
    created_at: datetime


class UsageDailyPoint(BaseModel):
    date: str
    total_tokens: int
    prompt_tokens: int
    completion_tokens: int


class UsageFeaturePoint(BaseModel):
    feature: str
    total_tokens: int
    calls: int


class UsageRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    feature: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: int
    created_at: datetime


class UsageSummaryResponse(BaseModel):
    range_days: int
    budget_tokens: int | None
    total_tokens: int
    total_calls: int
    prompt_tokens: int
    completion_tokens: int
    today_tokens: int
    daily: list[UsageDailyPoint]
    by_feature: list[UsageFeaturePoint]
    p50_latency_ms: int
    p90_latency_ms: int
    p99_latency_ms: int
    average_latency_ms: int
    recent: list[UsageRecordResponse]
    recent_total: int
    recent_page: int
    recent_page_size: int
