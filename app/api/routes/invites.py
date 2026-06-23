from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, require_permission
from app.core.auth import RequestActor
from app.schemas.marketing import (
    InviteConfigUpdateRequest,
    RechargeCallbackRequest,
    RegisterCallbackRequest,
)
from app.services.invite_service import AntiFraudError, InviteLimitExceededError, InviteService

router = APIRouter(prefix="/api/invites", tags=["marketing"])


@router.get("/my-link")
async def get_my_invite_link(
    user_id: str = Query(..., min_length=1),
    account_id: str = Query(..., min_length=1),
    actor: RequestActor = Depends(require_permission("tasks.view")),
    session: Session = Depends(get_db_session),
) -> dict:
    svc = InviteService(session)
    link = svc.get_or_create_link(user_id, account_id)
    return {
        "id": link.id,
        "account_id": link.account_id,
        "user_id": link.user_id,
        "invite_code": link.invite_code,
        "invite_url": f"/invite?code={link.invite_code}",
        "created_at": link.created_at.isoformat() if link.created_at else None,
    }


@router.get("/my-records")
async def get_my_invite_records(
    user_id: str = Query(..., min_length=1),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    actor: RequestActor = Depends(require_permission("tasks.view")),
    session: Session = Depends(get_db_session),
) -> dict:
    svc = InviteService(session)
    return svc.get_my_records(user_id, page=page, size=size)


@router.post("/register-callback")
async def register_callback(
    payload: RegisterCallbackRequest,
    session: Session = Depends(get_db_session),
) -> dict:
    svc = InviteService(session)
    try:
        record = svc.on_register_callback(
            inviter_code=payload.inviter_code,
            invitee_user_id=payload.invitee_user_id,
            invitee_ip=payload.invitee_ip,
            invitee_device_id=payload.invitee_device_id,
        )
    except (LookupError, ValueError, InviteLimitExceededError, AntiFraudError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "rewarded": record is not None,
        "reward_amount": str(record.reward_amount) if record else "0",
    }


@router.post("/recharge-callback")
async def recharge_callback(
    payload: RechargeCallbackRequest,
    session: Session = Depends(get_db_session),
) -> dict:
    svc = InviteService(session)
    try:
        record = svc.on_recharge_callback(
            inviter_user_id=payload.inviter_user_id,
            invitee_user_id=payload.invitee_user_id,
            amount=payload.amount,
            invitee_ip=payload.invitee_ip,
            invitee_device_id=payload.invitee_device_id,
        )
    except (LookupError, ValueError, InviteLimitExceededError, AntiFraudError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "rewarded": record is not None,
        "reward_amount": str(record.reward_amount) if record else "0",
    }


@router.get("/config")
async def get_invite_config(
    session: Session = Depends(get_db_session),
) -> dict:
    svc = InviteService(session)
    return svc.get_config()


@router.put("/config")
async def update_invite_config(
    payload: InviteConfigUpdateRequest,
    actor: RequestActor = Depends(require_permission("settings.runtime")),
    session: Session = Depends(get_db_session),
) -> dict:
    svc = InviteService(session)
    svc.update_config(payload.model_dump(exclude_none=True))
    return svc.get_config()
