from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import (
    get_platform_member_verification_service,
    get_runtime_state_service,
    require_permission,
)
from app.core.auth import RequestActor
from app.schemas.platform_member_verifications import (
    PlatformMemberVerificationActionRequest,
    PlatformMemberVerificationResponse,
    PlatformMemberVerificationStatus,
    PlatformMemberVerificationStatusUpdateRequest,
)
from app.services.platform_member_verification_service import PlatformMemberVerificationService
from app.services.runtime_state import RuntimeStateStore

router = APIRouter(prefix="/api/platform", tags=["platform-member-verifications"])


async def _update_member_verification_status(
    *,
    request_id: str,
    status: PlatformMemberVerificationStatus,
    note: str | None,
    verification_service: PlatformMemberVerificationService,
    runtime_state: RuntimeStateStore,
    actor: RequestActor,
) -> PlatformMemberVerificationResponse:
    try:
        current = await verification_service.get_request(request_id=request_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    actor.require_account_access(current.account_id)
    try:
        updated = await verification_service.update_status(
            request_id=request_id,
            status=status,
            note=note,
            reviewer_actor_id=actor.actor_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    runtime_state.add_audit_log(
        account_id=updated.account_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        action="platform_member_verification_status_updated",
        target_type="member_verification_request",
        target_id=updated.id,
        payload={
            "member_profile_id": updated.member_profile_id,
            "member_no": updated.member_no,
            "status": updated.status,
            "note": note,
        },
    )
    runtime_state.commit()
    return updated


@router.get(
    "/member-verifications",
    summary="List member verifications",
    description="List platform member verification requests.",
    tags=["platform-member-verifications"],
)
async def list_platform_member_verifications(
    account_id: str | None = None,
    status: PlatformMemberVerificationStatus | None = None,
    verification_service: PlatformMemberVerificationService = Depends(get_platform_member_verification_service),
    actor: RequestActor = Depends(require_permission("users.view")),
) -> list[PlatformMemberVerificationResponse]:
    if account_id is not None:
        actor.require_account_access(account_id)
    allowed_account_ids = None if actor.is_super_admin else set(actor.account_ids)
    return await verification_service.list_requests(
        account_id=account_id,
        allowed_account_ids=allowed_account_ids,
        status=status,
    )


@router.get(
    "/member-verifications/{request_id}",
    summary="Get member verification",
    description="Get a specific platform member verification request.",
    tags=["platform-member-verifications"],
)
async def get_platform_member_verification(
    request_id: str,
    verification_service: PlatformMemberVerificationService = Depends(get_platform_member_verification_service),
    actor: RequestActor = Depends(require_permission("users.view")),
) -> PlatformMemberVerificationResponse:
    try:
        detail = await verification_service.get_request(request_id=request_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    actor.require_account_access(detail.account_id)
    return detail


@router.post(
    "/member-verifications/{request_id}/status",
    summary="Update verification status",
    description="Update the status of a member verification request.",
    tags=["platform-member-verifications"],
)
async def update_platform_member_verification_status(
    request_id: str,
    payload: PlatformMemberVerificationStatusUpdateRequest,
    verification_service: PlatformMemberVerificationService = Depends(get_platform_member_verification_service),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("users.edit")),
) -> PlatformMemberVerificationResponse:
    return await _update_member_verification_status(
        request_id=request_id,
        status=payload.status,
        note=payload.note,
        verification_service=verification_service,
        runtime_state=runtime_state,
        actor=actor,
    )


@router.post(
    "/member-verification/requests/{request_id}/approve",
    summary="Approve verification request",
    description="Approve a pending member verification request.",
    tags=["platform-member-verifications"],
)
async def approve_platform_member_verification_request(
    request_id: str,
    payload: PlatformMemberVerificationActionRequest,
    verification_service: PlatformMemberVerificationService = Depends(get_platform_member_verification_service),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("users.edit")),
) -> PlatformMemberVerificationResponse:
    note = (payload.comment or payload.reason or "").strip() or None
    return await _update_member_verification_status(
        request_id=request_id,
        status="approved",
        note=note,
        verification_service=verification_service,
        runtime_state=runtime_state,
        actor=actor,
    )


@router.post(
    "/member-verification/requests/{request_id}/reject",
    summary="Reject verification request",
    description="Reject a pending member verification request.",
    tags=["platform-member-verifications"],
)
async def reject_platform_member_verification_request(
    request_id: str,
    payload: PlatformMemberVerificationActionRequest,
    verification_service: PlatformMemberVerificationService = Depends(get_platform_member_verification_service),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("users.edit")),
) -> PlatformMemberVerificationResponse:
    note = (payload.comment or payload.reason or "").strip() or None
    return await _update_member_verification_status(
        request_id=request_id,
        status="rejected",
        note=note,
        verification_service=verification_service,
        runtime_state=runtime_state,
        actor=actor,
    )
