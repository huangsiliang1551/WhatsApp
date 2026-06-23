from fastapi import APIRouter, Body, Depends, HTTPException, Query

from app.api.deps import get_db_session, require_permission
from app.core.auth import RequestActor
from app.schemas.platform import (
    BatchLifecycleRequest,
    BatchLifecycleResponse,
    CustomerTimelineResponse,
)
from app.services.customer_summary_service import CustomerSummaryService
from app.services.customer_timeline_service import CustomerTimelineService
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/customers", tags=["customers"])


# ── Static paths (must be before /{customer_id}) ─────────────────────


@router.post(
    "/batch-lifecycle",
    summary="Batch update customer lifecycle status",
    description="Batch block or unblock multiple customers.",
)
async def batch_update_lifecycle(
    payload: BatchLifecycleRequest,
    db_session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("customers.edit_lifecycle")),
) -> BatchLifecycleResponse:
    from app.core.platform_enums import UserLifecycleStatus
    from app.db.models import AppUser
    from sqlalchemy import or_, select as sa_select

    actor.require_account_access(payload.account_id)

    try:
        UserLifecycleStatus(payload.lifecycle_status)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid lifecycle_status '{payload.lifecycle_status}'. Must be one of: {[s.value for s in UserLifecycleStatus]}",
        )

    # Deduplicate
    unique_ids = list(dict.fromkeys(payload.customer_ids))
    updated: list[str] = []

    for cid in unique_ids:
        user = db_session.scalar(
            sa_select(AppUser).where(
                or_(
                    AppUser.id == cid,
                    AppUser.public_user_id == cid,
                ),
                AppUser.account_id == payload.account_id,
            )
        )
        if user is not None:
            user.lifecycle_status = payload.lifecycle_status
            updated.append(cid)

    db_session.commit()

    return BatchLifecycleResponse(
        updated_count=len(updated),
        lifecycle_status=payload.lifecycle_status,
        account_id=payload.account_id,
        customer_ids=updated,
    )


# ── Parameterized paths ─────────────────────────────────────────────


@router.get(
    "/{customer_id}/summary",
    summary="Get customer 360 summary",
    description="Get aggregated customer data including conversations, tickets, wallet, and member status.",
)
async def get_customer_summary(
    customer_id: str,
    account_id: str | None = Query(default=None),
    db_session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("customers.detail")),
) -> dict:
    if account_id:
        actor.require_account_access(account_id)
    service = CustomerSummaryService(db_session)
    return await service.get_summary(customer_id=customer_id, account_id=account_id)


@router.get(
    "/{customer_id}/timeline",
    summary="Get customer interaction timeline",
    description="Merged timeline of messages, tickets, verifications, WhatsApp bindings, wallet entries, and withdrawals.",
)
async def get_customer_timeline(
    customer_id: str,
    account_id: str | None = Query(default=None),
    limit: int = Query(default=30, ge=1, le=200),
    db_session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("customers.timeline")),
) -> CustomerTimelineResponse:
    if account_id:
        actor.require_account_access(account_id)
    service = CustomerTimelineService(db_session)
    return await service.get_timeline(
        customer_id=customer_id, account_id=account_id, limit=limit
    )


@router.patch(
    "/{customer_id}/lifecycle-status",
    summary="Update customer lifecycle status",
    description="Set customer lifecycle status (active/frozen/blacklisted). Used for blocking/unblocking users.",
)
async def update_customer_lifecycle_status(
    customer_id: str,
    account_id: str = Query(...),
    lifecycle_status: str = Body(..., embed=True),
    db_session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("customers.edit_lifecycle")),
) -> dict:
    """Block or unblock a customer by updating lifecycle_status.

    Valid values: active, frozen, blacklisted
    Blacklisted users will not receive messages or be able to initiate new conversations.
    """
    from app.core.platform_enums import UserLifecycleStatus
    from app.db.models import AppUser
    from sqlalchemy import or_, select as sa_select

    actor.require_account_access(account_id)

    try:
        UserLifecycleStatus(lifecycle_status)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid lifecycle_status '{lifecycle_status}'. Must be one of: {[s.value for s in UserLifecycleStatus]}",
        )

    # Support lookup by internal id or public_user_id (used by conversation customer_id)
    user = db_session.scalar(
        sa_select(AppUser).where(
            or_(
                AppUser.id == customer_id,
                AppUser.public_user_id == customer_id,
            ),
            AppUser.account_id == account_id,
        )
    )
    if user is None:
        raise HTTPException(status_code=404, detail=f"Customer '{customer_id}' not found in account '{account_id}'")

    old_status = user.lifecycle_status
    user.lifecycle_status = lifecycle_status
    db_session.commit()

    return {
        "customer_id": customer_id,
        "account_id": account_id,
        "lifecycle_status": lifecycle_status,
        "previous_status": old_status,
    }
