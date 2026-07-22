"""Small asynchronous client for the DeepSeek Chat Completions API."""

import asyncio
import json
import time
from collections.abc import AsyncIterator, Sequence
from typing import Any

import httpx

from app.config import settings


class DeepSeekError(RuntimeError):
    """Base error for DeepSeek configuration and upstream failures."""


class DeepSeekConfigurationError(DeepSeekError):
    """Raised when the API key is not configured."""


class DeepSeekAPIError(DeepSeekError):
    """Raised when DeepSeek returns an error or an unusable response."""


class DeepSeekClient:
    """Async DeepSeek client using the OpenAI-compatible HTTP API."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else settings.deepseek_api_key
        self.base_url = (base_url or settings.deepseek_base_url).rstrip("/")
        self.timeout = timeout or settings.deepseek_timeout_seconds
        self.last_usage: dict[str, int | str] = {}

    async def chat_completion(
        self,
        messages: Sequence[dict[str, str]],
        model: str | None = None,
        response_format: dict[str, str] | None = None,
        json_mode: bool = True,
        allow_reasoning_json_fallback: bool = False,
        max_tokens: int = 4096,
        temperature: float | None = None,
    ) -> str:
        """Return the assistant message content for one non-streaming completion."""

        if not self.api_key:
            raise DeepSeekConfigurationError("DEEPSEEK_API_KEY is not configured")
        if not messages:
            raise ValueError("messages must contain at least one message")

        payload: dict[str, Any] = {
            "model": model or settings.deepseek_model,
            "messages": list(messages),
            "stream": False,
            "max_tokens": max_tokens,
        }
        if json_mode:
            payload["response_format"] = response_format or {"type": "json_object"}
        if response_format is not None:
            payload["response_format"] = response_format
        if temperature is not None:
            payload["temperature"] = temperature
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        started_at = time.perf_counter()

        try:
            async with httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout) as client:
                for attempt in range(3):
                    response = await client.post(
                        "/chat/completions", headers=headers, json=payload
                    )
                    if response.is_error:
                        # DeepSeek may temporarily return 429/5xx while the
                        # provider is busy. Retry transient upstream failures
                        # before exposing a 502 to the frontend.
                        if response.status_code in {429, 500, 502, 503, 504} and attempt < 2:
                            await asyncio.sleep(1.0 * (attempt + 1))
                            continue
                        raise DeepSeekAPIError(
                            f"DeepSeek API returned HTTP {response.status_code}"
                        )

                    try:
                        data = response.json()
                        usage = data.get("usage") or {}
                        self.last_usage = {
                            "model": data.get("model") or payload["model"],
                            "prompt_tokens": int(usage.get("prompt_tokens") or 0),
                            "completion_tokens": int(usage.get("completion_tokens") or 0),
                            "total_tokens": int(usage.get("total_tokens") or 0),
                            "latency_ms": round((time.perf_counter() - started_at) * 1000),
                        }
                        message = data["choices"][0]["message"]
                        content = message.get("content")
                    except (AttributeError, ValueError, KeyError, IndexError, TypeError) as error:
                        raise DeepSeekAPIError(
                            "DeepSeek returned an invalid completion response"
                        ) from error

                    if isinstance(content, str) and content.strip():
                        return content.strip()

                    if allow_reasoning_json_fallback:
                        fallback = self._extract_json_from_reasoning(
                            message.get("reasoning_content")
                        )
                        if fallback is not None:
                            return fallback

                    # DeepSeek reasoning models can occasionally return an empty
                    # final content field. Retry once before reporting an error.
                    if attempt < 2:
                        await asyncio.sleep(0.5)
                        continue
                    raise DeepSeekAPIError("DeepSeek returned empty completion content")
        except httpx.HTTPError as error:
            raise DeepSeekAPIError("Unable to reach DeepSeek API") from error

    @staticmethod
    def _extract_json_from_reasoning(reasoning: Any) -> str | None:
        """Recover a final JSON object when a reasoning model leaves content empty."""

        if not isinstance(reasoning, str):
            return None
        start = reasoning.rfind("{")
        end = reasoning.rfind("}")
        if start < 0 or end <= start:
            return None
        candidate = reasoning[start : end + 1].strip()
        try:
            json.loads(candidate)
        except json.JSONDecodeError:
            return None
        return candidate

    async def chat_completion_stream(
        self,
        messages: Sequence[dict[str, str]],
        model: str | None = None,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        """Yield assistant text chunks from DeepSeek's SSE response."""

        if not self.api_key:
            raise DeepSeekConfigurationError("DEEPSEEK_API_KEY is not configured")
        if not messages:
            raise ValueError("messages must contain at least one message")

        payload: dict[str, Any] = {
            "model": model or settings.deepseek_model,
            "messages": list(messages),
            "stream": True,
            "max_tokens": max_tokens,
            "stream_options": {"include_usage": True},
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }
        started_at = time.perf_counter()
        output_chunks: list[str] = []

        try:
            async with httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout) as client:
                async with client.stream(
                    "POST", "/chat/completions", headers=headers, json=payload
                ) as response:
                    if response.is_error:
                        raise DeepSeekAPIError(
                            f"DeepSeek API returned HTTP {response.status_code}"
                        )

                    async for line in response.aiter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                            usage = chunk.get("usage") or {}
                            if usage:
                                self.last_usage = {
                                    "model": chunk.get("model") or payload["model"],
                                    "prompt_tokens": int(usage.get("prompt_tokens") or 0),
                                    "completion_tokens": int(usage.get("completion_tokens") or 0),
                                    "total_tokens": int(usage.get("total_tokens") or 0),
                                }
                            choices = chunk.get("choices") or []
                            if not choices:
                                continue
                            content = choices[0].get("delta", {}).get("content", "")
                        except (ValueError, KeyError, IndexError, TypeError) as error:
                            raise DeepSeekAPIError(
                                "DeepSeek returned an invalid stream chunk"
                            ) from error
                        if content:
                            # Some compatible providers return several
                            # seconds of text in one SSE delta. Split large
                            # deltas so the browser always renders a visibly
                            # progressive response instead of one final block.
                            for offset in range(0, len(content), 2):
                                piece = content[offset : offset + 2]
                                output_chunks.append(piece)
                                yield piece
                                await asyncio.sleep(0.045)
                    if not self.last_usage:
                        completion_tokens = max(1, round(len("".join(output_chunks)) / 4))
                        self.last_usage = {
                            "model": payload["model"],
                            "prompt_tokens": 0,
                            "completion_tokens": completion_tokens,
                            "total_tokens": completion_tokens,
                        }
                    self.last_usage["latency_ms"] = round((time.perf_counter() - started_at) * 1000)
        except DeepSeekAPIError:
            raise
        except httpx.HTTPError as error:
            raise DeepSeekAPIError("Unable to reach DeepSeek API") from error


async def chat_completion(
    messages: Sequence[dict[str, str]],
    model: str | None = None,
) -> str:
    """Convenience wrapper for the default configured DeepSeek client."""

    return await DeepSeekClient().chat_completion(messages=messages, model=model)
