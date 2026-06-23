"""Agent audit log API routes.

Agents can view audit logs for their own sites.
All operations are automatically recorded via RuntimeStateStore.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.core.settings import Settings, get_settings
from app.db.models import Agency, AuditLog, H5Site

router = APIRouter(prefix="/api/agent-audit", tags=["agent-audit"])


def _get_agency_from_request(request, settings, session):
    """Get agency from JWT token."""
    from app.api.routes.agent_auth import _decode_agent_jwt

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header.")
    token = auth_header[7:]
    payload = _decode_agent_jwt(token, settings.admin_jwt_secret)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")

    agency = session.get(Agency, payload.get("agency_id"))
    if agency is None:
        raise HTTPException(status_code=401, detail="Agency not found.")
    return agency


@router.get("")
async def list_agent_audit_logs(
    request: Request,
    action: str | None = Query(default=None),
    target_type: str | None = Query(default=None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> dict:
    """List audit logs scoped to the authenticated agent's sites."""
    agency = _get_agency_from_request(request, settings, session)

    # Get all site IDs belonging to this agency
    site_ids = list(
        session.scalars(
            select(H5Site.id).where(H5Site.agency_id == agency.id)
        ).all()
    )

    # Build query filtering by site targets or agency-related actions
    query = select(AuditLog).order_by(AuditLog.created_at.desc())

    # Filter by target_id belonging to agent's sites, or agency-related actions
    site_id_set = set(site_ids) if site_ids else {None}
    query = query.where(
        AuditLog.target_id.in_(site_id_set) | (AuditLog.target_id == agency.id)
    )

    if action:
        query = query.where(AuditLog.action == action)
    if target_type:
        query = query.where(AuditLog.target_type == target_type)

    total = session.scalar(select(__import__("sqlalchemy").func.count()).select_from(query.subquery())) or 0

    items = session.execute(query.offset(offset).limit(limit)).scalars().all()

    return {
        "items": [
            {
                "id": item.id,
                "actor_type": item.actor_type,
                "actor_id": item.actor_id,
                "action": item.action,
                "target_type": item.target_type,
                "target_id": item.target_id,
                "payload": item.payload,
                "created_at": item.created_at.isoformat() if hasattr(item, "created_at") and item.created_at else None,
            }
            for item in items
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }
