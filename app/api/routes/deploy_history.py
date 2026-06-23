"""Deploy history API routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, require_permission, get_request_actor
from app.core.auth import RequestActor
from app.services.deploy_history_service import DeployHistoryService

router = APIRouter(prefix="/api/h5/sites", tags=["h5-sites"])


class CreateDeployHistoryRequest(BaseModel):
    action: str  # build / deploy / verify / rollback
    status: str  # success / error
    details: dict | None = None


@router.get("/{site_id}/deploy-history")
async def list_deploy_history(
    site_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("sites.deploy")),
) -> dict:
    """List deployment history for a site."""
    agency_id = None if actor.is_super_admin else actor.agency_id
    svc = DeployHistoryService(session)
    items = svc.list_history(site_id, limit=limit, offset=offset, agency_id=agency_id)
    return {"items": items, "limit": limit, "offset": offset}


@router.post("/{site_id}/deploy-history", status_code=201)
async def create_deploy_history(
    site_id: str,
    payload: CreateDeployHistoryRequest,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("sites.deploy")),
) -> dict:
    """Record a new deployment history entry."""
    svc = DeployHistoryService(session)
    return svc.create_history(
        site_id=site_id,
        action=payload.action,
        status=payload.status,
        details=payload.details,
    )
