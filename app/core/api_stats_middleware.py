"""API Stats Middleware — IV-BE-006.

Records request count and total latency to Redis for every API request.
Key format:
  api_stats:{agency_id}:{endpoint}:{date}:count
  api_stats:{agency_id}:{endpoint}:{date}:total_ms
"""

from __future__ import annotations

import os
import time
from datetime import datetime

import redis as sync_redis
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


class ApiStatsMiddleware(BaseHTTPMiddleware):
    """Middleware that records API request stats to Redis."""

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        start = time.monotonic()
        response = await call_next(request)
        elapsed = time.monotonic() - start

        # Only track API routes
        path = request.url.path
        if not path.startswith("/api/"):
            return response

        # Skip stats endpoints themselves to avoid inflation
        if path.startswith("/api/api-stats/"):
            return response

        settings = get_settings()
        if settings.test_mode or "PYTEST_CURRENT_TEST" in os.environ:
            return response

        try:
            client = sync_redis.from_url(
                settings.redis_url,
                socket_timeout=REDIS_SOCKET_TIMEOUT_SECONDS,
                socket_connect_timeout=REDIS_CONNECT_TIMEOUT_SECONDS,
            )

            agency_id = _resolve_request_scope_id(
                request,
                jwt_secret=settings.admin_jwt_secret,
            )
            date = datetime.now().strftime("%Y-%m-%d")
            endpoint = path

            count_key = f"api_stats:{agency_id}:{endpoint}:{date}:count"
            ms_key = f"api_stats:{agency_id}:{endpoint}:{date}:total_ms"

            client.incr(count_key)
            client.incrby(ms_key, int(elapsed * 1000))
            client.close()
        except Exception:
            # Stats recording must never break the request
            pass

        return response
