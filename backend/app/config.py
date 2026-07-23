"""Application configuration loaded from environment variables and .env."""

from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime settings for the backend service."""

    app_env: str = "development"
    app_name: str = "AI Interview Agent Backend"
    debug: bool = False
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/ai_interviewer"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = Field(default=60, ge=5, le=1440)
    jwt_issuer: str = "ai-interviewer-agent"
    jwt_audience: str = "ai-interviewer-web"
    storage_dir: str = str(PROJECT_ROOT / "storage")
    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-chat"
    deepseek_base_url: str = "https://api.deepseek.com"
    # LLM requests are intentionally longer than normal API requests.
    deepseek_timeout_seconds: float = Field(default=120.0, ge=5, le=600)
    # Eight concise question objects do not need the default 4096-token budget.
    deepseek_question_max_tokens: int = Field(default=1800, ge=256, le=8192)
    # The report contains eight short answer evaluations and summary lists.
    deepseek_evaluation_max_tokens: int = Field(default=2600, ge=256, le=8192)
    admin_username: str = "admin"
    admin_password: str = ""
    admin_budget_tokens: int | None = None
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    trusted_proxy_networks: str = "127.0.0.1/32,::1/128,172.16.0.0/12"
    max_resume_upload_bytes: int = Field(default=10 * 1024 * 1024, ge=1024, le=25 * 1024 * 1024)
    max_pdf_pages: int = Field(default=50, ge=1, le=200)
    max_resume_text_chars: int = Field(default=80_000, ge=1000, le=200_000)
    max_job_description_chars: int = Field(default=20_000, ge=1000, le=50_000)
    max_avatar_upload_bytes: int = Field(default=5 * 1024 * 1024, ge=1024, le=10 * 1024 * 1024)
    rate_limit_fail_closed: bool = True
    distributed_lock_ttl_seconds: int = Field(default=600, ge=60, le=1800)

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        env_ignore_empty=True,
    )

    @property
    def parsed_cors_origins(self) -> list[str]:
        """Return normalized, explicitly configured browser origins."""

        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        """Refuse known development credentials in production mode."""

        if self.app_env.casefold() not in {"production", "prod"}:
            return self

        weak_jwt_secrets = {
            "change-this-development-secret-key",
            "secret",
            "changeme",
        }
        if len(self.jwt_secret_key) < 32 or self.jwt_secret_key.casefold() in weak_jwt_secrets:
            raise ValueError("JWT_SECRET_KEY must be a random value of at least 32 characters")
        weak_admin_passwords = {"admin", "admin123", "admin@123", "password", "changeme"}
        if len(self.admin_password) < 12 or self.admin_password.casefold() in weak_admin_passwords:
            raise ValueError("ADMIN_PASSWORD must be a strong value of at least 12 characters")
        database = urlparse(self.database_url)
        if not database.password or database.password.casefold() in {"postgres", "password"}:
            raise ValueError("DATABASE_URL must contain a non-default database password")
        redis = urlparse(self.redis_url)
        if not redis.password:
            raise ValueError("REDIS_URL must contain a Redis password")
        return self


@lru_cache
def get_settings() -> Settings:
    """Return a cached settings instance for dependency injection and imports."""

    return Settings()


settings = get_settings()
