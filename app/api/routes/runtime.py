from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import (
    get_db_session,
    get_launch_readiness_service,
    get_runtime_state_service,
    get_support_knowledge_service,
    require_permission,
    get_settings,
)
from app.core.auth import ActorRole, RequestActor, filter_account_scoped_items
from app.core.settings import get_settings
from app.schemas.audit import AuditLogEntry
from app.schemas.handover import AgentRegistrationRequest, AgentStatusUpdateRequest
from app.schemas.runtime import (
    AccountRegistrationRequest,
    AiToggleRequest,
    ConversationAiStatusResponse,
    ConversationHandoverRequest,
    LaunchReadinessResponse,
    ProviderStatusBufferEntry,
    ProviderStatusBufferListResponse,
    ProviderStatusBufferReplayRequest,
    ProviderStatusBufferReplayResponse,
    RuntimeConfigSummary,
    RuntimeStateResponse,
)
from app.schemas.support_knowledge import (
    SupportKnowledgeEntryCreateRequest,
    SupportKnowledgeEntryUpdateRequest,
    SupportKnowledgeExportBundle,
    SupportKnowledgeImportRequest,
    SupportKnowledgeImportResult,
)
from app.services.business_hours_service import BusinessHoursService
from app.services.handover_service import HandoverService
from app.services.launch_readiness_service import LaunchReadinessService
from app.services.meta_scope_validation import MetaScopeValidator
from app.services.runtime_state import RuntimeStateStore
from app.services.support_knowledge_service import SupportKnowledgeService
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/runtime", tags=["runtime"])


def _validate_runtime_meta_scope(
    *,
    session: Session,
    actor: RequestActor,
    account_id: str | None,
    waba_id: str | None,
    phone_number_id: str | None,
) -> None:
    validator = MetaScopeValidator(session)
    validator.validate_waba_scope(
        account_id=account_id,
        waba_id=waba_id,
        allowed_account_ids=None if actor.is_super_admin else set(actor.account_ids),
    )
    validator.validate_phone_number_scope(
        phone_number_id=phone_number_id,
        account_id=account_id,
        waba_id=waba_id,
        allowed_account_ids=None if actor.is_super_admin else set(actor.account_ids),
        enforce_waba_match=True,
    )


@router.get(
    "/state",
    summary="Get runtime state",
    description="Get current runtime state including accounts, conversations, and AI status.",
    tags=["runtime"],
)
async def get_runtime_state(
    runtime_state_store: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("runtime.view")),
) -> dict[str, object]:
    try:
        state = await runtime_state_store.list_state()
    except Exception:
        # DB unreachable (PostgreSQL/Redis unavailable), return empty state
        return RuntimeStateResponse(
            global_ai_enabled=True,
            accounts=[],
            conversations=[],
        ).model_dump()
    if actor.is_super_admin:
        return state.model_dump()
    filtered_state = RuntimeStateResponse(
        global_ai_enabled=state.global_ai_enabled,
        accounts=[account for account in state.accounts if actor.can_access_account(account.account_id)],
        conversations=[
            conversation
            for conversation in state.conversations
            if actor.can_access_account(conversation.account_id)
        ],
    )
    return filtered_state.model_dump()


@router.get(
    "/config-summary",
    summary="Get config summary",
    description="Get runtime configuration summary including provider settings.",
    tags=["runtime"],
)
async def get_runtime_config_summary(
    actor: RequestActor = Depends(require_permission("runtime.view")),
) -> dict[str, object]:
    _ = actor
    settings = get_settings()
    ai_model = (
        settings.openai_model
        if settings.ai_provider == "openai"
        else settings.deepseek_model
        if settings.ai_provider == "deepseek"
        else "mock"
    )
    translation_provider = settings.resolve_translation_provider_name()
    queue_backend = "memory" if settings.test_mode else settings.queue_provider
    return RuntimeConfigSummary(
        app_env=settings.app_env,
        test_mode=settings.test_mode,
        messaging_provider=settings.messaging_provider,
        ai_provider=settings.ai_provider,
        ai_model=ai_model,
        ecommerce_provider=settings.ecommerce_provider,
        openai_configured=bool(settings.openai_api_key),
        deepseek_configured=bool(settings.deepseek_api_key),
        translation_provider=translation_provider,
        live_translation_enabled=settings.live_translation_enabled,
        console_language=settings.console_language,
        auto_translate_on_human_handover=settings.auto_translate_on_human_handover,
        auto_translate_on_conversation_open=settings.auto_translate_on_conversation_open,
        auto_translate_operator_outbound=settings.auto_translate_operator_outbound,
        queue_backend=queue_backend,
        queue_max_retries=settings.queue_max_retries,
        queue_poll_timeout_seconds=settings.queue_poll_timeout_seconds,
    ).model_dump()


@router.get(
    "/launch-readiness",
    summary="Get launch readiness",
    description="Assess launch readiness for accounts with optional scope filter.",
    tags=["runtime"],
)
async def get_launch_readiness(
    account_id: str | None = None,
    launch_readiness_service: LaunchReadinessService = Depends(get_launch_readiness_service),
    actor: RequestActor = Depends(require_permission("runtime.view")),
) -> dict[str, object]:
    if account_id is not None:
        actor.require_account_access(account_id)
    try:
        readiness = await launch_readiness_service.assess_with_scope(
            allowed_account_ids=None if actor.is_super_admin else set(actor.account_ids),
            account_id=account_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception:
        # DB unreachable (PostgreSQL/Redis unavailable), return empty readiness
        return LaunchReadinessResponse().model_dump(mode="json")
    return LaunchReadinessResponse.model_validate(
        readiness
    ).model_dump(mode="json")


def _serialize_provider_status_buffer_entry(
    *,
    item: object,
    runtime_state_store: RuntimeStateStore,
) -> dict[str, object]:
    first_seen_at = item.first_seen_at if isinstance(item.first_seen_at, datetime) else None
    pending_age_seconds = (
        max(
            0.0,
            (
                datetime.now(UTC).replace(tzinfo=None)
                - first_seen_at
            ).total_seconds(),
        )
        if first_seen_at is not None
        else 0.0
    )
    resolved_waba_id, resolved_phone_number_id = runtime_state_store.resolve_provider_status_buffer_scope(
        item
    )
    return ProviderStatusBufferEntry(
        id=item.id,
        account_id=item.account_id,
        provider_name=item.provider_name,
        waba_id=resolved_waba_id,
        phone_number_id=resolved_phone_number_id,
        provider_message_id=item.provider_message_id,
        external_status=item.external_status,
        recipient_id=item.recipient_id,
        occurred_at=item.occurred_at,
        error_code=item.error_code,
        payload=dict(item.payload) if isinstance(item.payload, dict) else {},
        first_seen_at=item.first_seen_at.isoformat(),
        last_seen_at=item.last_seen_at.isoformat(),
        seen_count=item.seen_count,
        replay_state=item.replay_state,
        replayed_at=item.replayed_at.isoformat() if item.replayed_at is not None else None,
        replayed_message_event_id=item.replayed_message_event_id,
        replay_error=item.replay_error,
        pending_age_seconds=pending_age_seconds,
    ).model_dump(mode="json")


@router.get(
    "/provider-status-buffer",
    summary="List provider status buffer",
    description="List provider status buffer events with optional filters.",
    tags=["runtime"],
)
async def list_provider_status_buffer(
    account_id: str | None = None,
    provider_name: str | None = None,
    provider_message_id: str | None = None,
    external_status: str | None = None,
    replay_state: str | None = None,
    waba_id: str | None = None,
    phone_number_id: str | None = None,
    limit: int = 100,
    db_session: Session = Depends(get_db_session),
    runtime_state_store: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("runtime.view")),
) -> dict[str, object]:
    if replay_state is not None and replay_state not in {"pending", "replayed"}:
        raise HTTPException(status_code=400, detail="replay_state must be pending or replayed.")
    limit = max(1, min(limit, 200))
    if account_id is not None:
        actor.require_account_access(account_id)
    try:
        _validate_runtime_meta_scope(
            session=db_session,
            actor=actor,
            account_id=account_id,
            waba_id=waba_id,
            phone_number_id=phone_number_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    allowed_account_ids = None if actor.is_super_admin else set(actor.account_ids)
    try:
        items = await runtime_state_store.list_provider_status_buffer_events(
            account_id=account_id,
            account_ids=allowed_account_ids,
            provider_name=provider_name,
            provider_message_id=provider_message_id,
            external_status=external_status,
            replay_state=replay_state,
            waba_id=waba_id,
            phone_number_id=phone_number_id,
            limit=limit,
        )
        pending_counts = await runtime_state_store.count_provider_status_buffer_events(
            account_id=account_id,
            account_ids=allowed_account_ids,
            replay_state="pending",
            provider_name=provider_name,
            provider_message_id=provider_message_id,
            external_status=external_status,
            waba_id=waba_id,
            phone_number_id=phone_number_id,
        )
        replayed_counts = await runtime_state_store.count_provider_status_buffer_events(
            account_id=account_id,
            account_ids=allowed_account_ids,
            replay_state="replayed",
            provider_name=provider_name,
            provider_message_id=provider_message_id,
            external_status=external_status,
            waba_id=waba_id,
            phone_number_id=phone_number_id,
        )
    except Exception:
        # DB unreachable (PostgreSQL/Redis unavailable), return empty buffer
        return ProviderStatusBufferListResponse(
            items=[], returned_count=0, pending_count=0, replayed_count=0
        ).model_dump(mode="json")
    return ProviderStatusBufferListResponse(
        items=[
            _serialize_provider_status_buffer_entry(
                item=item,
                runtime_state_store=runtime_state_store,
            )
            for item in items
        ],
        returned_count=len(items),
        pending_count=sum(pending_counts.values()),
        replayed_count=sum(replayed_counts.values()),
    ).model_dump(mode="json")


@router.post(
    "/provider-status-buffer/replay",
    summary="Replay provider status buffer",
    description="Replay pending provider status buffer events.",
    tags=["runtime"],
)
async def replay_provider_status_buffer(
    payload: ProviderStatusBufferReplayRequest,
    db_session: Session = Depends(get_db_session),
    runtime_state_store: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("runtime.edit")),
) -> dict[str, object]:
    actor.require_account_access(payload.account_id)
    try:
        _validate_runtime_meta_scope(
            session=db_session,
            actor=actor,
            account_id=payload.account_id,
            waba_id=payload.waba_id,
            phone_number_id=payload.phone_number_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    pending_counts = await runtime_state_store.count_provider_status_buffer_events(
        account_id=payload.account_id,
        account_ids={payload.account_id},
        replay_state="pending",
        provider_name=payload.provider_name,
        provider_message_id=payload.provider_message_id,
        external_status=payload.external_status,
        waba_id=payload.waba_id,
        phone_number_id=payload.phone_number_id,
    )
    checked_count = sum(pending_counts.values())
    if checked_count == 0:
        raise HTTPException(status_code=404, detail="No pending provider status buffer events matched.")
    checked_count, replayed_count = await runtime_state_store.replay_provider_status_buffer_events(
        account_id=payload.account_id,
        provider_name=payload.provider_name,
        provider_message_id=payload.provider_message_id,
        external_status=payload.external_status,
        waba_id=payload.waba_id,
        phone_number_id=payload.phone_number_id,
        limit=payload.limit,
    )
    failed_count = checked_count - replayed_count
    runtime_state_store.add_audit_log(
        account_id=payload.account_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        action="provider_status_buffer_replay_requested",
        target_type="provider_status_buffer",
        target_id=payload.provider_message_id or payload.account_id,
        payload={
            "provider_name": payload.provider_name,
            "provider_message_id": payload.provider_message_id,
            "external_status": payload.external_status,
            "waba_id": payload.waba_id,
            "phone_number_id": payload.phone_number_id,
            "checked_count": checked_count,
            "replayed_count": replayed_count,
            "failed_count": failed_count,
        },
    )
    runtime_state_store.commit()
    if replayed_count == 0:
        raise HTTPException(
            status_code=409,
            detail="Pending provider status buffer events were found, but none could be replayed.",
        )
    return ProviderStatusBufferReplayResponse(
        account_id=payload.account_id,
        provider_name=payload.provider_name,
        provider_message_id=payload.provider_message_id,
        external_status=payload.external_status,
        waba_id=payload.waba_id,
        phone_number_id=payload.phone_number_id,
        checked_count=checked_count,
        replayed_count=replayed_count,
        failed_count=failed_count,
    ).model_dump(mode="json")


@router.get(
    "/business-hours",
    summary="Get business hours",
    description="Get business hours configuration for an account, including whether it is currently business hours.",
    tags=["runtime"],
)
async def get_business_hours(
    account_id: str,
    db_session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("settings.runtime")),
) -> dict:
    actor.require_account_access(account_id)
    service = BusinessHoursService(db_session)
    return await service.get_hours(account_id=account_id)


@router.put(
    "/business-hours",
    summary="Update business hours",
    description="Update business hours configuration for an account.",
    tags=["runtime"],
)
async def update_business_hours(
    account_id: str,
    weekdays: list[int] | None = Query(default=None),
    start_time: str | None = Query(default=None),
    end_time: str | None = Query(default=None),
    timezone: str | None = Query(default=None),
    off_hours_behavior: str | None = Query(default=None),
    off_hours_message: str | None = Query(default=None),
    db_session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("settings.runtime")),
) -> dict:
    actor.require_account_access(account_id)
    service = BusinessHoursService(db_session)
    return await service.upsert_hours(
        account_id=account_id,
        weekdays=weekdays,
        start_time=start_time,
        end_time=end_time,
        timezone=timezone,
        off_hours_behavior=off_hours_behavior,
        off_hours_message=off_hours_message,
    )


@router.get(
    "/audit-logs",
    summary="List audit logs",
    description="List audit log entries with optional filters and date range.",
    tags=["runtime"],
)
async def list_audit_logs(
    account_id: str | None = None,
    waba_id: str | None = None,
    phone_number_id: str | None = None,
    actor_type: str | None = None,
    actor_id: str | None = None,
    action: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 100,
    db_session: Session = Depends(get_db_session),
    runtime_state_store: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("audit.view")),
) -> list[dict[str, object]]:
    if account_id is not None:
        actor.require_account_access(account_id)
    if date_from is not None and date_to is not None and date_from > date_to:
        raise HTTPException(status_code=400, detail="date_from cannot be after date_to.")
    try:
        _validate_runtime_meta_scope(
            session=db_session,
            actor=actor,
            account_id=account_id,
            waba_id=waba_id,
            phone_number_id=phone_number_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        audit_logs = await runtime_state_store.list_audit_logs(
            account_id=account_id,
            waba_id=waba_id,
            phone_number_id=phone_number_id,
            actor_type=actor_type,
            actor_id=actor_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            date_from=date_from,
            date_to=date_to,
            limit=max(1, min(limit, 200)),
            allowed_account_ids=None if actor.is_super_admin else set(actor.account_ids),
        )
        if not actor.is_super_admin:
            audit_logs = [
                item
                for item in audit_logs
                if item.account_id is None or actor.can_access_account(item.account_id)
            ]
        return [
            AuditLogEntry.model_validate(
                {
                    "id": item.id,
                    "account_id": item.account_id,
                    "waba_id": runtime_state_store._extract_audit_waba_id(item),
                    "phone_number_id": runtime_state_store._extract_audit_phone_number_id(item.payload),
                    "actor_type": item.actor_type,
                    "actor_id": item.actor_id,
                    "action": item.action,
                    "target_type": item.target_type,
                    "target_id": item.target_id,
                    "payload": item.payload,
                    "created_at": item.created_at,
                }
            ).model_dump(mode="json")
            for item in audit_logs
        ]
    except Exception:
        # DB unreachable (PostgreSQL/Redis unavailable), return empty list
        return []


@router.get(
    "/support-knowledge",
    summary="Get support knowledge",
    description="List support knowledge entries with optional category and account filters.",
    tags=["runtime"],
)
async def get_support_knowledge(
    category: str | None = None,
    account_id: str | None = None,
    include_builtin: bool = True,
    support_knowledge_service: SupportKnowledgeService = Depends(get_support_knowledge_service),
    actor: RequestActor = Depends(require_permission("knowledge.view")),
) -> list[dict[str, object]]:
    if account_id is not None:
        actor.require_account_access(account_id)
    entries = await support_knowledge_service.list_entries(
        account_id=account_id,
        category=category,
        include_builtin=include_builtin,
    )
    if actor.is_super_admin:
        return [item.model_dump() for item in entries]
    return [
        item.model_dump()
        for item in entries
        if item.account_id is None or actor.can_access_account(item.account_id)
    ]


@router.post(
    "/support-knowledge",
    summary="Create support knowledge",
    description="Create a new support knowledge entry.",
    tags=["runtime"],
)
async def create_support_knowledge(
    payload: SupportKnowledgeEntryCreateRequest,
    support_knowledge_service: SupportKnowledgeService = Depends(get_support_knowledge_service),
    runtime_state_store: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("knowledge.manage")),
) -> dict[str, object]:
    actor.require_account_access(payload.account_id)
    try:
        entry = await support_knowledge_service.create_entry(payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    runtime_state_store.add_audit_log(
        account_id=payload.account_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        action="support_knowledge_created",
        target_type="support_knowledge",
        target_id=payload.article_id,
        payload={
            "route_name": payload.route_name,
            "category": payload.category,
        },
    )
    runtime_state_store.commit()
    return entry.model_dump()


@router.get(
    "/support-knowledge/export",
    summary="Export support knowledge",
    description="Export support knowledge entries as a bundle.",
    tags=["runtime"],
)
async def export_support_knowledge(
    account_id: str | None = None,
    category: str | None = None,
    include_inactive: bool = True,
    support_knowledge_service: SupportKnowledgeService = Depends(get_support_knowledge_service),
    runtime_state_store: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("knowledge.view")),
) -> dict[str, object]:
    if account_id is not None:
        actor.require_account_access(account_id)
    bundle = await support_knowledge_service.export_entries(
        account_id=account_id,
        category=category,
        include_inactive=include_inactive,
    )
    if not actor.is_super_admin and account_id is None:
        bundle.entries = [
            entry
            for entry in bundle.entries
            if actor.can_access_account(entry.account_id)
        ]
        bundle.total_entries = len(bundle.entries)
    runtime_state_store.add_audit_log(
        account_id=account_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        action="support_knowledge_exported",
        target_type="support_knowledge_bundle",
        target_id=account_id or "all_accounts",
        payload={
            "category": category,
            "include_inactive": include_inactive,
            "total_entries": bundle.total_entries,
        },
    )
    runtime_state_store.commit()
    return SupportKnowledgeExportBundle.model_validate(bundle).model_dump(mode="json")


@router.post(
    "/support-knowledge/import",
    summary="Import support knowledge",
    description="Import support knowledge entries from a bundle.",
    tags=["runtime"],
)
async def import_support_knowledge(
    payload: SupportKnowledgeImportRequest,
    support_knowledge_service: SupportKnowledgeService = Depends(get_support_knowledge_service),
    runtime_state_store: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("knowledge.manage")),
) -> dict[str, object]:
    if payload.target_account_id is not None:
        actor.require_account_access(payload.target_account_id)
    else:
        for entry in payload.entries:
            actor.require_account_access(entry.account_id)
    try:
        result = await support_knowledge_service.import_entries(payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    account_scope = payload.target_account_id
    if account_scope is None:
        distinct_accounts = {entry.account_id for entry in payload.entries}
        if len(distinct_accounts) == 1:
            account_scope = next(iter(distinct_accounts))

    runtime_state_store.add_audit_log(
        account_id=account_scope,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        action="support_knowledge_imported",
        target_type="support_knowledge_bundle",
        target_id=account_scope or "mixed_accounts",
        payload={
            "entry_count": len(payload.entries),
            "created_count": result.created_count,
            "updated_count": result.updated_count,
            "skipped_count": result.skipped_count,
            "upsert_existing": payload.upsert_existing,
        },
    )
    runtime_state_store.commit()
    return SupportKnowledgeImportResult.model_validate(result).model_dump()


@router.post(
    "/support-knowledge/{article_id}",
    summary="Update support knowledge",
    description="Update an existing support knowledge entry.",
    tags=["runtime"],
)
async def update_support_knowledge(
    article_id: str,
    account_id: str,
    payload: SupportKnowledgeEntryUpdateRequest,
    support_knowledge_service: SupportKnowledgeService = Depends(get_support_knowledge_service),
    runtime_state_store: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("knowledge.manage")),
) -> dict[str, object]:
    actor.require_account_access(account_id)
    try:
        entry = await support_knowledge_service.update_entry(
            account_id=account_id,
            article_id=article_id,
            payload=payload,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    runtime_state_store.add_audit_log(
        account_id=account_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        action="support_knowledge_updated",
        target_type="support_knowledge",
        target_id=article_id,
        payload=payload.model_dump(exclude_none=True),
    )
    runtime_state_store.commit()
    return entry.model_dump()


@router.delete(
    "/support-knowledge/{article_id}",
    summary="Delete support knowledge",
    description="Delete a support knowledge entry.",
    tags=["runtime"],
)
async def delete_support_knowledge(
    article_id: str,
    account_id: str,
    support_knowledge_service: SupportKnowledgeService = Depends(get_support_knowledge_service),
    runtime_state_store: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("knowledge.manage")),
) -> dict[str, object]:
    actor.require_account_access(account_id)
    try:
        await support_knowledge_service.delete_entry(account_id=account_id, article_id=article_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    runtime_state_store.add_audit_log(
        account_id=account_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        action="support_knowledge_deleted",
        target_type="support_knowledge",
        target_id=article_id,
        payload=None,
    )
    runtime_state_store.commit()
    return {
        "account_id": account_id,
        "article_id": article_id,
        "deleted": True,
    }


@router.get(
    "/accounts",
    summary="List accounts",
    description="List registered accounts with optional ID filter.",
    tags=["runtime"],
)
async def list_accounts(
    account_id: str | None = None,
    runtime_state_store: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("runtime.view")),
) -> list[dict[str, object]]:
    if account_id is not None:
        actor.require_account_access(account_id)
        if runtime_state_store.get_account_model(account_id) is None:
            raise HTTPException(status_code=404, detail=f"Account '{account_id}' was not found.")
    accounts = (await runtime_state_store.list_state()).accounts
    return [
        account.model_dump()
        for account in filter_account_scoped_items(actor, accounts, lambda item: item.account_id)
        if account_id is None or account.account_id == account_id
    ]


@router.post(
    "/accounts",
    summary="Register account",
    description="Register a new account in the runtime state.",
    tags=["runtime"],
)
async def register_account(
    payload: AccountRegistrationRequest,
    runtime_state_store: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("runtime.edit")),
) -> dict[str, object]:
    actor.require_account_access(payload.account_id)
    account = await runtime_state_store.ensure_account(
        account_id=payload.account_id,
        display_name=payload.display_name,
        provider_type=payload.provider_type,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
    )
    return runtime_state_store._serialize_account(account).model_dump()


@router.get(
    "/agents",
    summary="List agents",
    description="List registered agents with optional status and active filters.",
    tags=["runtime"],
)
async def list_agents(
    account_id: str | None = None,
    status: str | None = None,
    is_active: bool | None = None,
    runtime_state_store: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("runtime.view")),
) -> list[dict[str, object]]:
    if account_id is not None:
        actor.require_account_access(account_id)
    handover_service = HandoverService(runtime_state_store)
    try:
        return [
            agent.model_dump()
            for agent in await handover_service.list_agents(
                account_id=account_id,
                allowed_account_ids=None if actor.is_super_admin else set(actor.account_ids),
                status=status,
                is_active=is_active,
            )
        ]
    except Exception:
        # DB unreachable (PostgreSQL/Redis unavailable), return empty list
        return []


@router.get(
    "/agents/workloads",
    summary="List agent workloads",
    description="List agent workloads with optional status and active filters.",
    tags=["runtime"],
)
async def list_agent_workloads(
    account_id: str | None = None,
    status: str | None = None,
    is_active: bool | None = None,
    runtime_state_store: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("runtime.view")),
) -> list[dict[str, object]]:
    if account_id is not None:
        actor.require_account_access(account_id)
    handover_service = HandoverService(runtime_state_store)
    return [
        item.model_dump()
        for item in await handover_service.list_agent_workloads(
            account_id=account_id,
            allowed_account_ids=None if actor.is_super_admin else set(actor.account_ids),
            status=status,
            is_active=is_active,
        )
    ]


@router.post(
    "/agents",
    summary="Register agent",
    description="Register a new agent in the runtime.",
    tags=["runtime"],
)
async def register_agent(
    payload: AgentRegistrationRequest,
    runtime_state_store: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("runtime.edit")),
) -> dict[str, object]:
    actor.require_account_access(payload.account_id)
    handover_service = HandoverService(runtime_state_store)
    return (
        await handover_service.register_agent(
            payload,
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
        )
    ).model_dump()


@router.post(
    "/agents/{agent_id}/status",
    summary="Set agent status",
    description="Update the status of a registered agent.",
    tags=["runtime"],
)
async def set_agent_status(
    agent_id: str,
    payload: AgentStatusUpdateRequest,
    account_id: str | None = None,
    runtime_state_store: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("runtime.edit")),
) -> dict[str, object]:
    actor.require_account_access(account_id)
    handover_service = HandoverService(runtime_state_store)
    try:
        return (
            await handover_service.set_agent_status(
                account_id,
                agent_id,
                payload.status,
                actor_type=actor.actor_type,
                actor_id=actor.actor_id,
            )
        ).model_dump()
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/ai/global",
    summary="Set global AI",
    description="Enable or disable AI globally across all conversations.",
    tags=["runtime"],
)
async def set_global_ai(
    payload: AiToggleRequest,
    runtime_state_store: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("settings.ai_config")),
) -> dict[str, object]:
    return (
        await runtime_state_store.set_global_ai_enabled(
            payload.enabled,
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
        )
    ).model_dump()


@router.post(
    "/accounts/{account_id}/ai",
    summary="Set account AI",
    description="Enable or disable AI for a specific account.",
    tags=["runtime"],
)
async def set_account_ai(
    account_id: str,
    payload: AiToggleRequest,
    runtime_state_store: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("settings.ai_config")),
) -> dict[str, object]:
    actor.require_account_access(account_id)
    try:
        return (
            await runtime_state_store.set_account_ai_enabled(
                account_id,
                payload.enabled,
                actor_type=actor.actor_type,
                actor_id=actor.actor_id,
            )
        ).model_dump()
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/conversations/{conversation_id}/ai",
    summary="Set conversation AI",
    description="Enable or disable AI for a specific conversation.",
    tags=["runtime"],
)
async def set_conversation_ai(
    conversation_id: str,
    account_id: str,
    payload: AiToggleRequest,
    runtime_state_store: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("conversations.handover")),
) -> dict[str, object]:
    actor.require_account_access(account_id)
    resolved_agent_id = actor.validate_agent_id(payload.agent_id)
    if resolved_agent_id is None and actor.role in {ActorRole.OPERATOR, ActorRole.SUPPORT_AGENT}:
        resolved_agent_id = actor.actor_id
    admin_override = actor.is_super_admin and not actor.allow_impersonation
    try:
        return (
            await runtime_state_store.set_conversation_ai_enabled(
                account_id,
                conversation_id,
                payload.enabled,
                agent_id=resolved_agent_id,
                actor_type=actor.actor_type,
                actor_id=actor.actor_id,
                admin_override=admin_override,
            )
        ).model_dump()
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.get(
    "/conversations/{conversation_id}/ai-status",
    summary="Get conversation AI status",
    description="Get the effective AI status for a conversation.",
    tags=["runtime"],
)
async def get_conversation_ai_status(
    conversation_id: str,
    account_id: str,
    runtime_state_store: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("runtime.view")),
) -> dict[str, object]:
    actor.require_account_access(account_id)
    try:
        status = await runtime_state_store.get_effective_ai_status(account_id, conversation_id)
    except (LookupError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ConversationAiStatusResponse.model_validate(status).model_dump()


@router.post(
    "/conversations/{conversation_id}/handover",
    summary="Set conversation handover",
    description="Handover conversation management mode between AI and human.",
    tags=["runtime"],
)
async def set_conversation_handover(
    conversation_id: str,
    account_id: str,
    payload: ConversationHandoverRequest,
    runtime_state_store: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("conversations.handover")),
) -> dict[str, object]:
    actor.require_account_access(account_id)
    resolved_agent_id = actor.validate_agent_id(payload.agent_id)
    if resolved_agent_id is None and actor.role in {ActorRole.OPERATOR, ActorRole.SUPPORT_AGENT}:
        resolved_agent_id = actor.actor_id
    # super_admin 可越过 agent 注册要求直接接管
    admin_override = actor.is_super_admin
    try:
        return (
            await runtime_state_store.set_conversation_management_mode(
                account_id,
                conversation_id,
                payload.management_mode,
                resolved_agent_id,
                payload.reason,
                actor_type=actor.actor_type,
                actor_id=actor.actor_id,
                admin_override=admin_override,
            )
        ).model_dump()
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
