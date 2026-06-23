"""Domain verification API routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, require_permission
from app.core.auth import RequestActor
from app.services.domain_verification_service import DomainVerificationService

router = APIRouter(prefix="/api/h5/sites", tags=["h5-sites"])


@router.post("/{site_id}/verify-dns")
async def verify_site_dns(
    site_id: str,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("sites.deploy")),
) -> dict:
    """Verify DNS A record and SSL certificate for a site's domain."""
    svc = DomainVerificationService(session)
    try:
        return svc.verify_domain(site_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
