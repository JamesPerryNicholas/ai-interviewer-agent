"""Password hashing and JWT access-token helpers."""

from datetime import datetime, timedelta, timezone

import bcrypt
from jose import jwt

from app.config import settings


def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt before it is persisted."""

    password_bytes = password.encode("utf-8")
    return bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""

    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except (ValueError, TypeError):
        return False


def create_access_token(
    subject: str,
    expires_delta: timedelta | None = None,
    token_type: str = "user",
) -> str:
    """Create a signed JWT with an explicit user or admin token type."""

    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.jwt_expire_minutes)
    )
    payload = {"sub": subject, "exp": expire, "token_type": token_type}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
