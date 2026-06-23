"""Agent presence and online status management routes."""

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import (
    get_runtime_state_service,
    require_permission,
)
from app.core.auth import RequestActor
from app.schemas.handover import AgentPresenceRecordSchema, AgentStatusUpdateRequest
from app.services.handover_service import HandoverService
from app.services.runtime_state import RuntimeStateStore

router = APIRouter(prefix="/api/agents", tags=["agents"])


def _make_handover_service(
    runtime_state: RuntimeStateStore,
) -> HandoverService:
    return HandoverService(runtime_state)


@router.post(
    "/presence/online",
    summary="Agent online",
    description="Mark an agent as online in Redis presence store.",
    tags=["agents"],
)
async def agent_online(
    agent_id: str,
    account_id: str | None = None,
    runtime_state_store: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("members.manage")),
) -> AgentPresenceRecordSchema:
    """Mark an agent as online (Redis presence)."""
    actor.require_account_access(account_id)
    handover_service = HandoverService(runtime_state_store)
    try:
        await handover_service.set_agent_status(
            account_id=account_id,
            agent_id=agent_id,
            status="online",
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
        )
        record = await handover_service.list_online_agents(account_id=account_id)
        for r in record:
            if r.agent_id == agent_id:
                return r
        return AgentPresenceRecordSchema(
            account_id=account_id,
            agent_id=agent_id,
            status="online",
            last_heartbeat=__import__("time").time(),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/presence/offline",
    summary="Agent offline",
    description="Mark an agent as offline, removing from Redis presence store.",
    tags=["agents"],
)
async def agent_offline(
    agent_id: str,
    account_id: str | None = None,
    runtime_state_store: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("members.manage")),
) -> dict[str, object]:
    """Mark an agent as offline (removes Redis presence)."""
    actor.require_account_access(account_id)
    handover_service = HandoverService(runtime_state_store)
    try:
        await handover_service.set_agent_status(
            account_id=account_id,
            agent_id=agent_id,
            status="offline",
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
        )
        return {"agent_id": agent_id, "account_id": account_id, "status": "offline"}
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/presence",
    summary="List agent presence",
    description="List online agents from Redis presence store.",
    tags=["agents"],
)
async def list_presence(
    account_id: str | None = None,
    runtime_state_store: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("members.status")),
) -> list[AgentPresenceRecordSchema]:
    """List online agents (Redis presence)."""
    if account_id is not None:
        actor.require_account_access(account_id)
    handover_service = HandoverService(runtime_state_store)
    return await handover_service.list_online_agents(account_id=account_id)


@router.post(
    "/presence/heartbeat",
    summary="Agent heartbeat",
    description="Send heartbeat to keep agent presence alive.",
    tags=["agents"],
)
async def agent_heartbeat(
    agent_id: str,
    account_id: str | None = None,
    runtime_state_store: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("members.manage")),
) -> AgentPresenceRecordSchema | dict[str, object]:
    """Send heartbeat to keep presence alive."""
    actor.require_account_access(account_id)
    handover_service = HandoverService(runtime_state_store)
    record = await handover_service.presence_heartbeat(agent_id, account_id)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail=f"Agent '{agent_id}' has no active presence session.",
        )
    return record


@router.post(
    "/{agent_id}/status",
    summary="Update agent status",
    description="Update agent status in DB and sync with Redis presence.",
    tags=["agents"],
)
async def update_agent_status(
    agent_id: str,
    payload: AgentStatusUpdateRequest,
    account_id: str | None = None,
    runtime_state_store: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("members.manage")),
) -> dict[str, object]:
    """Update agent status (DB + Redis presence sync)."""
    actor.require_account_access(account_id)
    handover_service = HandoverService(runtime_state_store)
    try:
        result = await handover_service.set_agent_status(
            account_id=account_id,
            agent_id=agent_id,
            status=payload.status,
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
        )
        return result.model_dump()
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
