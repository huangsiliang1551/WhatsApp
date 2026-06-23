"""WABA assignment and re-assignment API routes."""

from http import HTTPStatus

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, require_permission
from app.core.auth import RequestActor
from app.db.models import SiteWABABinding, WhatsAppBusinessAccount
from app.services.notification_service import NotificationService
from app.services.runtime_state import RuntimeStateStore

router = APIRouter(prefix="/api/waba", tags=["waba"])


class AssignWABARequest(BaseModel):
    site_id: str


class ReassignWABARequest(BaseModel):
    site_id: str


@router.post("/{waba_id}/assign")
async def assign_waba(
    waba_id: str,
    data: AssignWABARequest,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("sites.waba_assign")),
) -> dict:
    """Assign a WABA to a site (super admin only).
    Checks that this WABA is not already assigned to another site.
    """
    waba = session.get(WhatsAppBusinessAccount, waba_id)
    if waba is None:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="WABA not found")

    # Check if already assigned to any site
    existing_any = session.execute(
        select(SiteWABABinding).where(SiteWABABinding.waba_id == waba_id)
    ).scalars().all()

    for b in existing_any:
        if b.site_id != data.site_id:
            raise HTTPException(
                status_code=409,
                detail=f"WABA is already assigned to site {b.site_id}. Use reassign or revoke first.",
            )

    # Check binding doesn't already exist for this specific site
    existing = next((b for b in existing_any if b.site_id == data.site_id), None)
    if existing:
        return {"message": "WABA already assigned to this site", "binding_id": existing.id}

    binding = SiteWABABinding(
        id=__import__("uuid").uuid4().hex[:36],
        site_id=data.site_id,
        waba_id=waba_id,
        assigned_by=_actor.actor_id,
    )
    session.add(binding)
    session.flush()

    # Audit log
    RuntimeStateStore(session).add_audit_log(
        account_id=waba.account_id,
        actor_type="admin",
        actor_id=_actor.actor_id,
        action="waba.assign",
        target_type="site",
        target_id=data.site_id,
        payload={"waba_id": waba_id, "binding_id": binding.id},
    )

    # Notification
    NotificationService(session).create_notification(
        account_id=waba.account_id, type="waba", category="system",
        title="WABA 已分配",
        message=f"WABA {waba_id} 已分配给站点 {data.site_id}",
        severity="info",
    )

    return {
        "message": "WABA assigned to site",
        "binding_id": binding.id,
        "site_id": data.site_id,
        "waba_id": waba_id,
    }


@router.post("/{waba_id}/reassign")
async def reassign_waba(
    waba_id: str,
    data: ReassignWABARequest,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("sites.waba_assign")),
) -> dict:
    """Reassign a WABA to a different site (super admin only).
    First revokes all existing bindings, then assigns to the new site.
    """
    waba = session.get(WhatsAppBusinessAccount, waba_id)
    if waba is None:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="WABA not found")

    # Remove all existing bindings for this WABA
    existing_bindings = session.execute(
        select(SiteWABABinding).where(SiteWABABinding.waba_id == waba_id)
    ).scalars().all()

    for b in existing_bindings:
        session.delete(b)

    # Create new binding
    binding = SiteWABABinding(
        id=__import__("uuid").uuid4().hex[:36],
        site_id=data.site_id,
        waba_id=waba_id,
        assigned_by=_actor.actor_id,
    )
    session.add(binding)
    session.flush()

    # Audit log
    RuntimeStateStore(session).add_audit_log(
        account_id=waba.account_id,
        actor_type="admin",
        actor_id=_actor.actor_id,
        action="waba.reassign",
        target_type="site",
        target_id=data.site_id,
        payload={"waba_id": waba_id, "binding_id": binding.id},
    )

    # Notification
    NotificationService(session).create_notification(
        account_id=waba.account_id, type="waba", category="system",
        title="WABA 已重分配",
        message=f"WABA {waba_id} 已重新分配给站点 {data.site_id}",
        severity="info",
    )

    return {
        "message": "WABA reassigned to new site",
        "binding_id": binding.id,
        "site_id": data.site_id,
        "waba_id": waba_id,
    }


@router.post("/{waba_id}/revoke")
async def revoke_waba(
    waba_id: str,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("sites.waba_assign")),
) -> dict:
    """Revoke a WABA from all sites (unassign without reassigning)."""
    waba = session.get(WhatsAppBusinessAccount, waba_id)
    if waba is None:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="WABA not found")

    existing_bindings = session.execute(
        select(SiteWABABinding).where(SiteWABABinding.waba_id == waba_id)
    ).scalars().all()

    revoked_sites = []
    for b in existing_bindings:
        revoked_sites.append(b.site_id)
        session.delete(b)

    session.flush()

    # Audit log
    RuntimeStateStore(session).add_audit_log(
        account_id=waba.account_id,
        actor_type="admin",
        actor_id=_actor.actor_id,
        action="waba.revoke",
        target_type="waba",
        target_id=waba_id,
        payload={"revoked_sites": revoked_sites},
    )

    # Notification
    NotificationService(session).create_notification(
        account_id=waba.account_id, type="waba", category="system",
        title="WABA 已收回",
        message=f"WABA {waba_id} 已从所有站点收回",
        severity="warning",
    )

    return {
        "message": "WABA revoked from all sites",
        "waba_id": waba_id,
        "revoked_sites": revoked_sites,
    }


@router.get("/{waba_id}/assignment")
async def get_waba_assignment(
    waba_id: str,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("meta.view")),
) -> dict:
    """Get WABA current assignment status."""
    waba = session.get(WhatsAppBusinessAccount, waba_id)
    if waba is None:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="WABA not found")

    bindings = session.execute(
        select(SiteWABABinding).where(SiteWABABinding.waba_id == waba_id)
    ).scalars().all()

    return {
        "id": waba.id,
        "waba_id": waba.waba_id,
        "account_id": waba.account_id,
        "agency_id": waba.agency_id,
        "is_assigned": len(bindings) > 0,
        "assigned_sites": [
            {
                "binding_id": b.id,
                "site_id": b.site_id,
                "assigned_at": b.assigned_at.isoformat() if b.assigned_at else None,
                "assigned_by": b.assigned_by,
            }
            for b in bindings
        ],
    }


@router.get("/{waba_id}")
async def get_waba(
    waba_id: str,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("meta.view")),
) -> dict:
    """Get WABA details with site bindings."""
    waba = session.get(WhatsAppBusinessAccount, waba_id)
    if waba is None:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="WABA not found")

    bindings = session.execute(
        select(SiteWABABinding).where(SiteWABABinding.waba_id == waba_id)
    ).scalars().all()

    return {
        "id": waba.id,
        "waba_id": waba.waba_id,
        "account_id": waba.account_id,
        "agency_id": waba.agency_id,
        "webhook_verification_status": waba.webhook_verification_status,
        "webhook_runtime_status": waba.webhook_runtime_status,
        "is_active": waba.is_active,
        "ai_enabled": waba.ai_enabled,
        "site_bindings": [
            {"id": b.id, "site_id": b.site_id, "assigned_at": b.assigned_at.isoformat() if b.assigned_at else None}
            for b in bindings
        ],
    }
