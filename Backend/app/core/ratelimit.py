"""Fixed-window rate limits in Redis. Fails open: a Redis outage never takes the app down."""

import logging
import time
from collections.abc import Callable
from functools import lru_cache
from typing import Annotated, Protocol

import redis.asyncio as redis
from fastapi import Depends

from app.core.config import get_settings
from app.core.errors import AppError

log = logging.getLogger(__name__)

KEY_PREFIX = "rl"


class Counter(Protocol):
    """The two Redis commands we need (lets tests use an in-memory fake)."""

    async def incr(self, name: str) -> int: ...
    async def expire(self, name: str, time: int) -> bool: ...


@lru_cache
def get_redis() -> redis.Redis:
    return redis.Redis.from_url(
        get_settings().redis_url, socket_timeout=1, socket_connect_timeout=1
    )


async def hit(
    r: Counter, key: str, limit: int, window_s: int = 60, clock: Callable[[], float] = time.time
) -> bool:
    """Count one request; True if still within `limit` for the current window."""
    window = int(clock() // window_s)
    full_key = f"{KEY_PREFIX}:{key}:{window}"
    try:
        count = await r.incr(full_key)
        if count == 1:
            await r.expire(full_key, window_s)
    except Exception as exc:
        log.warning("Rate limiter unavailable (%s); allowing request", exc)
        return True
    return count <= limit


class RateLimiter:
    def __init__(self, r: Counter, clock: Callable[[], float] = time.time) -> None:
        self.r = r
        self.clock = clock  # injectable so tests don't depend on minute boundaries

    async def check(self, key: str, limit: int, window_s: int = 60) -> None:
        if not await hit(self.r, key, limit, window_s, self.clock):
            raise AppError(
                "rate_limited",
                "Too many requests. Please wait a minute and try again.",
                429,
                {"Retry-After": str(window_s)},
            )

    async def login(self, ip: str, email: str) -> None:
        await self.check(f"login:{ip}:{email.lower()}", get_settings().login_per_min)

    async def ai(self, user_id: object, org_id: object) -> None:
        """Per user and per org: Mistral quotas are per account, so one org can't starve others."""
        s = get_settings()
        await self.check(f"ai:user:{user_id}", s.ai_per_min)
        await self.check(f"ai:org:{org_id}", s.ai_org_per_min)


def get_rate_limiter() -> RateLimiter:
    return RateLimiter(get_redis())


Limiter = Annotated[RateLimiter, Depends(get_rate_limiter)]
