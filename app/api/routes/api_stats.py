"""API Stats API — IV-BE-006.

Endpoints:
  GET /api/api-stats/summary         — overall summary
  GET /api/api-stats/by-agency/{id}  — per-agency stats
  GET /api/api-stats/by-endpoint     — per-endpoint stats
  GET /api/api-stats/timeline        — daily timeline (default 7 days)
"""

from __future__ import annotations

from datetime import datetime, timedelta

import redis as sync_redis
from fastapi import APIRouter, Depends, Query

from app.api.deps import get_db_session, require_permission
from app.core.auth import RequestActor
from app.core.settings import Settings, get_settings

router = APIRouter(prefix="/api/api-stats", tags=["api-stats"])


def _get_redis(settings: Settings):
    return sync_redis.from_url(settings.redis_url, socket_timeout=3)


@router.get("/summary", summary="API 统计汇总")
def get_summary(
    settings: Settings = Depends(get_settings),
    _actor: RequestActor = Depends(require_permission("api_stats.view")),
):
    client = _get_redis(settings)
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        # Scan all keys for today
        pattern = f"api_stats:*:*:{today}:count"
        keys = client.keys(pattern)
        total_count = 0
        total_ms = 0
        agencies = set()

        for key in keys:
            parts = key.decode() if isinstance(key, bytes) else key
            parts = parts.split(":")
            agency = parts[1]
            agencies.add(agency)
            count = int(client.get(key) or 0)
            total_count += count

            ms_key = key.replace(b":count" if isinstance(key, bytes) else ":count",
                                 b":total_ms" if isinstance(key, bytes) else ":total_ms")
            ms_val = int(client.get(ms_key) or 0)
            total_ms += ms_val

        return {
            "today_count": total_count,
            "avg_ms": round(total_ms / total_count, 2) if total_count else 0,
            "active_agencies": len(agencies),
            "date": today,
        }
    finally:
        client.close()


@router.get("/by-agency/{agency_id}", summary="按代理商统计")
def get_by_agency(
    agency_id: str,
    settings: Settings = Depends(get_settings),
    _actor: RequestActor = Depends(require_permission("api_stats.view")),
):
    client = _get_redis(settings)
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        pattern = f"api_stats:{agency_id}:*:{today}:count"
        keys = client.keys(pattern)
        total_count = 0
        total_ms = 0
        endpoints = []

        for key in keys:
            parts = key.decode() if isinstance(key, bytes) else key
            parts = parts.split(":")
            endpoint = parts[2]
            count = int(client.get(key) or 0)
            total_count += count

            ms_key = key.replace(b":count" if isinstance(key, bytes) else ":count",
                                 b":total_ms" if isinstance(key, bytes) else ":total_ms")
            ms_val = int(client.get(ms_key) or 0)
            total_ms += ms_val

            endpoints.append({
                "endpoint": endpoint,
                "count": count,
                "avg_ms": round(ms_val / count, 2) if count else 0,
            })

        return {
            "agency_id": agency_id,
            "total_count": total_count,
            "avg_ms": round(total_ms / total_count, 2) if total_count else 0,
            "endpoints": endpoints,
        }
    finally:
        client.close()


@router.get("/by-endpoint", summary="按端点统计")
def get_by_endpoint(
    settings: Settings = Depends(get_settings),
    _actor: RequestActor = Depends(require_permission("api_stats.view")),
):
    client = _get_redis(settings)
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        pattern = f"api_stats:*:*:{today}:count"
        keys = client.keys(pattern)
        endpoint_map: dict[str, dict] = {}

        for key in keys:
            parts = key.decode() if isinstance(key, bytes) else key
            parts = parts.split(":")
            endpoint = parts[2]
            count = int(client.get(key) or 0)

            ms_key = key.replace(b":count" if isinstance(key, bytes) else ":count",
                                 b":total_ms" if isinstance(key, bytes) else ":total_ms")
            ms_val = int(client.get(ms_key) or 0)

            if endpoint not in endpoint_map:
                endpoint_map[endpoint] = {"count": 0, "total_ms": 0}
            endpoint_map[endpoint]["count"] += count
            endpoint_map[endpoint]["total_ms"] += ms_val

        return [
            {
                "endpoint": ep,
                "count": data["count"],
                "avg_ms": round(data["total_ms"] / data["count"], 2) if data["count"] else 0,
            }
            for ep, data in sorted(endpoint_map.items(), key=lambda x: x[1]["count"], reverse=True)
        ]
    finally:
        client.close()


@router.get("/timeline", summary="时间线统计")
def get_timeline(
    days: int = Query(7, ge=1, le=90),
    settings: Settings = Depends(get_settings),
    _actor: RequestActor = Depends(require_permission("api_stats.view")),
):
    client = _get_redis(settings)
    try:
        timeline = []
        for i in range(days - 1, -1, -1):
            date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            pattern = f"api_stats:*:*:{date}:count"
            keys = client.keys(pattern)
            day_count = 0
            for key in keys:
                day_count += int(client.get(key) or 0)
            timeline.append({"date": date, "count": day_count})
        return {"timeline": timeline, "days": days}
    finally:
        client.close()
