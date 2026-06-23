"""Site analytics API routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, require_permission
from app.core.auth import RequestActor
from app.services.h5_site_analytics_service import H5SiteAnalyticsService

router = APIRouter(prefix="/api/h5/sites", tags=["h5-sites"])



@router.get("/{site_id}/analytics")
async def get_site_analytics(
    site_id: str,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("sites.analytics")),
) -> dict:
    """Get aggregated analytics for an H5 site."""
    svc = H5SiteAnalyticsService(session)
    try:
        return svc.get_analytics(site_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
