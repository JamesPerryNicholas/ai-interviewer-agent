"""Ownership-safe Redis lock used around costly state transitions."""

import logging
from uuid import uuid4

from redis.asyncio import Redis, from_url

from app.config import settings

logger = logging.getLogger(__name__)

_RELEASE_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
  return redis.call('del', KEYS[1])
end
return 0
"""


class LockBusyError(RuntimeError):
    """Raised when another request already owns the operation lock."""


async def acquire_lock(key: str, ttl_seconds: int | None = None) -> tuple[Redis, str]:
    """Acquire a lock and return the live Redis client plus ownership token."""

    client = from_url(settings.redis_url, decode_responses=True)
    token = uuid4().hex
    acquired = await client.set(
        f"lock:{key}",
        token,
        nx=True,
        ex=ttl_seconds or settings.distributed_lock_ttl_seconds,
    )
    if not acquired:
        await client.aclose()
        raise LockBusyError("该操作正在处理中，请勿重复提交")
    return client, token


async def release_lock(client: Redis, key: str, token: str) -> None:
    """Release a lock only when the caller still owns it."""

    try:
        try:
            await client.eval(_RELEASE_SCRIPT, 1, f"lock:{key}", token)
        except Exception:
            # The TTL still guarantees eventual release. Never turn a
            # successfully committed business operation into an HTTP 500.
            logger.exception("Unable to release distributed lock %s", key)
    finally:
        await client.aclose()
