"""Pydantic v2 schemas for authentication endpoints."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


CAREER_STATUSES = (
    "在校学生",
    "应届毕业生",
    "实习求职",
    "社招求职",
    "已就业（准备跳槽）",
)


class UserRegister(BaseModel):
    """Payload used to create a new user account."""

    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserLogin(BaseModel):
    """Payload used to authenticate an existing user."""

    account: str | None = Field(default=None, min_length=1, max_length=255)
    # Backward-compatible API field for existing clients.
    email: EmailStr | None = None
    password: str = Field(min_length=1, max_length=128)

    @model_validator(mode="after")
    def validate_account(self) -> "UserLogin":
        """Require either the new account field or the legacy email field."""

        if not self.account and not self.email:
            raise ValueError("Account is required")
        return self


class UserResponse(BaseModel):
    """Public user representation; never exposes password_hash."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    display_name: str | None = None
    career_status: str
    email: EmailStr
    avatar_url: str | None = None
    created_at: datetime


class PasswordChangeRequest(BaseModel):
    """Payload used to update a user's password."""

    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class LoginRecordResponse(BaseModel):
    """Safe login audit data shown in the account settings page."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    login_at: datetime
    ip_address: str | None = None
    user_agent: str | None = None


class TokenResponse(BaseModel):
    """JWT access-token response."""

    access_token: str
    token_type: str = "bearer"
