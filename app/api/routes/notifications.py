from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, require_permission
from app.core.auth import RequestActor
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("")
async def list_notifications(
    account_id: str | None = Query(default=None),
    user_id: str | None = Query(default=None),
    unread: bool | None = Query(default=None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    actor: RequestActor = Depends(require_permission("notifications.view")),
    session: Session = Depends(get_db_session),
) -> dict:
    if account_id:
        actor.require_account_access(account_id)
    svc = NotificationService(session)
    items, total = svc.list_notifications(
        account_id=account_id,
        user_id=user_id,
        unread_only=unread or False,
        limit=limit,
        offset=offset,
    )
    return {
        "items": [
            {
                "id": n.id,
                "account_id": n.account_id,
                "type": n.type,
                "category": n.category,
                "title": n.title,
                "message": n.message,
                "severity": n.severity,
                "is_read": n.is_read,
                "action_url": n.action_url,
                "metadata": n.metadata_json,
                "created_at": n.created_at.isoformat() if n.created_at else None,
                "read_at": n.read_at.isoformat() if n.read_at else None,
            }
            for n in items
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/unread-count")
async def get_unread_count(
    account_id: str | None = Query(default=None),
    user_id: str | None = Query(default=None),
    actor: RequestActor = Depends(require_permission("notifications.view")),
    session: Session = Depends(get_db_session),
) -> dict:
    if account_id:
        actor.require_account_access(account_id)
    svc = NotificationService(session)
    count = svc.get_unread_count(account_id=account_id, user_id=user_id)
    return {"unread_count": count}


@router.post("/mark-read")
async def mark_as_read(
    notification_ids: list[str] = Body(...),
    actor: RequestActor = Depends(require_permission("notifications.mark_read")),
    session: Session = Depends(get_db_session),
) -> dict:
    svc = NotificationService(session)
    count = svc.mark_as_read(notification_ids)
    return {"marked_count": count}


@router.post("/mark-all-read")
async def mark_all_as_read(
    account_id: str = Query(...),
    user_id: str | None = Query(default=None),
    actor: RequestActor = Depends(require_permission("notifications.mark_read")),
    session: Session = Depends(get_db_session),
) -> dict:
    actor.require_account_access(account_id)
    svc = NotificationService(session)
    count = svc.mark_all_as_read(account_id=account_id, user_id=user_id)
    return {"marked_count": count}
