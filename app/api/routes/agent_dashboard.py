"""Agent dashboard API routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, require_permission
from app.core.auth import RequestActor
from app.services.agent_dashboard_service import AgentDashboardService

router = APIRouter(prefix="/api/agent-dashboard", tags=["agent-dashboard"])


@router.get("")
async def get_dashboard(
    agency_id: str,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("dashboard.view")),
) -> dict:
    """Get full dashboard data for an agency."""
    svc = AgentDashboardService(session)
    try:
        return svc.get_dashboard(agency_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/sites")
async def get_site_stats(
    agency_id: str,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("dashboard.view")),
) -> list[dict]:
    """Get per-site statistics."""
    svc = AgentDashboardService(session)
    return svc.get_site_stats(agency_id)


@router.get("/revenue")
async def get_revenue_stats(
    agency_id: str,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("dashboard.view")),
) -> dict:
    """Get revenue statistics."""
    svc = AgentDashboardService(session)
    return svc.get_revenue_stats(agency_id)


@router.get("/members")
async def get_member_stats(
    agency_id: str,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("dashboard.view")),
) -> list[dict]:
    """Get member statistics."""
    svc = AgentDashboardService(session)
    return svc.get_member_stats(agency_id)
