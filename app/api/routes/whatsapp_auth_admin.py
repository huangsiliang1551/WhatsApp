from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.services.site_whatsapp_phone_pool_service import SiteWhatsAppPhonePoolService

router = APIRouter(prefix="/api/whatsapp-auth-admin", tags=["whatsapp-auth-admin"])


@router.get("/site-pools/{site_id}")
async def list_site_whatsapp_phone_pools(
    site_id: str,
    account_id: str,
    session: Session = Depends(get_db_session),
) -> list[dict[str, object]]:
    service = SiteWhatsAppPhonePoolService(session=session)
    pools = service.list_site_pools(account_id=account_id, site_id=site_id, active_only=False)
    if not pools:
        site = service.get_site_by_id(site_id=site_id)
        if site is None:
            raise HTTPException(status_code=404, detail={"code": "site_not_found", "message": "Site was not found."})
    return [
        {
            "id": pool.id,
            "siteId": pool.site_id,
            "accountId": pool.account_id,
            "wabaId": pool.waba_id,
            "phoneNumberId": pool.phone_number_id,
            "displayPhoneNumber": pool.display_phone_number,
            "status": pool.status,
            "weight": pool.weight,
            "priority": pool.priority,
        }
        for pool in pools
    ]
