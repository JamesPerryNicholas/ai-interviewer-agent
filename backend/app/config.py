"""Application configuration loaded from environment variables and .env."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime settings for the backend service."""

    app_name: str = "AI Interview Agent Backend"
    debug: bool = False
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/ai_interviewer"
    redis_url: str = "redis://localhost:6379/0"
    # Development fallback only. Always override these values in deployment secrets.
    jwt_secret_key: str = "change-this-development-secret-key"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60
    storage_dir: str = str(PROJECT_ROOT / "storage")
    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-chat"
    deepseek_base_url: str = "https://api.deepseek.com"
    # LLM requests are intentionally longer than normal API requests.
    deepseek_timeout_seconds: float = 120.0
    # Eight concise question objects do not need the default 4096-token budget.
    deepseek_question_max_tokens: int = 1800
    # The report contains eight short answer evaluations and summary lists.
    deepseek_evaluation_max_tokens: int = 2600
    admin_username: str = "admin"
    admin_password: str = "admin@123"
    admin_budget_tokens: int | None = None

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        env_ignore_empty=True,
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached settings instance for dependency injection and imports."""

    return Settings()


settings = get_settings()
