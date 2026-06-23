from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, get_queue_service, require_permission
from app.core.auth import RequestActor
from app.core.settings import Settings, get_settings
from app.services.dashboard_service import DashboardService
from app.services.queue_service import QueueService

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def _get_dashboard_service(
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    queue_service: QueueService = Depends(get_queue_service),
) -> DashboardService:
    return DashboardService(session=session, settings=settings, queue_service=queue_service)


@router.get(
    "/summary",
    summary="Get dashboard summary",
    description="Get aggregated dashboard data including system health, conversation stats, message stats, AI performance, and queue status.",
    tags=["dashboard"],
)
async def get_dashboard_summary(
    dashboard_service: DashboardService = Depends(_get_dashboard_service),
    actor: RequestActor = Depends(require_permission("dashboard.view")),
) -> dict:
    agency_id = None if actor.is_super_admin else actor.agency_id
    return await dashboard_service.get_summary(agency_id=agency_id)


@router.get(
    "/todo",
    summary="Get todo items",
    description="Get aggregated todo items including handover recommendations, pending reviews, open tickets, pending withdrawals, and dead letter jobs.",
    tags=["dashboard"],
)
async def get_todo_items(
    dashboard_service: DashboardService = Depends(_get_dashboard_service),
    actor: RequestActor = Depends(require_permission("dashboard.view")),
) -> dict:
    agency_id = None if actor.is_super_admin else actor.agency_id
    return await dashboard_service.get_todo_items(agency_id=agency_id)


@router.get(
    "/message-trend",
    summary="Get message trend",
    description="Get hourly message trend data. Supports 24h, 7d, or 30d windows.",
    tags=["dashboard"],
)
async def get_message_trend(
    hours: int = Query(default=24, description="Time window in hours (24, 168, 720)"),
    dashboard_service: DashboardService = Depends(_get_dashboard_service),
    actor: RequestActor = Depends(require_permission("dashboard.view")),
) -> dict:
    validated_hours = max(1, min(hours, 720))
    agency_id = None if actor.is_super_admin else actor.agency_id
    return await dashboard_service.get_message_trend(hours=validated_hours, agency_id=agency_id)


@router.get(
    "/ai-performance",
    summary="Get AI performance",
    description="Get AI performance trend data grouped by day. Shows reply rate, fallback rate, and handover rate.",
    tags=["dashboard"],
)
async def get_ai_performance(
    days: int = Query(default=7, ge=1, le=90, description="Number of days to include"),
    dashboard_service: DashboardService = Depends(_get_dashboard_service),
    actor: RequestActor = Depends(require_permission("dashboard.view")),
) -> dict:
    agency_id = None if actor.is_super_admin else actor.agency_id
    return await dashboard_service.get_ai_performance(days=days, agency_id=agency_id)


@router.get(
    "/top-intents",
    summary="Get top intents",
    description="Get the most common intents detected in conversations within the given time range.",
    tags=["dashboard"],
)
async def get_top_intents(
    days: int = Query(default=7, ge=1, le=90, description="Number of days to include"),
    limit: int = Query(default=10, ge=1, le=50, description="Maximum number of intents to return"),
    dashboard_service: DashboardService = Depends(_get_dashboard_service),
    actor: RequestActor = Depends(require_permission("dashboard.view")),
) -> dict:
    agency_id = None if actor.is_super_admin else actor.agency_id
    return await dashboard_service.get_top_intents(days=days, limit=limit, agency_id=agency_id)
