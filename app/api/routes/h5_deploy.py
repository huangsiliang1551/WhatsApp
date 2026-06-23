from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, require_permission
from app.core.auth import RequestActor
from app.db.models import H5Site, H5SiteConfig
from app.services.h5_deploy_service import H5DeployService

router = APIRouter(prefix="/api/h5/sites", tags=["h5-deploy"])



@router.post("/{site_id}/deploy-script")
async def generate_deploy_script(
    site_id: str,
    actor: RequestActor = Depends(require_permission("sites.deploy")),
    session: Session = Depends(get_db_session),
) -> dict:
    site = session.get(H5Site, site_id)
    if not site:
        raise HTTPException(status_code=404, detail=f"Site '{site_id}' not found.")

    config = session.scalar(
        select(H5SiteConfig).where(H5SiteConfig.site_id == site_id)
    )
    if not config:
        raise HTTPException(status_code=404, detail=f"Site config not found for site '{site_id}'.")

    svc = H5DeployService()
    script = svc.generate_deploy_script(site, config)
    return {
        "site_id": site_id,
        "site_key": site.site_key,
        "domain": config.domain or site.domain,
        "script": script,
    }


@router.post("/{site_id}/verify-deployment")
async def verify_deployment(
    site_id: str,
    actor: RequestActor = Depends(require_permission("sites.deploy")),
    session: Session = Depends(get_db_session),
) -> dict:
    site = session.get(H5Site, site_id)
    if not site:
        raise HTTPException(status_code=404, detail=f"Site '{site_id}' not found.")

    config = session.scalar(
        select(H5SiteConfig).where(H5SiteConfig.site_id == site_id)
    )
    if not config:
        raise HTTPException(status_code=404, detail=f"Site config not found for site '{site_id}'.")

    svc = H5DeployService()
    results = svc.verify_deployment(site, config)
    return {
        "site_id": site_id,
        "domain": config.domain or site.domain,
        "results": results,
    }
