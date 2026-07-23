"""Redis-backed fixed-window rate limiting for sensitive endpoints."""

import hashlib
import ipaddress
import logging

from fastapi import HTTPException, Request, status
from redis.asyncio import Redis, from_url
from redis.exceptions import RedisError

from app.config import settings

logger = logging.getLogger(__name__)

_RATE_LIMIT_SCRIPT = """
local current = tonumber(redis.call('get', KEYS[1]) or '0')
if current >= tonumber(ARGV[2]) then
  return {current, redis.call('ttl', KEYS[1]), 0}
end
current = redis.call('incr', KEYS[1])
if current == 1 then
  redis.call('expire', KEYS[1], ARGV[1])
end
return {current, redis.call('ttl', KEYS[1]), 1}
"""

_REFUND_RATE_LIMIT_SCRIPT = """
local current = tonumber(redis.call('get', KEYS[1]) or '0')
if current <= 1 then
  return redis.call('del', KEYS[1])
end
return redis.call('decr', KEYS[1])
"""


def client_ip(request: Request) -> str:
    """Use forwarding headers only when the direct peer is a trusted proxy."""

    peer = request.client.host if request.client else "unknown"
    try:
        peer_address = ipaddress.ip_address(peer)
        trusted = any(
            peer_address in ipaddress.ip_network(network.strip())
            for network in settings.trusted_proxy_networks.split(",")
            if network.strip()
        )
    except ValueError:
        trusted = False
    if trusted:
        forwarded = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
        try:
            return str(ipaddress.ip_address(forwarded))
        except ValueError:
            pass
    return peer


def _rate_limit_key(scope: str, identity: str) -> str:
    """Return a non-reversible Redis key for one limit scope and identity."""

    identity_hash = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:32]
    return f"rate:{scope}:{identity_hash}"


async def enforce_rate_limit(
    scope: str,
    identity: str,
    *,
    limit: int,
    window_seconds: int,
) -> None:
    """Reject requests exceeding a fixed Redis window."""

    key = _rate_limit_key(scope, identity)
    client: Redis | None = None
    try:
        client = from_url(settings.redis_url, decode_responses=True)
        count, ttl, accepted = await client.eval(
            _RATE_LIMIT_SCRIPT, 1, key, window_seconds, limit
        )
        count = int(count)
        ttl = int(ttl)
        if not int(accepted):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="请求过于频繁，请稍后再试",
                headers={"Retry-After": str(max(1, ttl))},
            )
    except HTTPException:
        raise
    except RedisError as error:
        logger.exception("Rate-limit storage is unavailable")
        if settings.app_env.casefold() in {"production", "prod"} and settings.rate_limit_fail_closed:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="安全服务暂时不可用，请稍后重试",
            ) from error
    finally:
        if client is not None:
            await client.aclose()


async def refund_rate_limit(scope: str, identity: str) -> None:
    """Return one consumed slot when an expensive request did not succeed."""

    client: Redis | None = None
    try:
        client = from_url(settings.redis_url, decode_responses=True)
        await client.eval(_REFUND_RATE_LIMIT_SCRIPT, 1, _rate_limit_key(scope, identity))
    except RedisError:
        # The fixed expiry remains a safe fallback; do not mask the original
        # request failure with a secondary Redis error.
        logger.exception("Unable to refund rate-limit slot for %s", scope)
    finally:
        if client is not None:
            await client.aclose()
