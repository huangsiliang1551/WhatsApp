from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, require_permission
from app.core.auth import RequestActor
from app.db.models import ClientError

router = APIRouter(prefix="/api/h5/client-errors", tags=["h5-client-errors"])


class ClientErrorReportRequest(BaseModel):
    site_key: str | None = None
    error_type: str  # "javascript" / "resource" / "promise"
    message: str
    stack_trace: str | None = None
    url: str | None = None


@router.post("", status_code=201)
async def report_client_error(
    payload: ClientErrorReportRequest,
    request: Request,
    session: Session = Depends(get_db_session),
) -> dict:
    """Record a frontend JS error."""
    error = ClientError(
        id=str(uuid4()),
        site_key=payload.site_key,
        error_type=payload.error_type,
        message=payload.message,
        stack_trace=payload.stack_trace,
        url=payload.url,
        user_agent=request.headers.get("User-Agent"),
        ip_address=request.client.host if request.client else None,
    )
    session.add(error)
    session.commit()
    return {"status": "ok", "id": error.id}


@router.get("")
async def list_client_errors(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    error_type: str | None = Query(None),
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("monitoring.view")),
) -> dict:
    """List client errors with pagination."""
    from app.services.client_error_service import ClientErrorService

    svc = ClientErrorService(session)
    errors = svc.list_errors(limit=limit, offset=offset, error_type=error_type)
    total = svc.count_errors(error_type=error_type)
    return {
        "items": [
            {
                "id": e.id,
                "site_key": e.site_key,
                "error_type": e.error_type,
                "message": e.message,
                "stack_trace": e.stack_trace,
                "url": e.url,
                "user_agent": e.user_agent,
                "ip_address": e.ip_address,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in errors
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{error_id}")
async def get_client_error(
    error_id: str,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("monitoring.view")),
) -> dict:
    """Get a single client error by ID with full details."""
    error = session.get(ClientError, error_id)
    if not error:
        raise HTTPException(status_code=404, detail=f"Client error '{error_id}' not found.")
    return {
        "id": error.id,
        "site_key": error.site_key,
        "error_type": error.error_type,
        "message": error.message,
        "stack_trace": error.stack_trace,
        "url": error.url,
        "user_agent": error.user_agent,
        "ip_address": error.ip_address,
        "created_at": error.created_at.isoformat() if error.created_at else None,
    }


@router.delete("/{error_id}", status_code=204)
async def delete_client_error(
    error_id: str,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("monitoring.manage")),
) -> None:
    """Delete a client error."""
    from app.services.client_error_service import ClientErrorService

    svc = ClientErrorService(session)
    try:
        svc.delete_error(error_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
