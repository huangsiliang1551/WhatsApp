from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.core.settings import get_settings
from app.services.h5_gateway_agent_service import H5GatewayAgentAuthError, H5GatewayAgentService

router = APIRouter(prefix="/api/h5-gateway/agent", tags=["h5-gateway-agent"])


class H5GatewayStepRequest(BaseModel):
    step_name: str
    command_name: str | None = None
    status: str
    stdout_tail: str | None = None
    stderr_tail: str | None = None
    result_json: dict[str, object] | None = None
    exit_code: int | None = None


class H5GatewayFinishRequest(BaseModel):
    status: str
    result_json: dict[str, object] | None = None
    failure_code: str | None = None
    failure_message: str | None = None


class H5GatewayHeartbeatRequest(BaseModel):
    node_code: str
    agent_version: str | None = None
    nginx_status: str | None = None
    frontend_version: str | None = None
    config_version: int | None = None
    blocked_domain_count: int | None = None
    cpu: float | None = None
    memory: float | None = None
    disk: float | None = None
    load: str | None = None


def _get_bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid H5 gateway agent token.")
    return authorization[7:]


def _get_service(session: Session) -> H5GatewayAgentService:
    return H5GatewayAgentService(session, shared_secret=get_settings().h5_gateway_agent_shared_secret)


@router.get("/jobs/poll")
async def poll_job(
    node_code: str,
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_db_session),
) -> dict | None:
    service = _get_service(session)
    try:
        return service.poll_job(node_code=node_code, bearer_token=_get_bearer_token(authorization))
    except H5GatewayAgentAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.post("/jobs/{job_id}/start")
async def start_job(
    job_id: str,
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_db_session),
) -> dict[str, object]:
    service = _get_service(session)
    try:
        job = service.start_job(job_id, bearer_token=_get_bearer_token(authorization))
    except H5GatewayAgentAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    session.commit()
    return {"job_id": job.id, "status": job.status}


@router.post("/jobs/{job_id}/step")
async def append_job_step(
    job_id: str,
    payload: H5GatewayStepRequest,
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_db_session),
) -> dict[str, object]:
    service = _get_service(session)
    try:
        step = service.append_job_step(job_id, bearer_token=_get_bearer_token(authorization), **payload.model_dump())
    except H5GatewayAgentAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    session.commit()
    return {"step_id": step.id, "status": step.status}


@router.post("/jobs/{job_id}/finish")
async def finish_job(
    job_id: str,
    payload: H5GatewayFinishRequest,
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_db_session),
) -> dict[str, object]:
    service = _get_service(session)
    try:
        job = service.finish_job(job_id, bearer_token=_get_bearer_token(authorization), **payload.model_dump())
    except H5GatewayAgentAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    session.commit()
    return {"job_id": job.id, "status": job.status}


@router.post("/heartbeat")
async def heartbeat(
    payload: H5GatewayHeartbeatRequest,
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_db_session),
) -> dict[str, object]:
    service = _get_service(session)
    try:
        node = service.record_heartbeat(
            node_code=payload.node_code,
            bearer_token=_get_bearer_token(authorization),
            payload=payload.model_dump(),
        )
    except H5GatewayAgentAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    session.commit()
    return {"ok": True, "node_id": node.id, "agent_status": node.agent_status}
