"""Site WABA list API route."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, require_permission
from app.core.auth import RequestActor
from app.db.models import SiteWABABinding

router = APIRouter(prefix="/api/sites", tags=["sites"])


@router.get("/{site_id}/waba")
async def list_site_waba(
    site_id: str,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("sites.waba_assign")),
) -> list[dict]:
    """Get all WABAs assigned to a site."""
    bindings = session.execute(
        select(SiteWABABinding).where(SiteWABABinding.site_id == site_id)
    ).scalars().all()

    return [
        {
            "id": b.id,
            "site_id": b.site_id,
            "waba_id": b.waba_id,
            "assigned_at": b.assigned_at.isoformat() if b.assigned_at else None,
            "assigned_by": b.assigned_by,
        }
        for b in bindings
    ]
