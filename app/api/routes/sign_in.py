from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, require_permission
from app.core.auth import RequestActor
from app.schemas.marketing import SignInConfigUpdateRequest
from app.services.sign_in_service import (
    AlreadySignedInError,
    SignInService,
    SignInTaskAlreadyCompletedError,
)

router = APIRouter(prefix="/api/sign-in", tags=["marketing"])


@router.post("")
async def sign_in(
    user_id: str = Query(..., min_length=1),
    account_id: str = Query(..., min_length=1),
    actor: RequestActor = Depends(require_permission("tasks.push")),
    session: Session = Depends(get_db_session),
) -> dict:
    actor.require_account_access(account_id)
    svc = SignInService(session)
    try:
        result = svc.sign_in(user_id, account_id)
    except AlreadySignedInError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except SignInTaskAlreadyCompletedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return result.model_dump()


@router.get("/status")
async def sign_in_status(
    user_id: str = Query(..., min_length=1),
    account_id: str = Query(..., min_length=1),
    actor: RequestActor = Depends(require_permission("tasks.view")),
    session: Session = Depends(get_db_session),
) -> dict:
    svc = SignInService(session)
    result = svc.get_status(user_id, account_id)
    return result.model_dump()


@router.get("/config")
async def get_sign_in_config(
    session: Session = Depends(get_db_session),
) -> dict:
    svc = SignInService(session)
    return svc.get_config()


@router.put("/config")
async def update_sign_in_config(
    payload: SignInConfigUpdateRequest,
    actor: RequestActor = Depends(require_permission("task_rules.signin_config")),
    session: Session = Depends(get_db_session),
) -> dict:
    svc = SignInService(session)
    svc.update_config(
        consecutive_days=payload.consecutive_days,
        reward_amount=payload.reward_amount,
    )
    return svc.get_config()
