from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, require_permission
from app.core.auth import RequestActor
from app.db.models import H5FrontendRelease, H5GatewayNode, H5GatewayNodeRelease
from app.services.h5_gateway_job_service import H5GatewayJobService
from app.services.h5_gateway_node_service import H5GatewayNodeService
from app.services.h5_gateway_ssh_service import H5GatewaySSHService

router = APIRouter(prefix="/api/h5-gateway", tags=["h5-gateway"])


class H5GatewayNodeCreateRequest(BaseModel):
    name: str
    node_code: str
    ssh_host: str
    ssh_port: int = 22
    ssh_user: str
    ssh_secret: str
    agent_token: str | None = None
    public_ip: str | None = None
    private_ip: str | None = None
    region: str | None = None


class H5GatewayDeployFrontendRequest(BaseModel):
    version: str = Field(min_length=1, max_length=64)
    artifact_url: str = Field(min_length=1, max_length=1024)
    artifact_sha256: str = Field(min_length=1, max_length=128)


class H5GatewaySyncConfigDomainRequest(BaseModel):
    domain: str = Field(min_length=1, max_length=255)
    site_key: str = Field(min_length=1, max_length=64)
    root_dir: str = Field(min_length=1, max_length=512)
    certificate_mode: str = Field(min_length=1, max_length=64)
    blocked: bool = False


class H5GatewaySyncConfigRequest(BaseModel):
    upstream_base_url: str = Field(min_length=1, max_length=1024)
    origin_verify_header: str = Field(min_length=1, max_length=255)
    domains: list[H5GatewaySyncConfigDomainRequest] = Field(min_length=1)


class H5GatewayReleaseCreateRequest(BaseModel):
    version: str = Field(min_length=1, max_length=64)
    artifact_url: str = Field(min_length=1, max_length=1024)
    artifact_sha256: str = Field(min_length=1, max_length=128)
    build_commit: str | None = Field(default=None, max_length=64)


class H5GatewayReleaseDeployRequest(BaseModel):
    node_id: str = Field(min_length=1, max_length=64)


def _node_service(session: Session) -> H5GatewayNodeService:
    return H5GatewayNodeService(session)


def _serialize_release(release: H5FrontendRelease) -> dict[str, object]:
    return {
        "id": release.id,
        "version": release.version,
        "artifact_url": release.artifact_url,
        "artifact_sha256": release.artifact_sha256,
        "build_commit": release.build_commit,
        "status": release.status,
    }


def _record_node_release(
    *,
    session: Session,
    node_id: str,
    release: H5FrontendRelease,
    deployed_by: str,
) -> H5GatewayNodeRelease:
    previous = session.scalar(
        select(H5GatewayNodeRelease)
        .where(H5GatewayNodeRelease.node_id == node_id)
        .order_by(H5GatewayNodeRelease.created_at.desc())
    )
    node_release = H5GatewayNodeRelease(
        node_id=node_id,
        release_id=release.id,
        status="deploying",
        deployed_by=deployed_by,
        previous_release_id=previous.release_id if previous is not None else None,
    )
    session.add(node_release)
    session.flush()
    return node_release


@router.get("/nodes")
async def list_nodes(
    actor: RequestActor = Depends(require_permission("h5_gateway.view")),
    session: Session = Depends(get_db_session),
) -> dict[str, object]:
    service = _node_service(session)
    return {"items": [service.serialize_node(node) for node in service.list_nodes()]}


@router.post("/nodes", status_code=status.HTTP_201_CREATED)
async def create_node(
    payload: H5GatewayNodeCreateRequest,
    actor: RequestActor = Depends(require_permission("h5_gateway.manage")),
    session: Session = Depends(get_db_session),
) -> dict[str, object]:
    service = _node_service(session)
    node, credential = service.create_node(
        name=payload.name,
        node_code=payload.node_code,
        ssh_host=payload.ssh_host,
        ssh_port=payload.ssh_port,
        ssh_user=payload.ssh_user,
        created_by=actor.actor_id,
        ssh_secret=payload.ssh_secret,
        public_ip=payload.public_ip,
        private_ip=payload.private_ip,
        region=payload.region,
        agent_token=payload.agent_token,
    )
    session.commit()
    session.refresh(node)
    return service.serialize_node(node, credential_summary=credential)


@router.get("/releases")
async def list_releases(
    actor: RequestActor = Depends(require_permission("h5_gateway.view")),
    session: Session = Depends(get_db_session),
) -> dict[str, object]:
    items = session.scalars(select(H5FrontendRelease).order_by(H5FrontendRelease.created_at.desc())).all()
    return {"items": [_serialize_release(item) for item in items]}


@router.post("/releases", status_code=status.HTTP_201_CREATED)
async def create_release(
    payload: H5GatewayReleaseCreateRequest,
    actor: RequestActor = Depends(require_permission("h5_gateway.manage")),
    session: Session = Depends(get_db_session),
) -> dict[str, object]:
    existing = session.scalar(select(H5FrontendRelease).where(H5FrontendRelease.version == payload.version))
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"H5 frontend release version '{payload.version}' already exists.",
        )
    release = H5FrontendRelease(
        version=payload.version,
        artifact_url=payload.artifact_url,
        artifact_sha256=payload.artifact_sha256,
        build_commit=payload.build_commit,
        status="active",
    )
    session.add(release)
    session.commit()
    session.refresh(release)
    return _serialize_release(release)


@router.get("/nodes/{node_id}")
async def get_node(
    node_id: str,
    actor: RequestActor = Depends(require_permission("h5_gateway.view")),
    session: Session = Depends(get_db_session),
) -> dict[str, object]:
    service = _node_service(session)
    try:
        node = service.get_node(node_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return service.serialize_node(node)


@router.post("/nodes/{node_id}/test-ssh")
async def test_ssh(
    node_id: str,
    actor: RequestActor = Depends(require_permission("h5_gateway.manage")),
    session: Session = Depends(get_db_session),
) -> dict[str, object]:
    service = _node_service(session)
    try:
        node = service.get_node(node_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    result = H5GatewaySSHService(session).execute_whitelisted(node=node, command_name="test_ssh")
    return result


def _create_job_response(
    *,
    session: Session,
    node_id: str,
    job_type: str,
    actor_id: str,
    input_json: dict[str, Any] | None = None,
) -> dict[str, object]:
    job = H5GatewayJobService(session).create_job(
        node_id=node_id,
        job_type=job_type,
        requested_by=actor_id,
        input_json=input_json,
    )
    session.commit()
    return {
        "job": {
            "id": job.id,
            "job_type": job.job_type,
            "node_id": job.node_id,
            "status": job.status,
            "input_json": job.input_json or {},
        }
    }


@router.post("/nodes/{node_id}/bootstrap", status_code=status.HTTP_202_ACCEPTED)
async def bootstrap_node(
    node_id: str,
    actor: RequestActor = Depends(require_permission("h5_gateway.manage")),
    session: Session = Depends(get_db_session),
) -> dict[str, object]:
    return _create_job_response(session=session, node_id=node_id, job_type="bootstrap", actor_id=actor.actor_id)


@router.post("/nodes/{node_id}/health-check", status_code=status.HTTP_202_ACCEPTED)
async def health_check_node(
    node_id: str,
    actor: RequestActor = Depends(require_permission("h5_gateway.manage")),
    session: Session = Depends(get_db_session),
) -> dict[str, object]:
    return _create_job_response(session=session, node_id=node_id, job_type="health_check", actor_id=actor.actor_id)


@router.post("/nodes/{node_id}/security-hardening", status_code=status.HTTP_202_ACCEPTED)
async def security_hardening_node(
    node_id: str,
    actor: RequestActor = Depends(require_permission("h5_gateway.manage")),
    session: Session = Depends(get_db_session),
) -> dict[str, object]:
    return _create_job_response(
        session=session,
        node_id=node_id,
        job_type="security_hardening",
        actor_id=actor.actor_id,
    )


@router.post("/nodes/{node_id}/install-agent", status_code=status.HTTP_202_ACCEPTED)
async def install_agent_node(
    node_id: str,
    actor: RequestActor = Depends(require_permission("h5_gateway.manage")),
    session: Session = Depends(get_db_session),
) -> dict[str, object]:
    return _create_job_response(session=session, node_id=node_id, job_type="install_agent", actor_id=actor.actor_id)


@router.post("/nodes/{node_id}/reload-nginx", status_code=status.HTTP_202_ACCEPTED)
async def reload_nginx_node(
    node_id: str,
    actor: RequestActor = Depends(require_permission("h5_gateway.manage")),
    session: Session = Depends(get_db_session),
) -> dict[str, object]:
    return _create_job_response(session=session, node_id=node_id, job_type="reload_nginx", actor_id=actor.actor_id)


@router.post("/nodes/{node_id}/rollback", status_code=status.HTTP_202_ACCEPTED)
async def rollback_node(
    node_id: str,
    actor: RequestActor = Depends(require_permission("h5_gateway.manage")),
    session: Session = Depends(get_db_session),
) -> dict[str, object]:
    return _create_job_response(session=session, node_id=node_id, job_type="rollback", actor_id=actor.actor_id)


@router.post("/nodes/{node_id}/deploy-frontend", status_code=status.HTTP_202_ACCEPTED)
async def deploy_frontend_node(
    node_id: str,
    payload: H5GatewayDeployFrontendRequest,
    actor: RequestActor = Depends(require_permission("h5_gateway.manage")),
    session: Session = Depends(get_db_session),
) -> dict[str, object]:
    return _create_job_response(
        session=session,
        node_id=node_id,
        job_type="deploy_frontend",
        actor_id=actor.actor_id,
        input_json={
            "version": payload.version,
            "artifact_url": payload.artifact_url,
            "artifact_sha256": payload.artifact_sha256,
        },
    )


@router.post("/nodes/{node_id}/sync-config", status_code=status.HTTP_202_ACCEPTED)
async def sync_config_node(
    node_id: str,
    payload: H5GatewaySyncConfigRequest,
    actor: RequestActor = Depends(require_permission("h5_gateway.manage")),
    session: Session = Depends(get_db_session),
) -> dict[str, object]:
    return _create_job_response(
        session=session,
        node_id=node_id,
        job_type="sync_config",
        actor_id=actor.actor_id,
        input_json={
            "upstream_base_url": payload.upstream_base_url,
            "origin_verify_header": payload.origin_verify_header,
            "domains": [domain.model_dump() for domain in payload.domains],
        },
    )


@router.post("/releases/{release_id}/deploy-to-node", status_code=status.HTTP_202_ACCEPTED)
async def deploy_release_to_node(
    release_id: str,
    payload: H5GatewayReleaseDeployRequest,
    actor: RequestActor = Depends(require_permission("h5_gateway.manage")),
    session: Session = Depends(get_db_session),
) -> dict[str, object]:
    release = session.get(H5FrontendRelease, release_id)
    if release is None:
        raise HTTPException(status_code=404, detail=f"H5 frontend release '{release_id}' not found.")
    _record_node_release(session=session, node_id=payload.node_id, release=release, deployed_by=actor.actor_id)
    return _create_job_response(
        session=session,
        node_id=payload.node_id,
        job_type="deploy_frontend",
        actor_id=actor.actor_id,
        input_json={
            "release_id": release.id,
            "version": release.version,
            "artifact_url": release.artifact_url,
            "artifact_sha256": release.artifact_sha256,
            "build_commit": release.build_commit,
        },
    )


@router.post("/releases/{release_id}/deploy-to-all", status_code=status.HTTP_202_ACCEPTED)
async def deploy_release_to_all(
    release_id: str,
    actor: RequestActor = Depends(require_permission("h5_gateway.manage")),
    session: Session = Depends(get_db_session),
) -> dict[str, object]:
    release = session.get(H5FrontendRelease, release_id)
    if release is None:
        raise HTTPException(status_code=404, detail=f"H5 frontend release '{release_id}' not found.")

    nodes = session.scalars(
        select(H5GatewayNode).where(H5GatewayNode.status == "active").order_by(H5GatewayNode.created_at.asc())
    ).all()
    jobs: list[dict[str, object]] = []
    job_service = H5GatewayJobService(session)
    for node in nodes:
        _record_node_release(session=session, node_id=node.id, release=release, deployed_by=actor.actor_id)
        job = job_service.create_job(
            node_id=node.id,
            job_type="deploy_frontend",
            requested_by=actor.actor_id,
            input_json={
                "release_id": release.id,
                "version": release.version,
                "artifact_url": release.artifact_url,
                "artifact_sha256": release.artifact_sha256,
                "build_commit": release.build_commit,
            },
        )
        jobs.append(
            {
                "id": job.id,
                "job_type": job.job_type,
                "node_id": job.node_id,
                "status": job.status,
                "input_json": job.input_json or {},
            }
        )
    session.commit()
    return {"job_count": len(jobs), "jobs": jobs}
