from __future__ import annotations

import asyncio
from types import SimpleNamespace

from starlette.requests import Request
from starlette.responses import Response

from app.core.api_stats_middleware import ApiStatsMiddleware
from app.core.rate_limit_middleware import RateLimitMiddleware


def _build_request(path: str = "/api/test") -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": path,
            "headers": [],
            "query_string": b"",
            "client": ("127.0.0.1", 12345),
            "server": ("testserver", 80),
            "scheme": "http",
            "root_path": "",
            "http_version": "1.1",
        }
    )


async def _call_next(_request: Request) -> Response:
    return Response("ok", status_code=200)


def test_api_stats_middleware_skips_redis_in_test_mode(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.core.api_stats_middleware.get_settings",
        lambda: SimpleNamespace(
            test_mode=True,
            redis_url="redis://localhost:6379/0",
            admin_jwt_secret="test-secret",
        ),
    )
    calls = {"count": 0}

    def _unexpected_redis(*args, **kwargs):
        calls["count"] += 1
        raise RuntimeError("Redis should be skipped in test mode.")

    monkeypatch.setattr(
        "app.core.api_stats_middleware.sync_redis.from_url",
        _unexpected_redis,
    )

    middleware = ApiStatsMiddleware(app=lambda scope, receive, send: None)
    response = asyncio.run(middleware.dispatch(_build_request(), _call_next))

    assert response.status_code == 200
    assert calls["count"] == 0


def test_api_stats_middleware_skips_redis_in_pytest_context(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.core.api_stats_middleware.get_settings",
        lambda: SimpleNamespace(
            test_mode=False,
            redis_url="redis://localhost:6379/0",
            admin_jwt_secret="test-secret",
        ),
    )
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "tests/test_api_middlewares.py::api_stats")
    calls = {"count": 0}

    def _unexpected_redis(*args, **kwargs):
        calls["count"] += 1
        raise RuntimeError("Redis should be skipped in pytest context.")

    monkeypatch.setattr(
        "app.core.api_stats_middleware.sync_redis.from_url",
        _unexpected_redis,
    )

    middleware = ApiStatsMiddleware(app=lambda scope, receive, send: None)
    response = asyncio.run(middleware.dispatch(_build_request(), _call_next))

    assert response.status_code == 200
    assert calls["count"] == 0


def test_api_stats_middleware_uses_fast_redis_connect_timeout(monkeypatch) -> None:
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setattr(
        "app.core.api_stats_middleware.get_settings",
        lambda: SimpleNamespace(
            test_mode=False,
            redis_url="redis://localhost:6379/0",
            admin_jwt_secret="test-secret",
        ),
    )
    captured: dict[str, object] = {}

    def _record_redis(url: str, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        raise RuntimeError("skip redis")

    monkeypatch.setattr(
        "app.core.api_stats_middleware.sync_redis.from_url",
        _record_redis,
    )

    middleware = ApiStatsMiddleware(app=lambda scope, receive, send: None)
    response = asyncio.run(middleware.dispatch(_build_request(), _call_next))

    assert response.status_code == 200
    assert captured["url"] == "redis://localhost:6379/0"
    assert captured["socket_timeout"] == 2
    assert captured["socket_connect_timeout"] == 0.2


def test_rate_limit_middleware_skips_redis_in_test_mode(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.core.rate_limit_middleware.get_settings",
        lambda: SimpleNamespace(
            test_mode=True,
            rate_limit_enabled=True,
            redis_url="redis://localhost:6379/0",
            admin_jwt_secret="test-secret",
        ),
    )
    calls = {"count": 0}

    def _unexpected_redis(*args, **kwargs):
        calls["count"] += 1
        raise RuntimeError("Redis should be skipped in test mode.")

    monkeypatch.setattr(
        "app.core.rate_limit_middleware.sync_redis.from_url",
        _unexpected_redis,
    )

    middleware = RateLimitMiddleware(app=lambda scope, receive, send: None)
    response = asyncio.run(middleware.dispatch(_build_request(), _call_next))

    assert response.status_code == 200
    assert calls["count"] == 0


def test_rate_limit_middleware_skips_redis_in_pytest_context(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.core.rate_limit_middleware.get_settings",
        lambda: SimpleNamespace(
            test_mode=False,
            rate_limit_enabled=True,
            redis_url="redis://localhost:6379/0",
            admin_jwt_secret="test-secret",
        ),
    )
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "tests/test_api_middlewares.py::rate_limit")
    calls = {"count": 0}

    def _unexpected_redis(*args, **kwargs):
        calls["count"] += 1
        raise RuntimeError("Redis should be skipped in pytest context.")

    monkeypatch.setattr(
        "app.core.rate_limit_middleware.sync_redis.from_url",
        _unexpected_redis,
    )

    middleware = RateLimitMiddleware(app=lambda scope, receive, send: None)
    response = asyncio.run(middleware.dispatch(_build_request(), _call_next))

    assert response.status_code == 200
    assert calls["count"] == 0


def test_rate_limit_middleware_uses_fast_redis_connect_timeout(monkeypatch) -> None:
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setattr(
        "app.core.rate_limit_middleware.get_settings",
        lambda: SimpleNamespace(
            test_mode=False,
            rate_limit_enabled=True,
            redis_url="redis://localhost:6379/0",
            admin_jwt_secret="test-secret",
        ),
    )
    captured: dict[str, object] = {}

    def _record_redis(url: str, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        raise RuntimeError("skip redis")

    monkeypatch.setattr(
        "app.core.rate_limit_middleware.sync_redis.from_url",
        _record_redis,
    )

    middleware = RateLimitMiddleware(app=lambda scope, receive, send: None)
    response = asyncio.run(middleware.dispatch(_build_request(), _call_next))

    assert response.status_code == 200
    assert captured["url"] == "redis://localhost:6379/0"
    assert captured["socket_timeout"] == 2
    assert captured["socket_connect_timeout"] == 0.2
