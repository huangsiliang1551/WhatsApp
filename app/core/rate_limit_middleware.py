"""Rate Limit Middleware — IV-BE-007.

Enforces per-agency + per-endpoint rate limits using Redis.
Supports IP banning when limits are exceeded.
"""

from __future__ import annotations

import os
import time

import redis as sync_redis
from fastapi import HTTPException
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.settings import get_settings

REDIS_SOCKET_TIMEOUT_SECONDS = 2
REDIS_CONNECT_TIMEOUT_SECONDS = 0.2


def _resolve_request_scope_id(request: Request, *, jwt_secret: str) -> str:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        from app.api.routes.agent_auth import _decode_agent_jwt

        payload = _decode_agent_jwt(auth_header[7:], jwt_secret)
        if payload is not None:
            agency_id = payload.get("agency_id")
            if agency_id not in (None, ""):
                return str(agency_id)
            subject = payload.get("sub")
            if subject not in (None, ""):
                return str(subject)
    return request.headers.get("X-Actor-Id", "global")


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware that enforces API rate limits using Redis."""

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        path = request.url.path
        if not path.startswith("/api/") or path in (
            "/api/health", "/api/metrics", "/api/rate-limits/banned-ips",
        ):
            return await call_next(request)

        settings = get_settings()
        if settings.test_mode or "PYTEST_CURRENT_TEST" in os.environ:
            return await call_next(request)
        if not settings.rate_limit_enabled:
            return await call_next(request)

        ip = request.client.host if request.client else "unknown"
        agency_id = _resolve_request_scope_id(
            request,
            jwt_secret=settings.admin_jwt_secret,
        )
        endpoint = path

        try:
            client = sync_redis.from_url(
                settings.redis_url,
                socket_timeout=REDIS_SOCKET_TIMEOUT_SECONDS,
                socket_connect_timeout=REDIS_CONNECT_TIMEOUT_SECONDS,
            )

            # 1. Check if IP is banned
            banned_key = f"banned:{ip}"
            if client.exists(banned_key):
                ttl = client.ttl(banned_key)
                raise HTTPException(
                    status_code=429,
                    detail=f"IP 已被封禁，剩余 {max(ttl, 0)} 秒",
                )

            # 2. Load matching rate rules from DB
            from app.db.session import get_sessionmaker

            session_factory = get_sessionmaker()
            with session_factory() as session:
                from app.db.models import ApiRateLimit
                from sqlalchemy import select

                stmt = select(ApiRateLimit).where(
                    ApiRateLimit.is_enabled.is_(True),
                )
                rules = list(session.scalars(stmt).all())

            # 3. Check each applicable rule
            for rule in rules:
                if not self._endpoint_matches(endpoint, rule.endpoint_pattern):
                    continue
                if rule.agency_id and rule.agency_id != agency_id:
                    continue

                window_key = (
                    f"rate:{agency_id}:{rule.endpoint_pattern}:"
                    f"{int(time.time() / rule.window_seconds)}"
                )
                count = client.incr(window_key)
                if count == 1:
                    client.expire(window_key, rule.window_seconds)

                if count > rule.max_requests:
                    # Ban the IP
                    ban_seconds = rule.ban_minutes * 60
                    client.setex(banned_key, ban_seconds, "1")
                    client.close()
                    raise HTTPException(
                        status_code=429,
                        detail=f"请求过于频繁，IP 已封禁 {rule.ban_minutes} 分钟",
                    )

            client.close()
        except HTTPException:
            raise
        except Exception:
            # Rate limit errors must never break the request
            pass

        return await call_next(request)

    def _endpoint_matches(self, actual: str, pattern: str) -> bool:
        """Check if an endpoint matches a pattern (supports * wildcard)."""
        if pattern.endswith("/*"):
            prefix = pattern[:-2]
            return actual.startswith(prefix)
        return actual == pattern
