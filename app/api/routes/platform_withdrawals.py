from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_platform_withdrawal_service, get_runtime_state_service, require_permission
from app.core.auth import RequestActor
from app.schemas.platform_withdrawals import (
    PlatformWithdrawalDuplicateAccountsResponse,
    PlatformWithdrawalResponse,
    PlatformWithdrawalStatus,
    PlatformWithdrawalStatusUpdateRequest,
)
from app.services.platform_withdrawal_service import PlatformWithdrawalService
from app.services.runtime_state import RuntimeStateStore

router = APIRouter(prefix="/api/platform", tags=["platform-withdrawals"])


@router.get(
    "/withdrawals",
    summary="List platform withdrawals",
    description="List platform withdrawal requests with optional filters.",
    tags=["platform-withdrawals"],
)
async def list_platform_withdrawals(
    account_id: str | None = None,
    status: PlatformWithdrawalStatus | None = None,
    withdrawal_service: PlatformWithdrawalService = Depends(get_platform_withdrawal_service),
    actor: RequestActor = Depends(require_permission("finance.view_withdrawal")),
) -> list[PlatformWithdrawalResponse]:
    if account_id is not None:
        actor.require_account_access(account_id)
    allowed_account_ids = None if actor.is_super_admin else set(actor.account_ids)
    return await withdrawal_service.list_withdrawals(
        account_id=account_id,
        allowed_account_ids=allowed_account_ids,
        status=status,
    )


@router.post(
    "/withdrawals/{withdrawal_id}/status",
    summary="Update withdrawal status",
    description="Update the status of a platform withdrawal request.",
    tags=["platform-withdrawals"],
)
async def update_platform_withdrawal_status(
    withdrawal_id: str,
    payload: PlatformWithdrawalStatusUpdateRequest,
    withdrawal_service: PlatformWithdrawalService = Depends(get_platform_withdrawal_service),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("finance.approve_withdrawal")),
) -> PlatformWithdrawalResponse:
    try:
        current = await withdrawal_service.get_withdrawal(withdrawal_id=withdrawal_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    actor.require_account_access(current.account_id)
    try:
        updated = await withdrawal_service.update_withdrawal_status(
            withdrawal_id=withdrawal_id,
            status=payload.status,
            note=payload.note,
            rejection_reason=payload.rejection_reason,
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    runtime_state.add_audit_log(
        account_id=updated.account_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        action="platform_withdrawal_status_updated",
        target_type="withdrawal_request",
        target_id=updated.id,
        payload={
            "request_no": updated.request_no,
            "status": updated.status,
            "rejection_reason": updated.rejection_reason,
        },
    )
    runtime_state.commit()
    return updated


@router.get(
    "/withdrawals/{withdrawal_id}/duplicate-accounts",
    summary="Get duplicate withdrawal accounts",
    description="Return overlapping members that used the same withdrawal account fingerprint.",
    tags=["platform-withdrawals"],
)
async def get_platform_withdrawal_duplicate_accounts(
    withdrawal_id: str,
    withdrawal_service: PlatformWithdrawalService = Depends(get_platform_withdrawal_service),
    actor: RequestActor = Depends(require_permission("withdrawal.duplicate_account.view")),
) -> PlatformWithdrawalDuplicateAccountsResponse:
    try:
        current = await withdrawal_service.get_withdrawal(withdrawal_id=withdrawal_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    actor.require_account_access(current.account_id)
    try:
        return await withdrawal_service.get_duplicate_accounts(withdrawal_id=withdrawal_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
