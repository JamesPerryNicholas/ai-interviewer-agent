"""Production secret validation tests."""

import pytest
from pydantic import ValidationError

from app.config import Settings


def test_production_rejects_default_secrets():
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            app_env="production",
            jwt_secret_key="change-this-development-secret-key",
            admin_password="admin@123",
            database_url="postgresql+asyncpg://postgres:weak@localhost/test",
            redis_url="redis://:weak@localhost/0",
        )


def test_production_accepts_strong_secrets():
    settings = Settings(
        _env_file=None,
        app_env="production",
        jwt_secret_key="a-strong-random-jwt-secret-value-1234567890",
        admin_password="A-strong-admin-password-2026!",
        database_url="postgresql+asyncpg://app:StrongDbPassword@localhost/test",
        redis_url="redis://:StrongRedisPassword@localhost/0",
    )
    assert settings.app_env == "production"
