"""Helpers for persisting provider usage without exposing API credentials."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.llm.deepseek import DeepSeekClient
from app.models.llm_usage import LLMUsage


def add_llm_usage(
    session: AsyncSession,
    *,
    client: DeepSeekClient,
    user_id: int | None,
    feature: str,
) -> None:
    """Add the last DeepSeek call usage to the current transaction."""

    usage = client.last_usage
    session.add(
        LLMUsage(
            user_id=user_id,
            feature=feature,
            model=usage.get("model") or settings.deepseek_model,
            prompt_tokens=int(usage.get("prompt_tokens") or 0),
            completion_tokens=int(usage.get("completion_tokens") or 0),
            total_tokens=int(usage.get("total_tokens") or 0),
            latency_ms=int(usage.get("latency_ms") or 0),
        )
    )
