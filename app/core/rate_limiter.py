"""Rate limiter using Redis sliding window for API rate limiting."""

import time
from typing import Protocol

import structlog
from redis import Redis

from app.core.settings import get_settings

logger = structlog.get_logger()

# Tier definitions: (max_requests, window_seconds)
RATE_LIMIT_TIERS: dict[str, tuple[int, int]] = {
    "auth": (5, 60),       # 5 req/min (login)
    "webhook": (100, 60),  # 100 req/min (Meta callbacks)
    "api": (60, 60),       # 60 req/min (Admin API)
    "h5_auth": (10, 60),   # 10 req/min (H5 login)
    "h5_api": (30, 60),    # 30 req/min (H5 business API)
    "mock": (30, 60),      # 30 req/min (Dev mock)
}


class RateLimitResult:
    """Result of a rate limit check."""

    def __init__(self, allowed: bool, remaining: int, reset_at: float) -> None:
        self.allowed = allowed
        self.remaining = remaining
        self.reset_at = reset_at


class RateLimitStore(Protocol):
    """Abstract rate limit store."""

    def increment_and_check(self, key: str, max_requests: int, window_seconds: int) -> RateLimitResult:
        ...


class InMemoryRateLimitStore:
    """In-memory sliding window rate limit store for development/testing."""

    def __init__(self) -> None:
        self._windows: dict[str, list[float]] = {}

    def increment_and_check(self, key: str, max_requests: int, window_seconds: int) -> RateLimitResult:
        now = time.time()
        window_start = now - window_seconds

        timestamps = self._windows.get(key, [])
        # Remove expired entries
        timestamps = [ts for ts in timestamps if ts > window_start]
        self._windows[key] = timestamps

        current_count = len(timestamps)
        if current_count >= max_requests:
            reset_at = timestamps[0] + window_seconds if timestamps else now + window_seconds
            return RateLimitResult(allowed=False, remaining=0, reset_at=reset_at)

        timestamps.append(now)
        self._windows[key] = timestamps
        reset_at = now + window_seconds
        return RateLimitResult(allowed=True, remaining=max_requests - current_count - 1, reset_at=reset_at)


class RedisRateLimitStore:
    """Redis-based sliding window rate limit store with fallback to in-memory."""

    def __init__(self, redis_url: str) -> None:
        self._redis_url = redis_url
        self._client: Redis | None = None
        self._fallback: InMemoryRateLimitStore = InMemoryRateLimitStore()
        self._available = False
        try:
            self._client = Redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=2)
            self._client.ping()
            self._available = True
        except Exception:
            logger.warning("redis_rate_limit_unavailable_using_fallback")

    def increment_and_check(self, key: str, max_requests: int, window_seconds: int) -> RateLimitResult:
        if not self._available or self._client is None:
            return self._fallback.increment_and_check(key, max_requests, window_seconds)

        try:
            redis_key = f"ratelimit:{key}:{window_seconds}"
            now = time.time()
            window_start = now - window_seconds
            pipe = self._client.pipeline()
            pipe.zremrangebyscore(redis_key, "-inf", window_start)
            pipe.zcard(redis_key)
            pipe.zadd(redis_key, {str(now): now})
            pipe.expire(redis_key, window_seconds * 2)
            results = pipe.execute()
            current_count = int(results[1])
            if current_count >= max_requests:
                return RateLimitResult(allowed=False, remaining=0, reset_at=now + window_seconds)
            return RateLimitResult(
                allowed=True,
                remaining=max_requests - current_count - 1,
                reset_at=now + window_seconds,
            )
        except Exception as exc:
            logger.warning("redis_rate_limit_fallback_due_to_error", error=str(exc))
            self._available = False
            return self._fallback.increment_and_check(key, max_requests, window_seconds)


class RateLimiter:
    """Rate limiter that checks and enforces API rate limits."""

    def __init__(self, store: RateLimitStore | None = None) -> None:
        self._store = store or InMemoryRateLimitStore()

    def check_limit(self, key: str, tier: str) -> RateLimitResult:
        """Check if a request key is within rate limits for the given tier."""
        if tier not in RATE_LIMIT_TIERS:
            tier = "api"  # Default to API tier

        max_requests, window_seconds = RATE_LIMIT_TIERS[tier]
        return self._store.increment_and_check(key, max_requests, window_seconds)

    def get_remaining(self, key: str, tier: str) -> int:
        """Get remaining requests for a key and tier."""
        result = self.check_limit(key, tier)
        return result.remaining

    def reset(self) -> None:
        """Reset all rate limit counters (for testing)."""
        if isinstance(self._store, InMemoryRateLimitStore):
            self._store._windows.clear()


# Global singleton
_limiter: RateLimiter | None = None


def _build_rate_limit_store() -> RateLimitStore:
    """Build a rate limit store, preferring Redis when available."""
    settings = get_settings()
    if settings.test_mode:
        return InMemoryRateLimitStore()
    try:
        return RedisRateLimitStore(settings.redis_url)
    except Exception:
        logger.warning("redis_rate_limit_store_creation_failed")
        return InMemoryRateLimitStore()


def get_rate_limiter() -> RateLimiter:
    global _limiter
    if _limiter is None:
        store = _build_rate_limit_store()
        _limiter = RateLimiter(store)
    return _limiter


def reset_rate_limiter() -> None:
    """Reset the global rate limiter singleton (for testing)."""
    global _limiter
    if _limiter is not None:
        _limiter.reset()


def rate_limit(tier: str):
    """FastAPI dependency factory for rate limiting.

    Usage:
        @router.post("/login")
        async def login(_: None = Depends(rate_limit("auth"))):
            ...
    """
    from collections.abc import Callable

    from fastapi import HTTPException, Request, status

    def dependency(request: Request) -> None:
        settings = get_settings()
        if not settings.rate_limit_enabled:
            return

        limiter = get_rate_limiter()
        # Use client IP or token as the rate limit key
        client_ip = request.client.host if request.client else "unknown"
        key = f"{tier}:{client_ip}"

        result = limiter.check_limit(key, tier)
        if not result.allowed:
            retry_after = int(max(1, result.reset_at - time.time()))
            logger.warning(
                "rate_limit_exceeded",
                tier=tier,
                key=key,
                retry_after=retry_after,
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Retry after {retry_after} seconds.",
                headers={"Retry-After": str(retry_after)},
            )

    return dependency
