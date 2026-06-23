from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import redis.asyncio as aioredis

from app.core.settings import Settings

WORKER_HEALTH_KEY = "worker:health"
WORKER_HEARTBEAT_TTL = 120


def _redis_url(settings: Settings) -> str:
    return settings.queue_redis_url


async def update_worker_health(
    settings: Settings,
    processed_count: int,
    failed_count: int,
    consecutive_failures: int,
    is_paused: bool,
    is_running: bool,
) -> None:
    client = aioredis.from_url(_redis_url(settings))
    try:
        now = datetime.now(UTC).isoformat()
        payload = {
            "last_processed_at": now,
            "processed_count": processed_count,
            "failed_count": failed_count,
            "consecutive_failures": consecutive_failures,
            "is_paused": is_paused,
            "is_running": is_running,
        }
        await client.setex(WORKER_HEALTH_KEY, WORKER_HEARTBEAT_TTL, json.dumps(payload))
    finally:
        await client.aclose()


async def get_worker_health(settings: Settings) -> dict[str, Any]:
    client = aioredis.from_url(_redis_url(settings))
    try:
        raw = await client.get(WORKER_HEALTH_KEY)
        if raw is None:
            return {
                "status": "unhealthy",
                "reason": "no_heartbeat",
                "last_processed_at": None,
                "processed_count": 0,
                "failed_count": 0,
                "consecutive_failures": 0,
                "is_paused": False,
                "is_running": False,
            }
        payload: dict[str, Any] = json.loads(raw)
        last_processed_str = payload.get("last_processed_at")
        last_processed: datetime | None = None
        if last_processed_str:
            last_processed = datetime.fromisoformat(last_processed_str)

        now = datetime.now(UTC)
        if last_processed and (now - last_processed) > timedelta(seconds=60):
            payload["status"] = "unhealthy"
            payload["reason"] = "stale_heartbeat"
        else:
            payload["status"] = "healthy"
            payload["reason"] = ""

        payload["last_processed_at"] = last_processed_str
        return payload
    finally:
        await client.aclose()
