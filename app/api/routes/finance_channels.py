"""Payment channel configuration API routes."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Any

from app.api.deps import get_db_session, require_permission
from app.core.auth import RequestActor
from app.services.payment_channel_service import PaymentChannelService
from app.services.channel_health_service import ChannelHealthService

router = APIRouter(prefix="/api/finance", tags=["finance"])


class ChannelCreateRequest(BaseModel):
    name: str
    channel_type: str
    app_id: str | None = None
    app_secret: str | None = None
    callback_url: str | None = None
    fee_rate: float = 0
    min_amount: float | None = None
    max_amount: float | None = None
    status: str = "active"
    is_sandbox: bool = False
    callback_secret: str | None = None
    config_json: dict[str, Any] | None = None


class ChannelUpdateRequest(BaseModel):
    name: str | None = None
    channel_type: str | None = None
    app_id: str | None = None
    app_secret: str | None = None
    callback_url: str | None = None
    fee_rate: float | None = None
    min_amount: float | None = None
    max_amount: float | None = None
    status: str | None = None
    is_sandbox: bool | None = None
    callback_secret: str | None = None
    config_json: dict[str, Any] | None = None


class AgentChannelUpdateRequest(BaseModel):
    is_enabled: bool = True
    is_recharge_enabled: bool = True
    is_withdraw_enabled: bool = True
    custom_merchant_id: str | None = None
    custom_secret: str | None = None


# ── Channels CRUD ──

@router.get("/channels")
def list_channels(
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("finance.view_channels")),
) -> list[dict]:
    svc = PaymentChannelService(session)
    return svc.list_channels()


@router.post("/channels", status_code=201)
def create_channel(
    data: ChannelCreateRequest,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("finance.edit_channels")),
) -> dict:
    svc = PaymentChannelService(session)
    return svc.create_channel(data.model_dump())


@router.patch("/channels/{channel_id}")
def update_channel(
    channel_id: str,
    data: ChannelUpdateRequest,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("finance.edit_channels")),
) -> dict:
    svc = PaymentChannelService(session)
    try:
        return svc.update_channel(channel_id, data.model_dump(exclude_none=True))
    except LookupError:
        raise HTTPException(status_code=404, detail="Channel not found")


@router.delete("/channels/{channel_id}")
def delete_channel(
    channel_id: str,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("finance.edit_channels")),
) -> dict:
    svc = PaymentChannelService(session)
    try:
        svc.delete_channel(channel_id)
        return {"message": "Channel deleted"}
    except LookupError:
        raise HTTPException(status_code=404, detail="Channel not found")


@router.get("/channels/{channel_id}/health")
def get_channel_health(
    channel_id: str,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("finance.view_channels")),
) -> dict:
    svc = ChannelHealthService(session)
    try:
        return svc.get_channel_health(channel_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Channel not found")


# ── Agent channel settings ──

@router.get("/agent-channels/{agency_id}")
def get_agent_channels(
    agency_id: str,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("finance.view_channels")),
) -> list[dict]:
    svc = PaymentChannelService(session)
    return svc.get_agent_channels(agency_id)


@router.put("/agent-channels/{agency_id}/{channel_id}")
def update_agent_channel(
    agency_id: str,
    channel_id: str,
    data: AgentChannelUpdateRequest,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("finance.edit_channels")),
) -> dict:
    svc = PaymentChannelService(session)
    return svc.upsert_agent_channel(agency_id, channel_id, data.model_dump())
