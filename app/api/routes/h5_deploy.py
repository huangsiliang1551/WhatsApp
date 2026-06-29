from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, require_permission
from app.core.auth import RequestActor
from app.db.models import H5Site, H5SiteConfig
from app.services.h5_deploy_service import H5DeployService

router = APIRouter(prefix="/api/h5/sites", tags=["h5-deploy"])


class H5GatewayDeployRequest(BaseModel):
    gateway_node_id: str | None = None


def _load_site_and_config(session: Session, site_id: str) -> tuple[H5Site, H5SiteConfig]:
    site = session.get(H5Site, site_id)
    if not site:
        raise HTTPException(status_code=404, detail=f"Site '{site_id}' not found.")
    config = session.scalar(select(H5SiteConfig).where(H5SiteConfig.site_id == site_id))
    if not config:
        raise HTTPException(status_code=404, detail=f"Site config not found for site '{site_id}'.")
    return site, config


def _serialize_job(job) -> dict[str, object]:
    return {
        "id": job.id,
        "job_type": job.job_type,
        "node_id": job.node_id,
        "status": job.status,
        "input_json": job.input_json or {},
    }


@router.post("/{site_id}/deploy-script")
async def generate_deploy_script(
    site_id: str,
    actor: RequestActor = Depends(require_permission("sites.deploy")),
    session: Session = Depends(get_db_session),
) -> dict:
    site, config = _load_site_and_config(session, site_id)
    script = H5DeployService(session).generate_deploy_script(site, config)
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
    site, config = _load_site_and_config(session, site_id)
    results = H5DeployService(session).verify_deployment(site, config)
    return {
        "site_id": site_id,
        "domain": config.domain or site.domain,
        "results": results,
    }


@router.post("/{site_id}/deploy-to-gateway", status_code=status.HTTP_202_ACCEPTED)
async def deploy_to_gateway(
    site_id: str,
    payload: H5GatewayDeployRequest,
    actor: RequestActor = Depends(require_permission("sites.deploy")),
    session: Session = Depends(get_db_session),
) -> dict[str, object]:
    site, config = _load_site_and_config(session, site_id)
    service = H5DeployService(session)
    try:
        job = service.queue_gateway_deploy(
            site=site,
            config=config,
            gateway_node_id=payload.gateway_node_id,
            requested_by=actor.actor_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    session.commit()
    return {"job": _serialize_job(job)}


@router.post("/{site_id}/block-domain", status_code=status.HTTP_202_ACCEPTED)
async def block_domain(
    site_id: str,
    payload: H5GatewayDeployRequest | None = None,
    actor: RequestActor = Depends(require_permission("sites.deploy")),
    session: Session = Depends(get_db_session),
) -> dict[str, object]:
    site, config = _load_site_and_config(session, site_id)
    service = H5DeployService(session)
    try:
        job = service.queue_domain_block(
            site=site,
            config=config,
            gateway_node_id=payload.gateway_node_id if payload else None,
            requested_by=actor.actor_id,
            blocked=True,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    session.commit()
    return {"job": _serialize_job(job)}


@router.post("/{site_id}/unblock-domain", status_code=status.HTTP_202_ACCEPTED)
async def unblock_domain(
    site_id: str,
    payload: H5GatewayDeployRequest | None = None,
    actor: RequestActor = Depends(require_permission("sites.deploy")),
    session: Session = Depends(get_db_session),
) -> dict[str, object]:
    site, config = _load_site_and_config(session, site_id)
    service = H5DeployService(session)
    try:
        job = service.queue_domain_block(
            site=site,
            config=config,
            gateway_node_id=payload.gateway_node_id if payload else None,
            requested_by=actor.actor_id,
            blocked=False,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    session.commit()
    return {"job": _serialize_job(job)}


@router.post("/{site_id}/gateway-health-check", status_code=status.HTTP_202_ACCEPTED)
async def gateway_health_check(
    site_id: str,
    payload: H5GatewayDeployRequest | None = None,
    actor: RequestActor = Depends(require_permission("sites.deploy")),
    session: Session = Depends(get_db_session),
) -> dict[str, object]:
    site, config = _load_site_and_config(session, site_id)
    service = H5DeployService(session)
    try:
        job = service.queue_gateway_health_check(
            site=site,
            config=config,
            gateway_node_id=payload.gateway_node_id if payload else None,
            requested_by=actor.actor_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    session.commit()
    return {"job": _serialize_job(job)}


@router.post("/{site_id}/issue-certificate", status_code=status.HTTP_202_ACCEPTED)
async def issue_certificate(
    site_id: str,
    payload: H5GatewayDeployRequest | None = None,
    actor: RequestActor = Depends(require_permission("sites.deploy")),
    session: Session = Depends(get_db_session),
) -> dict[str, object]:
    site, config = _load_site_and_config(session, site_id)
    service = H5DeployService(session)
    try:
        job = service.queue_issue_certificate(
            site=site,
            config=config,
            gateway_node_id=payload.gateway_node_id if payload else None,
            requested_by=actor.actor_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    session.commit()
    return {"job": _serialize_job(job)}
