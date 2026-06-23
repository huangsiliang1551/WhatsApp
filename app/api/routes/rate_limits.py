"""Rate limits API — IV-BE-007.

Endpoints:
  GET    /api/rate-limits                   — list rules
  POST   /api/rate-limits                   — create rule
  PATCH  /api/rate-limits/{id}              — update rule
  DELETE /api/rate-limits/{id}              — delete rule
  GET    /api/rate-limits/banned-ips        — list banned IPs
  DELETE /api/rate-limits/banned-ips/{ip}   — unban IP
"""

from __future__ import annotations

import time as time_module
from datetime import datetime
from typing import Any

import redis as sync_redis
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, require_permission
from app.core.auth import RequestActor
from app.core.settings import Settings, get_settings
from app.db.models import ApiRateLimit

router = APIRouter(prefix="/api/rate-limits", tags=["rate-limits"])


class CreateRateLimitRequest(BaseModel):
    endpoint_pattern: str
    max_requests: int
    window_seconds: int
    ban_minutes: int = 30
    agency_id: str | None = None


class UpdateRateLimitRequest(BaseModel):
    endpoint_pattern: str | None = None
    max_requests: int | None = None
    window_seconds: int | None = None
    ban_minutes: int | None = None
    is_enabled: bool | None = None


# ─── CRUD ───────────────────────────────────────────────────────────────────


@router.get("", summary="频率限制规则列表")
def list_rules(
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("rate_limits.manage")),
):
    rules = session.scalars(
        select(ApiRateLimit).order_by(ApiRateLimit.created_at.desc())
    ).all()
    return [
        {
            "id": r.id,
            "agency_id": r.agency_id,
            "endpoint_pattern": r.endpoint_pattern,
            "max_requests": r.max_requests,
            "window_seconds": r.window_seconds,
            "ban_minutes": r.ban_minutes,
            "is_enabled": r.is_enabled,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rules
    ]


@router.post("", summary="创建频率限制规则", status_code=201)
def create_rule(
    body: CreateRateLimitRequest,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("rate_limits.manage")),
):
    rule = ApiRateLimit(
        agency_id=body.agency_id,
        endpoint_pattern=body.endpoint_pattern,
        max_requests=body.max_requests,
        window_seconds=body.window_seconds,
        ban_minutes=body.ban_minutes,
    )
    session.add(rule)
    session.flush()
    return {
        "id": rule.id,
        "endpoint_pattern": rule.endpoint_pattern,
        "max_requests": rule.max_requests,
        "window_seconds": rule.window_seconds,
    }


@router.patch("/{rule_id}", summary="编辑频率限制规则")
def update_rule(
    rule_id: str,
    body: UpdateRateLimitRequest,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("rate_limits.manage")),
):
    rule = session.get(ApiRateLimit, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")
    for key, value in body.model_dump().items():
        if value is not None:
            setattr(rule, key, value)
    return {
        "id": rule.id,
        "endpoint_pattern": rule.endpoint_pattern,
        "is_enabled": rule.is_enabled,
    }


@router.delete("/{rule_id}", summary="删除频率限制规则")
def delete_rule(
    rule_id: str,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("rate_limits.manage")),
):
    rule = session.get(ApiRateLimit, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")
    session.delete(rule)
    return {"success": True}


# ─── IP Ban management ──────────────────────────────────────────────────────


@router.get("/banned-ips", summary="被封禁 IP 列表")
def list_banned_ips(
    settings: Settings = Depends(get_settings),
    _actor: RequestActor = Depends(require_permission("rate_limits.manage")),
):
    client = sync_redis.from_url(settings.redis_url, socket_timeout=3)
    try:
        keys = client.keys("banned:*")
        results = []
        now = time_module.time()
        for key in keys:
            ip = key.decode() if isinstance(key, bytes) else key
            ip = ip.replace("banned:", "", 1)
            ttl = client.ttl(key)
            results.append({
                "ip": ip,
                "banned_at": datetime.fromtimestamp(now - (settings.ban_minutes if hasattr(settings, 'ban_minutes') else 30) * 60 + ttl).isoformat() if ttl > 0 else None,
                "remaining_seconds": max(ttl, 0),
                "remaining_minutes": round(max(ttl, 0) / 60, 1),
            })
        return results
    finally:
        client.close()


@router.delete("/banned-ips/{ip}", summary="解除 IP 封禁")
def unban_ip(
    ip: str,
    settings: Settings = Depends(get_settings),
    _actor: RequestActor = Depends(require_permission("rate_limits.manage")),
):
    client = sync_redis.from_url(settings.redis_url, socket_timeout=3)
    try:
        key = f"banned:{ip}"
        if client.exists(key):
            client.delete(key)
            return {"success": True, "ip": ip, "message": f"IP {ip} 已解封"}
        return {"success": False, "message": f"IP {ip} 未被封禁"}
    finally:
        client.close()
