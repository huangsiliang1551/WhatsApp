"""归属 / AI 接待 / 入口链接 API 路由（spec 第 10 节）。

所有接口接入 ``require_permission`` strict 权限依赖（spec 2.3 / 11）。
权限边界：普通客服只能看自己范围内数据；代理商管理员管理本代理商；平台管理员全局。
路由按业务域分多个 APIRouter，由 main.py 统一 include。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import (
    RequestActor,
    get_db_session,
    get_transactional_db_session,
    require_permission,
)
from app.db.models import utc_now
from app.db.ownership_models import (
    AIAgent,
    ConversationAIAssignment,
    EntryLink,
    MemberAIAssignment,
    MemberOwnerAssignment,
    OwnershipAuditEvent,
)
from app.services.ai_agent_service import AIAgentNotFoundError, AIAgentService
from app.services.conversation_ai_assignment_service import (
    AIFailoverService,
    ConversationAIAssignmentService,
)
from app.services.entry_link_service import (
    EntryLinkNotFoundError,
    EntryLinkService,
    EntryLinkUnavailableError,
)
from app.services.member_ownership_service import (
    AttributionError,
    MemberAIOwnershipService,
    MemberOwnershipService,
    TransferUnauthorizedError,
)
from app.services.ownership_report_service import OwnershipReportService
from app.services.ownership_snapshot_service import OwnershipSnapshotService


# ──────────────────────────────────────────────────────────────────────────────
# Schemas
# ──────────────────────────────────────────────────────────────────────────────
class EntryLinkCreate(BaseModel):
    link_type: str = Field(min_length=1, max_length=32)
    channel: str = Field(default="h5", max_length=32)
    target_type: str = Field(min_length=1, max_length=32)
    target_staff_user_id: str | None = None
    target_agency_member_id: str | None = None
    target_ai_agent_id: str | None = None
    site_id: str | None = None
    waba_id: str | None = None
    phone_number_id: str | None = None
    whatsapp_phone_number: str | None = None
    usage_limit: int | None = None
    expires_at: Any | None = None


class EntryLinkPatch(BaseModel):
    status: str | None = None
    usage_limit: int | None = None
    expires_at: Any | None = None


class AIAgentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    display_name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    agency_id: str | None = None
    site_id: str | None = None
    provider_name: str = "openai"
    model_name: str = "gpt-4o-mini"
    prompt_version: str | None = None
    system_prompt: str | None = None
    waba_id: str | None = None
    phone_number_id: str | None = None
    owning_staff_user_id: str | None = None
    owning_agency_member_id: str | None = None
    fallback_staff_user_id: str | None = None
    fallback_agency_member_id: str | None = None
    fallback_ai_agent_id: str | None = None
    auto_reply_enabled: bool = True
    proactive_send_enabled: bool = False


class AIAgentPatch(BaseModel):
    name: str | None = None
    display_name: str | None = None
    description: str | None = None
    system_prompt: str | None = None
    owning_staff_user_id: str | None = None
    fallback_staff_user_id: str | None = None
    fallback_ai_agent_id: str | None = None
    auto_reply_enabled: bool | None = None
    proactive_send_enabled: bool | None = None


class TransferRequest(BaseModel):
    from_staff_user_id: str | None = None
    to_staff_user_id: str | None = None
    from_ai_agent_id: str | None = None
    to_ai_agent_id: str | None = None
    member_profile_ids: list[str] = Field(default_factory=list)
    transfer_all_current_owned_members: bool = False
    include_open_conversations: bool = True
    dry_run: bool = False
    reason: str | None = None
    site_id: str | None = None


class ConversationAISwitch(BaseModel):
    to_ai_agent_id: str
    reason: str | None = None


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────
def _entry_link_to_dict(link: EntryLink, svc: EntryLinkService) -> dict[str, Any]:
    urls = svc.build_urls(link)
    return {
        "id": link.id,
        "code": link.code,
        "link_type": link.link_type,
        "channel": link.channel,
        "status": link.status,
        "target_type": link.target_type,
        "target_staff_user_id": link.target_staff_user_id,
        "target_agency_member_id": link.target_agency_member_id,
        "target_ai_agent_id": link.target_ai_agent_id,
        "site_id": link.site_id,
        "waba_id": link.waba_id,
        "phone_number_id": link.phone_number_id,
        "whatsapp_phone_number": link.whatsapp_phone_number,
        "usage_count": link.usage_count,
        "usage_limit": link.usage_limit,
        "expires_at": link.expires_at,
        "last_used_at": link.last_used_at,
        "h5_register_url": urls["h5_register_url"],
        "whatsapp_chat_url": urls["whatsapp_chat_url"],
        "qr_payload": urls["qr_payload"],
        "created_at": link.created_at,
    }


def _ai_agent_to_dict(agent: AIAgent) -> dict[str, Any]:
    return {
        "id": agent.id,
        "account_id": agent.account_id,
        "agency_id": agent.agency_id,
        "site_id": agent.site_id,
        "name": agent.name,
        "display_name": agent.display_name,
        "description": agent.description,
        "status": agent.status,
        "provider_name": agent.provider_name,
        "model_name": agent.model_name,
        "prompt_version": agent.prompt_version,
        "waba_id": agent.waba_id,
        "phone_number_id": agent.phone_number_id,
        "owning_staff_user_id": agent.owning_staff_user_id,
        "fallback_staff_user_id": agent.fallback_staff_user_id,
        "fallback_ai_agent_id": agent.fallback_ai_agent_id,
        "auto_reply_enabled": agent.auto_reply_enabled,
        "proactive_send_enabled": agent.proactive_send_enabled,
        "health_status": agent.health_status,
        "last_health_check_at": agent.last_health_check_at,
        "created_at": agent.created_at,
    }


# ──────────────────────────────────────────────────────────────────────────────
# EntryLink routes
# ──────────────────────────────────────────────────────────────────────────────
entry_links_router = APIRouter(prefix="/api/entry-links", tags=["entry-links"])


@entry_links_router.get("")
async def list_entry_links(
    site_id: str | None = None,
    link_type: str | None = None,
    target_type: str | None = None,
    target_staff_user_id: str | None = None,
    target_ai_agent_id: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("entry_links.view")),
) -> list[dict[str, Any]]:
    svc = EntryLinkService(session)
    links = svc.list_links(
        account_id=None if actor.is_super_admin else (actor.account_ids[0] if actor.account_ids else None),
        site_id=site_id,
        link_type=link_type,
        target_type=target_type,
        target_staff_user_id=target_staff_user_id,
        target_ai_agent_id=target_ai_agent_id,
        status=status_filter,
    )
    return [_entry_link_to_dict(l, svc) for l in links]


@entry_links_router.post("", status_code=201)
async def create_entry_link(
    payload: EntryLinkCreate,
    session: Session = Depends(get_transactional_db_session),
    actor: RequestActor = Depends(require_permission("entry_links.manage")),
) -> dict[str, Any]:
    account_id = actor.account_ids[0] if actor.account_ids else "default-account"
    svc = EntryLinkService(session)
    link = svc.create_staff_register_link(
        account_id=account_id, site_id=payload.site_id, staff_user_id=payload.target_staff_user_id or "staff",
    ) if payload.target_type == "staff" else svc.create_ai_register_link(
        account_id=account_id, site_id=payload.site_id, ai_agent_id=payload.target_ai_agent_id or "",
        waba_id=payload.waba_id, phone_number_id=payload.phone_number_id,
        whatsapp_phone_number=payload.whatsapp_phone_number,
    )
    session.commit()
    return _entry_link_to_dict(link, svc)


@entry_links_router.get("/{link_id}")
async def get_entry_link(
    link_id: str,
    session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("entry_links.view")),
) -> dict[str, Any]:
    svc = EntryLinkService(session)
    try:
        link = svc._require(link_id)
    except EntryLinkNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _entry_link_to_dict(link, svc)


@entry_links_router.post("/{link_id}/revoke")
async def revoke_entry_link(
    link_id: str,
    session: Session = Depends(get_transactional_db_session),
    actor: RequestActor = Depends(require_permission("entry_links.manage")),
) -> dict[str, Any]:
    svc = EntryLinkService(session)
    try:
        link = svc.revoke(link_id, actor_id=actor.actor_id, reason=None)
    except EntryLinkNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    session.commit()
    return _entry_link_to_dict(link, svc)


@entry_links_router.post("/{link_id}/rotate")
async def rotate_entry_link(
    link_id: str,
    session: Session = Depends(get_transactional_db_session),
    actor: RequestActor = Depends(require_permission("entry_links.manage")),
) -> dict[str, Any]:
    svc = EntryLinkService(session)
    try:
        link = svc.rotate(link_id, actor_id=actor.actor_id, reason=None)
    except EntryLinkNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    session.commit()
    return _entry_link_to_dict(link, svc)


@entry_links_router.get("/{link_id}/stats")
async def entry_link_stats(
    link_id: str,
    session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("entry_links.view")),
) -> dict[str, Any]:
    svc = EntryLinkService(session)
    try:
        link = svc._require(link_id)
    except EntryLinkNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "id": link.id,
        "code": link.code,
        "usage_count": link.usage_count,
        "usage_limit": link.usage_limit,
        "status": link.status,
        "last_used_at": link.last_used_at,
    }


# ──────────────────────────────────────────────────────────────────────────────
# AI Agent routes
# ──────────────────────────────────────────────────────────────────────────────
ai_agents_router = APIRouter(prefix="/api/ai-agents", tags=["ai-agents"])


@ai_agents_router.get("")
async def list_ai_agents(
    site_id: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("ai_agents.view")),
) -> list[dict[str, Any]]:
    svc = AIAgentService(session)
    account_id = None if actor.is_super_admin else (actor.account_ids[0] if actor.account_ids else None)
    agents = svc.list_ai_agents(account_id=account_id, site_id=site_id, status=status_filter)
    return [_ai_agent_to_dict(a) for a in agents]


@ai_agents_router.post("", status_code=201)
async def create_ai_agent(
    payload: AIAgentCreate,
    session: Session = Depends(get_transactional_db_session),
    actor: RequestActor = Depends(require_permission("ai_agents.manage")),
) -> dict[str, Any]:
    account_id = actor.account_ids[0] if actor.account_ids else "default-account"
    svc = AIAgentService(session)
    agent = svc.create_ai_agent(
        account_id=account_id, name=payload.name, display_name=payload.display_name,
        description=payload.description, agency_id=payload.agency_id, site_id=payload.site_id,
        provider_name=payload.provider_name, model_name=payload.model_name,
        prompt_version=payload.prompt_version, system_prompt=payload.system_prompt,
        waba_id=payload.waba_id, phone_number_id=payload.phone_number_id,
        owning_staff_user_id=payload.owning_staff_user_id,
        owning_agency_member_id=payload.owning_agency_member_id,
        fallback_staff_user_id=payload.fallback_staff_user_id,
        fallback_agency_member_id=payload.fallback_agency_member_id,
        fallback_ai_agent_id=payload.fallback_ai_agent_id,
        auto_reply_enabled=payload.auto_reply_enabled,
        proactive_send_enabled=payload.proactive_send_enabled,
        actor_id=actor.actor_id,
    )
    session.commit()
    return _ai_agent_to_dict(agent)


@ai_agents_router.get("/{agent_id}")
async def get_ai_agent(
    agent_id: str,
    session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("ai_agents.view")),
) -> dict[str, Any]:
    svc = AIAgentService(session)
    try:
        return _ai_agent_to_dict(svc.require(agent_id))
    except AIAgentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@ai_agents_router.patch("/{agent_id}")
async def update_ai_agent(
    agent_id: str,
    payload: AIAgentPatch,
    session: Session = Depends(get_transactional_db_session),
    actor: RequestActor = Depends(require_permission("ai_agents.manage")),
) -> dict[str, Any]:
    svc = AIAgentService(session)
    try:
        agent = svc.update_ai_agent(agent_id, actor_id=actor.actor_id, **payload.model_dump(exclude_unset=True))
    except AIAgentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    session.commit()
    return _ai_agent_to_dict(agent)


@ai_agents_router.post("/{agent_id}/disable")
async def disable_ai_agent(
    agent_id: str,
    session: Session = Depends(get_transactional_db_session),
    actor: RequestActor = Depends(require_permission("ai_agents.disable")),
) -> dict[str, Any]:
    svc = AIAgentService(session)
    try:
        agent = svc.disable_ai_agent(agent_id, actor_id=actor.actor_id)
    except AIAgentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    session.commit()
    return _ai_agent_to_dict(agent)


@ai_agents_router.post("/{agent_id}/archive")
async def archive_ai_agent(
    agent_id: str,
    session: Session = Depends(get_transactional_db_session),
    actor: RequestActor = Depends(require_permission("ai_agents.disable")),
) -> dict[str, Any]:
    svc = AIAgentService(session)
    try:
        agent = svc.archive_ai_agent(agent_id, actor_id=actor.actor_id)
    except AIAgentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    session.commit()
    return _ai_agent_to_dict(agent)


@ai_agents_router.post("/{agent_id}/health-check")
async def health_check_ai_agent(
    agent_id: str,
    session: Session = Depends(get_transactional_db_session),
    actor: RequestActor = Depends(require_permission("ai_agents.manage")),
) -> dict[str, Any]:
    svc = AIAgentService(session)
    try:
        agent = svc.health_check(agent_id)
    except AIAgentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    session.commit()
    return _ai_agent_to_dict(agent)


@ai_agents_router.get("/{agent_id}/entry-links")
async def list_ai_agent_entry_links(
    agent_id: str,
    session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("entry_links.view")),
) -> list[dict[str, Any]]:
    svc = EntryLinkService(session)
    links = svc.list_links(target_ai_agent_id=agent_id)
    return [_entry_link_to_dict(l, svc) for l in links]


# ──────────────────────────────────────────────────────────────────────────────
# Member ownership routes
# ──────────────────────────────────────────────────────────────────────────────
member_ownership_router = APIRouter(prefix="/api/member-ownership", tags=["member-ownership"])


@member_ownership_router.post("/transfers")
async def transfer_members(
    payload: TransferRequest,
    session: Session = Depends(get_transactional_db_session),
    actor: RequestActor = Depends(require_permission("member_ownership.transfer")),
) -> dict[str, Any]:
    if not payload.from_staff_user_id or not payload.to_staff_user_id:
        raise HTTPException(status_code=400, detail="from_staff_user_id and to_staff_user_id are required.")
    account_id = actor.account_ids[0] if actor.account_ids else "default-account"
    svc = MemberOwnershipService(session)
    try:
        result = svc.transfer_members(
            account_id=account_id,
            from_staff_user_id=payload.from_staff_user_id,
            to_staff_user_id=payload.to_staff_user_id,
            member_profile_ids=payload.member_profile_ids,
            actor_id=actor.actor_id,
            site_id=payload.site_id,
            transfer_all_current_owned_members=payload.transfer_all_current_owned_members,
            dry_run=payload.dry_run,
            reason=payload.reason,
        )
    except TransferUnauthorizedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    session.commit()
    return result


# ──────────────────────────────────────────────────────────────────────────────
# Member AI ownership routes
# ──────────────────────────────────────────────────────────────────────────────
member_ai_ownership_router = APIRouter(prefix="/api/member-ai-ownership", tags=["member-ai-ownership"])


@member_ai_ownership_router.post("/transfers")
async def transfer_member_ai(
    payload: TransferRequest,
    session: Session = Depends(get_transactional_db_session),
    actor: RequestActor = Depends(require_permission("member_ai_ownership.transfer")),
) -> dict[str, Any]:
    if not payload.from_ai_agent_id or not payload.to_ai_agent_id:
        raise HTTPException(status_code=400, detail="from_ai_agent_id and to_ai_agent_id are required.")
    account_id = actor.account_ids[0] if actor.account_ids else "default-account"
    svc = MemberAIOwnershipService(session)
    try:
        result = svc.transfer_member_ai(
            account_id=account_id,
            from_ai_agent_id=payload.from_ai_agent_id,
            to_ai_agent_id=payload.to_ai_agent_id,
            member_profile_ids=payload.member_profile_ids,
            actor_id=actor.actor_id,
            include_open_conversations=payload.include_open_conversations,
            dry_run=payload.dry_run,
            reason=payload.reason,
        )
    except TransferUnauthorizedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    session.commit()
    return result


@member_ai_ownership_router.post("/failover/run")
async def run_ai_failover_migration(
    payload: TransferRequest,
    session: Session = Depends(get_transactional_db_session),
    actor: RequestActor = Depends(require_permission("member_ai_ownership.failover")),
) -> dict[str, Any]:
    if not payload.from_ai_agent_id or not payload.to_ai_agent_id:
        raise HTTPException(status_code=400, detail="from_ai_agent_id and to_ai_agent_id are required.")
    account_id = actor.account_ids[0] if actor.account_ids else "default-account"
    svc = AIFailoverService(session)
    affected = svc.permanent_migration(
        account_id=account_id,
        from_ai_agent_id=payload.from_ai_agent_id,
        to_ai_agent_id=payload.to_ai_agent_id,
        actor_id=actor.actor_id,
        reason=payload.reason,
    )
    session.commit()
    return {"affected_count": affected, "from_ai_agent_id": payload.from_ai_agent_id, "to_ai_agent_id": payload.to_ai_agent_id}


# ──────────────────────────────────────────────────────────────────────────────
# Conversation AI routes
# ──────────────────────────────────────────────────────────────────────────────
conversation_ai_router = APIRouter(prefix="/api/conversations", tags=["conversation-ai"])


@conversation_ai_router.get("/{conversation_id}/ai-assignment")
async def get_conversation_ai_assignment(
    conversation_id: str,
    account_id: str = Query(...),
    session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("conversations.ai.view")),
) -> dict[str, Any]:
    actor.require_account_access(account_id)
    svc = ConversationAIAssignmentService(session)
    assignment = svc.get_current(account_id=account_id, conversation_id=conversation_id)
    if assignment is None:
        raise HTTPException(status_code=404, detail="No current AI assignment for this conversation.")
    return {
        "id": assignment.id,
        "conversation_id": assignment.conversation_id,
        "bound_ai_agent_id": assignment.bound_ai_agent_id,
        "actual_ai_agent_id": assignment.actual_ai_agent_id,
        "source_type": assignment.source_type,
        "failover_from_ai_agent_id": assignment.failover_from_ai_agent_id,
        "failover_reason": assignment.failover_reason,
        "is_current": assignment.is_current,
        "assigned_at": assignment.assigned_at,
    }


@conversation_ai_router.post("/{conversation_id}/ai-assignment/switch")
async def switch_conversation_ai(
    conversation_id: str,
    payload: ConversationAISwitch,
    account_id: str = Query(...),
    session: Session = Depends(get_transactional_db_session),
    actor: RequestActor = Depends(require_permission("conversations.ai.switch")),
) -> dict[str, Any]:
    actor.require_account_access(account_id)
    svc = ConversationAIAssignmentService(session)
    try:
        assignment = svc.switch_conversation_ai(
            account_id=account_id, conversation_id=conversation_id,
            to_ai_agent_id=payload.to_ai_agent_id, actor_id=actor.actor_id, reason=payload.reason,
        )
    except AIAgentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    session.commit()
    return {"assignment_id": assignment.id, "actual_ai_agent_id": assignment.actual_ai_agent_id}


# ──────────────────────────────────────────────────────────────────────────────
# Ownership audit routes
# ──────────────────────────────────────────────────────────────────────────────
ownership_audit_router = APIRouter(prefix="/api/ownership-audit", tags=["ownership-audit"])


@ownership_audit_router.get("/events")
async def list_ownership_audit_events(
    target_type: str | None = None,
    target_id: str | None = None,
    action: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("member_ownership.history")),
) -> list[dict[str, Any]]:
    from sqlalchemy import select

    stmt = select(OwnershipAuditEvent).order_by(OwnershipAuditEvent.created_at.desc()).limit(limit)
    if target_type:
        stmt = stmt.where(OwnershipAuditEvent.target_type == target_type)
    if target_id:
        stmt = stmt.where(OwnershipAuditEvent.target_id == target_id)
    if action:
        stmt = stmt.where(OwnershipAuditEvent.action == action)
    events = list(session.scalars(stmt).all())
    return [
        {
            "id": e.id,
            "action": e.action,
            "target_type": e.target_type,
            "target_id": e.target_id,
            "actor_type": e.actor_type,
            "actor_id": e.actor_id,
            "payload": e.payload,
            "created_at": e.created_at,
        }
        for e in events
    ]


@ownership_audit_router.get("/member/{member_profile_id}")
async def audit_for_member(
    member_profile_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("member_ownership.history")),
) -> list[dict[str, Any]]:
    from sqlalchemy import select

    stmt = (
        select(OwnershipAuditEvent)
        .where(OwnershipAuditEvent.target_id == member_profile_id)
        .order_by(OwnershipAuditEvent.created_at.desc())
        .limit(limit)
    )
    return [
        {
            "id": e.id, "action": e.action, "target_type": e.target_type,
            "target_id": e.target_id, "actor_id": e.actor_id, "payload": e.payload,
            "created_at": e.created_at,
        }
        for e in session.scalars(stmt).all()
    ]


# ──────────────────────────────────────────────────────────────────────────────
# Ownership reports routes
# ──────────────────────────────────────────────────────────────────────────────
ownership_report_router = APIRouter(prefix="/api/reports/ownership", tags=["ownership-reports"])


@ownership_report_router.get("")
async def get_ownership_report(
    account_id: str | None = Query(default=None, alias="account_id"),
    session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("reports.ownership.view")),
) -> dict[str, Any]:
    if not actor.is_super_admin and account_id is None:
        account_id = actor.account_ids[0] if actor.account_ids else None
    svc = OwnershipReportService(session)
    return svc.ownership_report(account_id=account_id)
