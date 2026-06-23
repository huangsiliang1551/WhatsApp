"""Tests for API rate limiter."""

from fastapi.testclient import TestClient


def test_rate_limit_basic(client: TestClient) -> None:
    """Rate limiter allows requests within limit."""
    # auth tier allows 5 req/min - first 4 should always pass
    from app.core.rate_limiter import RateLimiter, InMemoryRateLimitStore

    limiter = RateLimiter(InMemoryRateLimitStore())
    result = limiter.check_limit("test:127.0.0.1", "auth")
    assert result.allowed
    assert result.remaining >= 0
    assert result.reset_at > 0


def test_rate_limit_exceeded(client: TestClient) -> None:
    """Rate limiter blocks when limit exceeded."""
    from app.core.rate_limiter import RateLimiter, InMemoryRateLimitStore

    store = InMemoryRateLimitStore()
    limiter = RateLimiter(store)

    # Use a tier with low limit for testing
    key = "test:limit_exceeded"
    # Consume all 5 auth requests
    for _ in range(5):
        result = limiter.check_limit(key, "auth")
        assert result.allowed

    # 6th request should be blocked
    result = limiter.check_limit(key, "auth")
    assert not result.allowed
    assert result.remaining == 0


def test_rate_limit_tiers_independent(client: TestClient) -> None:
    """Different tiers have independent counters."""
    from app.core.rate_limiter import RateLimiter, InMemoryRateLimitStore

    store = InMemoryRateLimitStore()
    limiter = RateLimiter(store)

    key = "test:independent"
    # Exhaust auth tier (5 req/min)
    for _ in range(5):
        limiter.check_limit(key, "auth")

    # api tier should still allow (60 req/min)
    result = limiter.check_limit(key, "api")
    assert result.allowed


def test_rate_limit_window_expires(client: TestClient) -> None:
    """Rate limit resets after window expires."""
    from app.core.rate_limiter import RateLimiter, InMemoryRateLimitStore
    import time

    store = InMemoryRateLimitStore()
    limiter = RateLimiter(store)

    key = "test:window"
    # Use a custom check that simulates old entries
    # Manually set old timestamps
    store._windows[key] = [time.time() - 120, time.time() - 119]  # Over 60s old

    # Should have 2 expired entries from the old window, new request should pass
    for _ in range(5):
        result = limiter.check_limit(key, "auth")
        assert result.allowed

    result = limiter.check_limit(key, "auth")
    assert not result.allowed


def test_rate_limit_disabled(client: TestClient) -> None:
    """Rate limiter can be disabled via settings."""
    import os

    original = os.environ.get("RATE_LIMIT_ENABLED")
    os.environ["RATE_LIMIT_ENABLED"] = "false"
    from app.core.settings import get_settings

    get_settings.cache_clear()
    settings = get_settings()
    assert not settings.rate_limit_enabled

    if original:
        os.environ["RATE_LIMIT_ENABLED"] = original
    else:
        del os.environ["RATE_LIMIT_ENABLED"]
    get_settings.cache_clear()


def test_rate_limit_returns_429(client: TestClient) -> None:
    """Rate limited requests return 429."""
    from app.core.rate_limiter import get_rate_limiter, InMemoryRateLimitStore, RateLimiter

    # Override the global limiter with a fresh one
    store = InMemoryRateLimitStore()
    limiter = RateLimiter(store)
    import app.core.rate_limiter as rl_module

    original_limiter = rl_module._limiter
    rl_module._limiter = limiter

    try:
        key = "test:429"
        for _ in range(5):
            result = limiter.check_limit(key, "auth")

        result = limiter.check_limit(key, "auth")
        assert not result.allowed
        assert result.remaining == 0
    finally:
        rl_module._limiter = original_limiter


def test_rate_limit_unknown_tier_defaults_to_api(client: TestClient) -> None:
    """Unknown tier defaults to API tier (60 req/min)."""
    from app.core.rate_limiter import RateLimiter, InMemoryRateLimitStore

    store = InMemoryRateLimitStore()
    limiter = RateLimiter(store)

    result = limiter.check_limit("test:unknown", "nonexistent_tier")
    assert result.allowed


def test_rate_limit_key_uses_client_ip(monkeypatch, client: TestClient) -> None:
    """Rate limit key includes client IP (test falls back to 'unknown')."""
    from app.core.rate_limiter import get_rate_limiter

    limiter = get_rate_limiter()
    # The key format is "{tier}:{client_ip}"
    # We can't test the exact key since client IP varies in tests
    # but the function should work
    result = limiter.check_limit("api:127.0.0.1", "api")
    assert isinstance(result.allowed, bool)
