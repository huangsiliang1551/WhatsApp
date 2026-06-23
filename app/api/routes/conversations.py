from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Any, cast

from app.api.deps import (
    get_conversation_service,
    get_db_session,
    get_media_asset_service,
    get_runtime_state_service,
    require_permission,
)
from app.core.auth import ActorRole, RequestActor, filter_account_scoped_items
from app.schemas.conversations import ForwardMessageRequest, OutboundMessageRequest
from app.schemas.handover import ConversationAssignmentRequest, ConversationCloseRequest
from app.schemas.media_assets import MediaAssetSendRequest, MediaAssetSendResponse
from app.services.conversation_service import ConversationService
from app.services.handover_service import HandoverService
from app.services.media_asset_service import MediaAssetService
from app.services.media_asset_errors import MediaProviderConfigError, MediaProviderUpstreamError
from app.services.runtime_state import RuntimeStateStore
from app.db.models import Conversation

class BatchConversationRequest(BaseModel):
    conversation_ids: list[str]
    reason: str | None = None


class BatchAssignRequest(BatchConversationRequest):
    agent_id: str


class BatchOperationResult(BaseModel):
    conversation_id: str
    status: str  # "success" or "failed"
    error: str | None = None


class BatchOperationResponse(BaseModel):
    success_count: int
    failed_count: int
    results: list[BatchOperationResult]


router = APIRouter(prefix="/api/conversations", tags=["conversations"])



def _raise_outbound_route_value_error(exc: ValueError) -> None:
    detail = str(exc)
    if ("access_token" in detail and "requires" in detail) or "access token" in detail.lower():
        raise HTTPException(status_code=503, detail=detail) from exc
    raise HTTPException(status_code=409, detail=detail) from exc


@router.get(
    "",
    summary="List conversations",
    description="List conversations with optional filters for account, WABA, agent, status, and intent.",
    tags=["conversations"],
)
async def list_conversations(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    sort: str | None = Query(default="-last_message_at"),
    search: str | None = None,
    account_id: str | None = None,
    waba_id: str | None = None,
    phone_number_id: str | None = None,
    assigned_agent_id: str | None = None,
    status: str | None = None,
    management_mode: str | None = None,
    latest_intent_name: str | None = None,
    latest_handover_recommended: bool | None = None,
    tag: str | None = Query(default=None),
    is_sleeping: bool | None = Query(default=None),
    conversation_service: ConversationService = Depends(get_conversation_service),
    actor: RequestActor = Depends(require_permission("conversations.view")),
) -> dict:
    if account_id is not None:
        actor.require_account_access(account_id)
    # 代理隔离：support_agent 只能看到分配给自己或被转接给自己的会话
    resolved_assigned_agent_id = assigned_agent_id
    if actor.role == ActorRole.SUPPORT_AGENT and resolved_assigned_agent_id is None:
        resolved_assigned_agent_id = actor.actor_id
    try:
        summaries, total = await conversation_service.list_conversations(
            account_id=account_id,
            waba_id=waba_id,
            phone_number_id=phone_number_id,
            assigned_agent_id=resolved_assigned_agent_id,
            status=status,
            management_mode=management_mode,
            latest_intent_name=latest_intent_name,
            latest_handover_recommended=latest_handover_recommended,
            tag=tag,
            is_sleeping=is_sleeping,
            allowed_account_ids=None if actor.is_super_admin else set(actor.account_ids),
            sort_by=sort.lstrip("-") if sort else None,
            sort_desc=sort.startswith("-") if sort else True,
            page=page,
            size=size,
        )
        # 代理已通过 assigned_agent_id 隔离，不再需要 account scope 过滤
        if actor.is_super_admin or (actor.role == ActorRole.SUPPORT_AGENT and resolved_assigned_agent_id):
            items = [summary.model_dump() for summary in summaries]
        else:
            items = [
                summary.model_dump()
                for summary in filter_account_scoped_items(
                    actor,
                    summaries,
                    lambda item: item.account_id,
                )
            ]
        # Client-side search filter (text search across customer_id and conversation_id)
        if search:
            search_lower = search.lower()
            items = [
                item for item in items
                if search_lower in (item.get("customer_id") or "").lower()
                or search_lower in (item.get("conversation_id") or "").lower()
            ]
        return {"items": items, "total": total, "page": page, "size": size}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/assigned",
    summary="List assigned conversations",
    description="List conversations assigned to a specific agent with status and management mode filters.",
    tags=["conversations"],
)
async def list_assigned_conversations(
    account_id: str | None = None,
    agent_id: str | None = None,
    status: str | None = "open",
    management_mode: str | None = None,
    conversation_service: ConversationService = Depends(get_conversation_service),
    actor: RequestActor = Depends(require_permission("conversations.view")),
) -> list[dict[str, object]]:
    if account_id is not None:
        actor.require_account_access(account_id)
    resolved_agent_id = actor.resolve_agent_id(agent_id)
    return [
        conversation.model_dump()
        for conversation in filter_account_scoped_items(
            actor,
            await conversation_service.list_conversations(
                account_id=account_id,
                assigned_agent_id=resolved_agent_id,
                status=status,
                management_mode=management_mode,
            ),
            lambda item: item.account_id,
        )
    ]


@router.get(
    "/{account_id}/{conversation_id}/messages",
    summary="List conversation messages",
    description="List messages for a conversation with optional translation inclusion.",
    tags=["conversations"],
)
async def list_messages(
    account_id: str,
    conversation_id: str,
    include_translations: bool = False,
    include_cold: bool = Query(default=False),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=30, ge=1, le=200),
    conversation_service: ConversationService = Depends(get_conversation_service),
    actor: RequestActor = Depends(require_permission("conversations.detail")),
) -> list[dict[str, object]]:
    actor.require_account_access(account_id)
    try:
        return [
            message.model_dump()
            for message in await conversation_service.list_messages_with_options(
                account_id=account_id,
                conversation_id=conversation_id,
                include_translations=include_translations,
                include_cold=include_cold,
                offset=offset,
                limit=limit,
            )
        ]
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/{account_id}/{conversation_id}/wake",
    summary="Wake a sleeping conversation",
    description="Wake up a sleeping conversation, restoring it to active state and re-heating cold messages.",
    tags=["conversations"],
)
async def wake_conversation(
    account_id: str,
    conversation_id: str,
    conversation_service: ConversationService = Depends(get_conversation_service),
    actor: RequestActor = Depends(require_permission("conversations.wake")),
) -> dict:
    actor.require_account_access(account_id)
    try:
        summary = await conversation_service.wake_conversation(
            account_id=account_id,
            conversation_id=conversation_id,
            actor_type=actor.actor_type if actor else "admin",
            actor_id=actor.actor_id if actor else None,
        )
        return summary.model_dump()
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/stats",
    summary="Get conversation statistics",
    description="Return counts of active, sleeping, and closed conversations.",
    tags=["conversations"],
)
async def get_conversation_stats(
    account_id: str | None = None,
    db_session=Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("conversations.view")),
) -> dict:
    from sqlalchemy import func, select
    base = select(func.count()).select_from(Conversation)
    if account_id is not None:
        actor.require_account_access(account_id)
        base = base.where(Conversation.account_id == account_id)
    else:
        if not actor.is_super_admin and actor.account_ids:
            base = base.where(Conversation.account_id.in_(actor.account_ids))

    def _count(**filters) -> int:
        q = base
        for k, v in filters.items():
            col = getattr(Conversation, k)
            q = q.where(col.is_(v))
        return db_session.scalar(q) or 0

    return {
        "active_count": _count(is_sleeping=False, status="open"),
        "sleeping_count": _count(is_sleeping=True),
        "closed_count": _count(status="closed"),
    }


@router.get(
    "/{account_id}/{conversation_id}/timeline",
    summary="List conversation timeline",
    description="List timeline events for a conversation with configurable limit.",
    tags=["conversations"],
)
async def list_conversation_timeline(
    account_id: str,
    conversation_id: str,
    limit: int = 50,
    conversation_service: ConversationService = Depends(get_conversation_service),
    actor: RequestActor = Depends(require_permission("conversations.detail")),
) -> list[dict[str, object]]:
    actor.require_account_access(account_id)
    try:
        return [
            item.model_dump()
            for item in await conversation_service.list_timeline(
                account_id=account_id,
                conversation_id=conversation_id,
                limit=max(1, min(limit, 200)),
            )
        ]
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/{account_id}/{conversation_id}/messages/outbound",
    summary="Send outbound message",
    description="Send an outbound message to a conversation via the messaging provider.",
    tags=["conversations"],
)
async def send_outbound_message(
    account_id: str,
    conversation_id: str,
    payload: OutboundMessageRequest,
    conversation_service: ConversationService = Depends(get_conversation_service),
    actor: RequestActor = Depends(require_permission("conversations.reply")),
) -> dict[str, object]:
    actor.require_account_access(account_id)
    resolved_agent_id = actor.validate_agent_id(payload.agent_id)
    if resolved_agent_id is None and actor.role in {ActorRole.OPERATOR, ActorRole.SUPPORT_AGENT}:
        resolved_agent_id = actor.actor_id
    resolved_payload = payload.model_copy(update={"agent_id": resolved_agent_id})
    try:
        return (
            await conversation_service.send_outbound_message(
                account_id=account_id,
                conversation_id=conversation_id,
                payload=resolved_payload,
                actor_type=actor.actor_type,
                actor_id=actor.actor_id,
            )
        ).model_dump()
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        _raise_outbound_route_value_error(exc)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


class TranslateOutboundRequest(BaseModel):
    text: str
    target_language: str


@router.post(
    "/{account_id}/{conversation_id}/messages/{message_id}/translate",
    summary="Translate a single message",
    description="Translate one inbound message to the console language and persist the result.",
    tags=["conversations"],
)
async def translate_message(
    account_id: str,
    conversation_id: str,
    message_id: str,
    conversation_service: ConversationService = Depends(get_conversation_service),
    actor: RequestActor = Depends(require_permission("conversations.translate")),
) -> dict[str, object]:
    actor.require_account_access(account_id)
    try:
        result = await conversation_service.translate_message(
            account_id=account_id,
            conversation_id=conversation_id,
            message_id=message_id,
        )
        return cast(dict[str, object], result)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/{account_id}/{conversation_id}/messages/translate-batch",
    summary="Batch translate conversation messages",
    description="Translate all untranslated inbound messages in a conversation in a single AI request.",
    tags=["conversations"],
)
async def batch_translate_messages(
    account_id: str,
    conversation_id: str,
    conversation_service: ConversationService = Depends(get_conversation_service),
    actor: RequestActor = Depends(require_permission("conversations.translate")),
) -> dict[str, object]:
    actor.require_account_access(account_id)
    result = await conversation_service.batch_translate_messages(
        account_id=account_id,
        conversation_id=conversation_id,
    )
    return cast(dict[str, object], result)


@router.post(
    "/{account_id}/{conversation_id}/messages/translate-outbound",
    summary="Preview outbound translation",
    description="Translate operator text to a target language for preview before sending.",
    tags=["conversations"],
)
async def translate_outbound_preview(
    account_id: str,
    conversation_id: str,
    payload: TranslateOutboundRequest,
    conversation_service: ConversationService = Depends(get_conversation_service),
    actor: RequestActor = Depends(require_permission("conversations.translate")),
) -> dict[str, object]:
    actor.require_account_access(account_id)
    result = await conversation_service.translate_outbound_preview(
        text=payload.text,
        target_language=payload.target_language,
    )
    return cast(dict[str, object], result)


@router.post(
    "/{account_id}/{conversation_id}/messages/media",
    summary="Send media message",
    description="Send a media message (image, document, video) to a conversation.",
    tags=["conversations"],
)
async def send_media_message(
    account_id: str,
    conversation_id: str,
    payload: MediaAssetSendRequest,
    media_asset_service: MediaAssetService = Depends(get_media_asset_service),
    actor: RequestActor = Depends(require_permission("conversations.reply")),
) -> MediaAssetSendResponse:
    actor.require_account_access(account_id)
    resolved_agent_id = actor.validate_agent_id(payload.agent_id)
    if resolved_agent_id is None and actor.role in {ActorRole.OPERATOR, ActorRole.SUPPORT_AGENT}:
        resolved_agent_id = actor.actor_id
    resolved_payload = payload.model_copy(update={"agent_id": resolved_agent_id})
    try:
        return await media_asset_service.send_asset_to_conversation(
            account_id=account_id,
            conversation_id=conversation_id,
            payload=resolved_payload,
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except MediaProviderConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except MediaProviderUpstreamError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        _raise_outbound_route_value_error(exc)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post(
    "/{account_id}/{conversation_id}/assignment",
    summary="Assign conversation",
    description="Assign a conversation to an agent with an optional reason.",
    tags=["conversations"],
)
async def assign_conversation(
    account_id: str,
    conversation_id: str,
    payload: ConversationAssignmentRequest,
    runtime_state_store: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("conversations.transfer")),
) -> dict[str, object]:
    actor.require_account_access(account_id)
    admin_override = actor.is_super_admin and not actor.allow_impersonation
    resolved_assigned_by_agent_id = actor.validate_agent_id(payload.assigned_by_agent_id)
    if resolved_assigned_by_agent_id is None and actor.role in {ActorRole.OPERATOR, ActorRole.SUPPORT_AGENT}:
        resolved_assigned_by_agent_id = actor.actor_id
    handover_service = HandoverService(runtime_state_store)
    try:
        return (
            await handover_service.assign_conversation(
                account_id=account_id,
                conversation_id=conversation_id,
                agent_id=payload.agent_id,
                assigned_by_agent_id=resolved_assigned_by_agent_id,
                reason=payload.reason,
                actor_type=actor.actor_type,
                actor_id=actor.actor_id,
                admin_override=admin_override,
            )
        ).model_dump()
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    runtime_state_store.add_audit_log(
        account_id=account_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        action="conversation.assign",
        target_type="conversation",
        target_id=conversation_id,
        payload={"agent_id": payload.agent_id, "assigned_by": resolved_assigned_by_agent_id, "reason": payload.reason},
    )


@router.post(
    "/{account_id}/{conversation_id}/close",
    summary="Close conversation",
    description="Close a conversation with a reason provided by the closing agent.",
    tags=["conversations"],
)
async def close_conversation(
    account_id: str,
    conversation_id: str,
    payload: ConversationCloseRequest,
    runtime_state_store: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("conversations.close")),
) -> dict[str, object]:
    actor.require_account_access(account_id)
    admin_override = actor.is_super_admin and not actor.allow_impersonation
    resolved_agent_id = actor.validate_agent_id(payload.agent_id)
    if resolved_agent_id is None and actor.role in {ActorRole.OPERATOR, ActorRole.SUPPORT_AGENT}:
        resolved_agent_id = actor.actor_id
    handover_service = HandoverService(runtime_state_store)
    try:
        return (
            await handover_service.close_conversation(
                account_id=account_id,
                conversation_id=conversation_id,
                closed_by_agent_id=resolved_agent_id,
                reason=payload.reason,
                actor_type=actor.actor_type,
                actor_id=actor.actor_id,
                admin_override=admin_override,
            )
        ).model_dump()
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    runtime_state_store.add_audit_log(
        account_id=account_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        action="conversation.close",
        target_type="conversation",
        target_id=conversation_id,
        payload={"closed_by": resolved_agent_id, "reason": payload.reason},
    )


@router.post(
    "/{account_id}/{conversation_id}/reopen",
    summary="Reopen conversation",
    description="Reopen a previously closed conversation, restoring it to AI-managed mode.",
    tags=["conversations"],
)
async def reopen_conversation(
    account_id: str,
    conversation_id: str,
    payload: ConversationCloseRequest,
    runtime_state_store: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("conversations.reopen")),
) -> dict[str, object]:
    actor.require_account_access(account_id)
    admin_override = actor.is_super_admin and not actor.allow_impersonation
    resolved_agent_id = actor.validate_agent_id(payload.agent_id)
    if resolved_agent_id is None and actor.role in {ActorRole.OPERATOR, ActorRole.SUPPORT_AGENT}:
        resolved_agent_id = actor.actor_id
    handover_service = HandoverService(runtime_state_store)
    try:
        return (
            await handover_service.reopen_conversation(
                account_id=account_id,
                conversation_id=conversation_id,
                reopened_by_agent_id=resolved_agent_id,
                reason=payload.reason,
                actor_type=actor.actor_type,
                actor_id=actor.actor_id,
                admin_override=admin_override,
            )
        ).model_dump()
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


class TagUpdateRequest(BaseModel):
    tags: list[str]


@router.get(
    "/{account_id}/{conversation_id}/tags",
    summary="Get conversation tags",
    description="Get tags for a conversation.",
    tags=["conversations"],
)
async def get_conversation_tags(
    account_id: str,
    conversation_id: str,
    runtime_state_store: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("conversations.tags")),
) -> dict:
    actor.require_account_access(account_id)
    model = await runtime_state_store.get_conversation_model(account_id, conversation_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    tags = getattr(model, "tags", None) or []
    return {
        "conversation_id": conversation_id,
        "account_id": account_id,
        "tags": tags,
        "updated_at": getattr(model, "updated_at", None),
    }


@router.put(
    "/{account_id}/{conversation_id}/tags",
    summary="Update conversation tags",
    description="Update tags for a conversation.",
    tags=["conversations"],
)
async def update_conversation_tags(
    account_id: str,
    conversation_id: str,
    payload: TagUpdateRequest,
    runtime_state_store: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("conversations.tags")),
) -> dict:
    actor.require_account_access(account_id)
    model = await runtime_state_store.get_conversation_model(account_id, conversation_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    model.tags = payload.tags
    runtime_state_store.commit()
    return {
        "conversation_id": conversation_id,
        "account_id": account_id,
        "tags": payload.tags,
        "updated_at": getattr(model, "updated_at", None),
    }


@router.post(
    "/batch-handover",
    summary="Batch handover conversations",
    description="Hand over multiple conversations to human management. Independent transactions - single failure does not affect others.",
    tags=["conversations"],
)
async def batch_handover_conversations(
    payload: BatchConversationRequest,
    runtime_state_store: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("conversations.batch")),
) -> BatchOperationResponse:
    results: list[BatchOperationResult] = []
    for cid in payload.conversation_ids:
        try:
            parts = cid.split(":", 1)
            acc_id = parts[0] if len(parts) > 1 else None
            conv_id = parts[-1]
            if acc_id:
                actor.require_account_access(acc_id)
            from app.schemas.handover import ConversationHandoverRequest
            handover_payload = ConversationHandoverRequest(
                target_mode="human_managed",
                reason=payload.reason or "batch_handover",
            )
            handover_service = HandoverService(runtime_state_store)
            await handover_service.request_handover(
                account_id=acc_id or "",
                conversation_id=conv_id,
                payload=handover_payload,
                actor_type=actor.actor_type,
                actor_id=actor.actor_id,
            )
            results.append(BatchOperationResult(conversation_id=cid, status="success"))
        except Exception as exc:
            results.append(BatchOperationResult(conversation_id=cid, status="failed", error=str(exc)))
    success = sum(1 for r in results if r.status == "success")
    return BatchOperationResponse(success_count=success, failed_count=len(results) - success, results=results)


@router.post(
    "/batch-restore-ai",
    summary="Batch restore AI management",
    description="Restore AI management for multiple conversations. Independent transactions.",
    tags=["conversations"],
)
async def batch_restore_ai_conversations(
    payload: BatchConversationRequest,
    runtime_state_store: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("conversations.batch")),
) -> BatchOperationResponse:
    results: list[BatchOperationResult] = []
    for cid in payload.conversation_ids:
        try:
            parts = cid.split(":", 1)
            acc_id = parts[0] if len(parts) > 1 else None
            conv_id = parts[-1]
            if acc_id:
                actor.require_account_access(acc_id)
            from app.schemas.handover import ConversationHandoverRequest
            handover_payload = ConversationHandoverRequest(
                target_mode="ai_managed",
                reason=payload.reason or "batch_restore_ai",
            )
            handover_service = HandoverService(runtime_state_store)
            await handover_service.request_handover(
                account_id=acc_id or "",
                conversation_id=conv_id,
                payload=handover_payload,
                actor_type=actor.actor_type,
                actor_id=actor.actor_id,
            )
            results.append(BatchOperationResult(conversation_id=cid, status="success"))
        except Exception as exc:
            results.append(BatchOperationResult(conversation_id=cid, status="failed", error=str(exc)))
    success = sum(1 for r in results if r.status == "success")
    return BatchOperationResponse(success_count=success, failed_count=len(results) - success, results=results)


@router.post(
    "/batch-close",
    summary="Batch close conversations",
    description="Close multiple conversations. Independent transactions.",
    tags=["conversations"],
)
async def batch_close_conversations(
    payload: BatchConversationRequest,
    runtime_state_store: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("conversations.batch")),
) -> BatchOperationResponse:
    results: list[BatchOperationResult] = []
    for cid in payload.conversation_ids:
        try:
            parts = cid.split(":", 1)
            acc_id = parts[0] if len(parts) > 1 else None
            conv_id = parts[-1]
            if acc_id:
                actor.require_account_access(acc_id)
            from app.schemas.handover import ConversationCloseRequest
            close_payload = ConversationCloseRequest(
                agent_id=actor.actor_id,
                reason=payload.reason or "batch_close",
            )
            handover_service = HandoverService(runtime_state_store)
            await handover_service.close_conversation(
                account_id=acc_id or "",
                conversation_id=conv_id,
                closed_by_agent_id=actor.actor_id,
                reason=close_payload.reason,
                actor_type=actor.actor_type,
                actor_id=actor.actor_id,
            )
            results.append(BatchOperationResult(conversation_id=cid, status="success"))
        except Exception as exc:
            results.append(BatchOperationResult(conversation_id=cid, status="failed", error=str(exc)))
    success = sum(1 for r in results if r.status == "success")
    return BatchOperationResponse(success_count=success, failed_count=len(results) - success, results=results)


@router.post(
    "/batch-assign",
    summary="Batch assign conversations",
    description="Assign multiple conversations to an agent. Independent transactions.",
    tags=["conversations"],
)
async def batch_assign_conversations(
    payload: BatchAssignRequest,
    runtime_state_store: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("conversations.batch")),
) -> BatchOperationResponse:
    results: list[BatchOperationResult] = []
    for cid in payload.conversation_ids:
        try:
            parts = cid.split(":", 1)
            acc_id = parts[0] if len(parts) > 1 else None
            conv_id = parts[-1]
            if acc_id:
                actor.require_account_access(acc_id)
            from app.schemas.handover import ConversationAssignmentRequest
            assign_payload = ConversationAssignmentRequest(
                agent_id=payload.agent_id,
                assigned_by_agent_id=actor.actor_id,
                reason=payload.reason or "batch_assign",
            )
            handover_service = HandoverService(runtime_state_store)
            await handover_service.assign_conversation(
                account_id=acc_id or "",
                conversation_id=conv_id,
                agent_id=assign_payload.agent_id,
                assigned_by_agent_id=actor.actor_id,
                reason=assign_payload.reason,
                actor_type=actor.actor_type,
                actor_id=actor.actor_id,
            )
            runtime_state_store.add_audit_log(
                account_id=acc_id or "",
                actor_type=actor.actor_type,
                actor_id=actor.actor_id,
                action="conversation.batch_assign",
                target_type="conversation",
                target_id=cid,
                payload={"agent_id": payload.agent_id, "reason": payload.reason},
            )
            results.append(BatchOperationResult(conversation_id=cid, status="success"))
        except Exception as exc:
            results.append(BatchOperationResult(conversation_id=cid, status="failed", error=str(exc)))
    success = sum(1 for r in results if r.status == "success")
    return BatchOperationResponse(success_count=success, failed_count=len(results) - success, results=results)


# ── B-01: Message search ──
@router.get(
    "/{account_id}/{conversation_id}/messages/search",
    summary="Search conversation messages",
    description="Search messages within a conversation by content text (ILIKE).",
    tags=["conversations"],
)
async def search_messages(
    account_id: str,
    conversation_id: str,
    q: str = Query(min_length=1),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    conversation_service: ConversationService = Depends(get_conversation_service),
    actor: RequestActor = Depends(require_permission("conversations.detail")),
) -> list[dict[str, object]]:
    actor.require_account_access(account_id)
    try:
        return [
            msg.model_dump()
            for msg in await conversation_service.search_messages(
                account_id=account_id,
                conversation_id=conversation_id,
                q=q,
                limit=limit,
                offset=offset,
            )
        ]
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ── B-02: Customer conversations ──
@router.get(
    "/by-customer/{customer_id}",
    summary="List customer conversations",
    description="List all conversations for a given customer, ordered by last message time.",
    tags=["conversations"],
)
async def list_customer_conversations(
    customer_id: str,
    account_id: str = Query(),
    exclude_conversation_id: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    conversation_service: ConversationService = Depends(get_conversation_service),
    actor: RequestActor = Depends(require_permission("conversations.view")),
) -> list[dict[str, object]]:
    actor.require_account_access(account_id)
    return await conversation_service.list_customer_conversations(
        account_id=account_id,
        customer_id=customer_id,
        exclude_conversation_id=exclude_conversation_id,
        limit=limit,
    )


# ── B-03: Forward message ──
@router.post(
    "/{account_id}/{conversation_id}/messages/{message_id}/forward",
    summary="Forward message",
    description="Forward a message to another conversation as an outbound message.",
    tags=["conversations"],
)
async def forward_message(
    account_id: str,
    conversation_id: str,
    message_id: str,
    payload: ForwardMessageRequest,
    conversation_service: ConversationService = Depends(get_conversation_service),
    actor: RequestActor = Depends(require_permission("conversations.reply")),
) -> dict[str, str]:
    actor.require_account_access(account_id)
    try:
        return await conversation_service.forward_message(
            account_id=account_id,
            conversation_id=conversation_id,
            message_id=message_id,
            target_conversation_id=payload.target_conversation_id,
            include_context=payload.include_context,
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# ── B-04: Sentiment analysis ──
@router.get(
    "/{account_id}/{conversation_id}/sentiment",
    summary="Get conversation sentiment",
    description="Analyze the sentiment of recent inbound messages using AI.",
    tags=["conversations"],
)
async def get_conversation_sentiment(
    account_id: str,
    conversation_id: str,
    conversation_service: ConversationService = Depends(get_conversation_service),
    actor: RequestActor = Depends(require_permission("conversations.sentiment")),
) -> dict[str, object]:
    actor.require_account_access(account_id)
    try:
        return await conversation_service.get_sentiment(
            account_id=account_id,
            conversation_id=conversation_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ── B-05: SLA ──
@router.get(
    "/{account_id}/{conversation_id}/sla",
    summary="Get conversation SLA",
    description="Get SLA waiting time info for a conversation.",
    tags=["conversations"],
)
async def get_conversation_sla(
    account_id: str,
    conversation_id: str,
    conversation_service: ConversationService = Depends(get_conversation_service),
    actor: RequestActor = Depends(require_permission("conversations.sla")),
) -> dict[str, object]:
    actor.require_account_access(account_id)
    try:
        return await conversation_service.get_sla(
            account_id=account_id,
            conversation_id=conversation_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ── B-06: AI reply preview ──
@router.post(
    "/{account_id}/{conversation_id}/ai-preview",
    summary="Preview AI reply",
    description="Generate an AI reply preview without persisting to the messages table.",
    tags=["conversations"],
)
async def preview_ai_reply(
    account_id: str,
    conversation_id: str,
    conversation_service: ConversationService = Depends(get_conversation_service),
    actor: RequestActor = Depends(require_permission("conversations.ai_preview")),
) -> dict[str, object]:
    actor.require_account_access(account_id)
    try:
        return await conversation_service.preview_ai_reply(
            account_id=account_id,
            conversation_id=conversation_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ── Batch metadata (tags + sentiment + SLA) ──

class BatchMetadataItem(BaseModel):
    account_id: str
    conversation_id: str
    tags: list[str] = []
    sentiment: str | None = None
    sentiment_confidence: float | None = None
    sla_overdue: bool = False
    sla_waiting_seconds: int = 0
    error: str | None = None


class BatchMetadataResponse(BaseModel):
    items: list[BatchMetadataItem]


@router.get(
    "/metadata/batch",
    summary="Batch get conversation metadata",
    description="Get tags, sentiment, and SLA for multiple conversations in a single request.",
    tags=["conversations"],
)
async def batch_get_metadata(
    ids: str = Query(description="Comma-separated account_id:conversation_id pairs"),
    conversation_service: ConversationService = Depends(get_conversation_service),
    actor: RequestActor = Depends(require_permission("conversations.detail")),
) -> BatchMetadataResponse:
    pairs: list[tuple[str, str]] = []
    for raw in ids.split(","):
        raw = raw.strip()
        if ":" not in raw:
            continue
        aid, cid = raw.split(":", 1)
        pairs.append((aid.strip(), cid.strip()))

    if not pairs:
        return BatchMetadataResponse(items=[])

    for aid, _cid in pairs:
        actor.require_account_access(aid)

    results: list[BatchMetadataItem] = []
    for aid, cid in pairs:
        item = BatchMetadataItem(account_id=aid, conversation_id=cid)
        try:
            conv = await conversation_service._runtime_state.get_conversation_model(aid, cid)
            if conv is None:
                item.error = "Conversation not found"
                results.append(item)
                continue

            item.tags = getattr(conv, "tags", None) or []

            try:
                sentiment_result = await conversation_service.get_sentiment(aid, cid)
                item.sentiment = str(sentiment_result.get("sentiment", "neutral"))
                item.sentiment_confidence = float(sentiment_result.get("confidence", 0.0))
            except Exception:
                item.sentiment = "neutral"
                item.sentiment_confidence = 0.0

            try:
                sla_result = await conversation_service.get_sla(aid, cid)
                waiting = int(sla_result.get("waiting_seconds", 0))
                critical = int(sla_result.get("threshold_critical", 3600))
                item.sla_waiting_seconds = waiting
                item.sla_overdue = waiting > critical
            except Exception:
                item.sla_waiting_seconds = 0
                item.sla_overdue = False

        except Exception as exc:
            item.error = str(exc)

        results.append(item)

    return BatchMetadataResponse(items=results)
