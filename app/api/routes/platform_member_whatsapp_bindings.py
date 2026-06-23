from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import (
    get_platform_member_whatsapp_binding_service,
    get_runtime_state_service,
    require_permission,
)
from app.core.auth import RequestActor
from app.schemas.platform_member_whatsapp_bindings import (
    PlatformMemberWhatsAppBindingResponse,
    PlatformMemberWhatsAppBindingStatus,
    PlatformMemberWhatsAppBindingStatusUpdateRequest,
)
from app.services.platform_member_whatsapp_binding_service import PlatformMemberWhatsAppBindingService
from app.services.runtime_state import RuntimeStateStore

router = APIRouter(prefix="/api/platform", tags=["platform-member-whatsapp-bindings"])


@router.get(
    "/member-whatsapp-bindings",
    summary="List WhatsApp bindings",
    description="List platform member WhatsApp binding requests.",
    tags=["platform-member-whatsapp-bindings"],
)
async def list_platform_member_whatsapp_bindings(
    account_id: str | None = None,
    status: PlatformMemberWhatsAppBindingStatus | None = None,
    binding_service: PlatformMemberWhatsAppBindingService = Depends(
        get_platform_member_whatsapp_binding_service
    ),
    actor: RequestActor = Depends(require_permission("users.view")),
) -> list[PlatformMemberWhatsAppBindingResponse]:
    if account_id is not None:
        actor.require_account_access(account_id)
    allowed_account_ids = None if actor.is_super_admin else set(actor.account_ids)
    return await binding_service.list_requests(
        account_id=account_id,
        allowed_account_ids=allowed_account_ids,
        status=status,
    )


@router.get(
    "/member-whatsapp-bindings/{request_id}",
    summary="Get WhatsApp binding",
    description="Get a specific platform member WhatsApp binding request.",
    tags=["platform-member-whatsapp-bindings"],
)
async def get_platform_member_whatsapp_binding(
    request_id: str,
    binding_service: PlatformMemberWhatsAppBindingService = Depends(
        get_platform_member_whatsapp_binding_service
    ),
    actor: RequestActor = Depends(require_permission("users.view")),
) -> PlatformMemberWhatsAppBindingResponse:
    try:
        detail = await binding_service.get_request(request_id=request_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    actor.require_account_access(detail.account_id)
    return detail


@router.post(
    "/member-whatsapp-bindings/{request_id}/status",
    summary="Update binding status",
    description="Update the status of a WhatsApp binding request.",
    tags=["platform-member-whatsapp-bindings"],
)
async def update_platform_member_whatsapp_binding_status(
    request_id: str,
    payload: PlatformMemberWhatsAppBindingStatusUpdateRequest,
    binding_service: PlatformMemberWhatsAppBindingService = Depends(
        get_platform_member_whatsapp_binding_service
    ),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("users.edit")),
) -> PlatformMemberWhatsAppBindingResponse:
    try:
        current = await binding_service.get_request(request_id=request_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    actor.require_account_access(current.account_id)
    try:
        updated = await binding_service.update_status(
            request_id=request_id,
            status=payload.status,
            note=payload.note,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    runtime_state.add_audit_log(
        account_id=updated.account_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        action="platform_member_whatsapp_binding_status_updated",
        target_type="member_whatsapp_binding_request",
        target_id=updated.id,
        payload={
            "member_profile_id": updated.member_profile_id,
            "member_no": updated.member_no,
            "public_user_id": updated.public_user_id,
            "status": updated.status,
            "requested_phone_number": updated.requested_phone_number,
            "note": payload.note,
        },
    )
    runtime_state.commit()
    return updated
