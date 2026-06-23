from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_runtime_state_service, get_template_service, require_permission
from app.core.auth import ActorRole, RequestActor
from app.schemas.templates import (
    MessageTemplateView,
    TemplateCategory,
    TemplateDraftRequest,
    TemplateDraftUpdateRequest,
    TemplateSendLogView,
    TemplateSendRequest,
    TemplateSendResponse,
    TemplateSendStatus,
    TemplateStatsDailyRow,
    TemplateStatsDetailResponse,
    TemplateStatsRebuildResponse,
    TemplateStatsSummary,
    TemplateSubmitResponse,
    TemplateSyncRequest,
    TemplateSyncResponse,
    TemplateStatus,
    TemplateStatusUpdateRequest,
)
from app.services.media_asset_errors import MediaProviderConfigError, MediaProviderUpstreamError
from app.services.runtime_state import RuntimeStateStore
from app.services.template_service import TemplateService
from pydantic import BaseModel


class BatchTemplateRequest(BaseModel):
    template_ids: list[str]
    reason: str | None = None


class BatchOperationResult(BaseModel):
    template_id: str
    status: str
    error: str | None = None


class BatchOperationResponse(BaseModel):
    success_count: int
    failed_count: int
    results: list[BatchOperationResult]


router = APIRouter(prefix="/api/templates", tags=["templates"])



def _require_existing_account(
    *,
    account_id: str | None,
    actor: RequestActor,
    runtime_state: RuntimeStateStore,
) -> None:
    if account_id is None:
        return
    actor.require_account_access(account_id)
    if runtime_state.get_account_model(account_id) is None:
        raise HTTPException(status_code=404, detail=f"Account '{account_id}' was not found.")


def _raise_template_draft_value_error(exc: ValueError) -> None:
    detail = str(exc)
    status_code = 404 if "was not found." in detail else 409
    raise HTTPException(status_code=status_code, detail=detail) from exc


def _raise_template_registry_value_error(exc: ValueError) -> None:
    detail = str(exc)
    status_code = 503 if "access_token" in detail and "requires" in detail else 409
    raise HTTPException(status_code=status_code, detail=detail) from exc


def _raise_template_registry_runtime_error(exc: RuntimeError) -> None:
    raise HTTPException(status_code=502, detail=str(exc)) from exc


def _raise_template_send_value_error(exc: ValueError) -> None:
    detail = str(exc)
    if ("access_token" in detail and "requires" in detail) or "access token" in detail.lower():
        raise HTTPException(status_code=503, detail=detail) from exc
    raise HTTPException(status_code=409, detail=detail) from exc


def _resolve_rebuild_audit_scope(
    *,
    account_id: str | None,
    waba_id: str | None,
    phone_number_id: str | None,
) -> tuple[str, str]:
    if phone_number_id:
        return phone_number_id, "phone_number"
    if waba_id:
        return waba_id, "waba"
    if account_id:
        return account_id, "account"
    return "all_accounts", "all_accounts"


@router.get(
    "",
    summary="List templates",
    description="List message templates with optional filters. Supports grouping by scope for template management.",
    tags=["templates"],
)
async def list_templates(
    account_id: str | None = None,
    agency_id: str | None = Query(default=None, description="Filter by agency scope"),
    waba_id: str | None = None,
    status: TemplateStatus | None = None,
    language: str | None = None,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    template_service: TemplateService = Depends(get_template_service),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("templates.view")),
) -> dict:
    # When agency_id is specified (super admin viewing agency templates), resolve to account scope
    resolved_account_id = account_id
    if agency_id and actor.is_super_admin and account_id is None:
        # Fetch all templates that belong to accounts owned by this agency
        # For now, return all templates since account-agency mapping is at runtime level
        pass

    if resolved_account_id is not None:
        _require_existing_account(account_id=resolved_account_id, actor=actor, runtime_state=runtime_state)
        items = await template_service.list_templates(
            account_id=resolved_account_id,
            waba_id=waba_id,
            status=status,
            language=language,
        )
        return {"items": items, "total": len(items), "page": page, "size": size}

    if actor.is_super_admin:
        # Return all templates, grouped by scope for UI display
        global_items = await template_service.list_templates(
            account_id=None,
            waba_id=waba_id,
            status=status,
            language=language,
        )
        return {
            "global_templates": global_items,
            "agency_templates": [],
            "total": len(global_items),
            "page": page,
            "size": size,
        }

    templates: list[MessageTemplateView] = []
    for allowed_account_id in dict.fromkeys(actor.account_ids):
        templates.extend(
            await template_service.list_templates(
                account_id=allowed_account_id,
                waba_id=waba_id,
                status=status,
                language=language,
            )
        )
    templates.sort(key=lambda template: template.name)
    templates.sort(key=lambda template: template.created_at, reverse=True)
    return {"items": templates, "total": len(templates), "page": page, "size": size}


@router.post(
    "/drafts",
    summary="Create template draft",
    description="Create a new message template draft.",
    tags=["templates"],
)
async def create_template_draft(
    payload: TemplateDraftRequest,
    template_service: TemplateService = Depends(get_template_service),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("templates.create")),
) -> MessageTemplateView:
    _require_existing_account(account_id=payload.account_id, actor=actor, runtime_state=runtime_state)
    try:
        return await template_service.create_template_draft(
            payload,
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        _raise_template_draft_value_error(exc)


@router.patch(
    "/{template_id}/draft",
    summary="Update template draft",
    description="Update an existing message template draft.",
    tags=["templates"],
)
async def update_template_draft(
    template_id: str,
    payload: TemplateDraftUpdateRequest,
    template_service: TemplateService = Depends(get_template_service),
    actor: RequestActor = Depends(require_permission("templates.edit")),
) -> MessageTemplateView:
    try:
        return await template_service.update_template_draft(
            template_id=template_id,
            payload=payload,
            allowed_account_ids=None if actor.is_super_admin else set(actor.account_ids),
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        _raise_template_draft_value_error(exc)


@router.post(
    "/{template_id}/status",
    summary="Update template status",
    description="Update the status of a message template.",
    tags=["templates"],
)
async def update_template_status(
    template_id: str,
    payload: TemplateStatusUpdateRequest,
    template_service: TemplateService = Depends(get_template_service),
    actor: RequestActor = Depends(require_permission("templates.review")),
) -> MessageTemplateView:
    try:
        return await template_service.update_template_status(
            template_id=template_id,
            payload=payload,
            allowed_account_ids=None if actor.is_super_admin else set(actor.account_ids),
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post(
    "/{template_id}/submit",
    summary="Submit template",
    description="Submit a message template to Meta for review.",
    tags=["templates"],
)
async def submit_template(
    template_id: str,
    template_service: TemplateService = Depends(get_template_service),
    actor: RequestActor = Depends(require_permission("templates.sync_meta")),
) -> TemplateSubmitResponse:
    try:
        return await template_service.submit_template(
            template_id=template_id,
            allowed_account_ids=None if actor.is_super_admin else set(actor.account_ids),
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        _raise_template_registry_value_error(exc)
    except RuntimeError as exc:
        _raise_template_registry_runtime_error(exc)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post(
    "/sync",
    summary="Sync templates",
    description="Sync message templates from Meta for a given account.",
    tags=["templates"],
)
async def sync_templates(
    payload: TemplateSyncRequest,
    template_service: TemplateService = Depends(get_template_service),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("templates.sync_meta")),
) -> TemplateSyncResponse:
    _require_existing_account(account_id=payload.account_id, actor=actor, runtime_state=runtime_state)
    try:
        return await template_service.sync_templates(
            payload,
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
        )
    except ValueError as exc:
        _raise_template_registry_value_error(exc)
    except RuntimeError as exc:
        _raise_template_registry_runtime_error(exc)


@router.get(
    "/send-logs",
    summary="List send logs",
    description="List template send logs with optional filters.",
    tags=["templates"],
)
async def list_template_send_logs(
    account_id: str | None = None,
    waba_id: str | None = None,
    conversation_id: str | None = None,
    external_conversation_id: str | None = None,
    internal_conversation_id: str | None = None,
    template_id: str | None = None,
    phone_number_id: str | None = None,
    status: TemplateSendStatus | None = None,
    error_code: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 100,
    template_service: TemplateService = Depends(get_template_service),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("templates.view")),
) -> list[TemplateSendLogView]:
    if account_id is not None:
        _require_existing_account(account_id=account_id, actor=actor, runtime_state=runtime_state)
    if (
        conversation_id is not None
        and external_conversation_id is not None
        and conversation_id != external_conversation_id
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "conversation_id and external_conversation_id refer to the same external "
                "conversation filter and must match when both are provided."
            ),
        )
    resolved_external_conversation_id = external_conversation_id or conversation_id
    try:
        return await template_service.list_send_logs(
            account_id=account_id,
            waba_id=waba_id,
            external_conversation_id=resolved_external_conversation_id,
            internal_conversation_id=internal_conversation_id,
            template_id=template_id,
            phone_number_id=phone_number_id,
            status=status,
            error_code=error_code,
            date_from=date_from,
            date_to=date_to,
            limit=max(1, min(limit, 200)),
            allowed_account_ids=None if actor.is_super_admin else set(actor.account_ids),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/stats/summary",
    summary="Get template stats summary",
    description="Get aggregated template usage statistics.",
    tags=["templates"],
)
async def get_template_stats_summary(
    account_id: str | None = None,
    waba_id: str | None = None,
    phone_number_id: str | None = None,
    category: TemplateCategory | None = None,
    language: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    template_service: TemplateService = Depends(get_template_service),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("templates.view")),
) -> TemplateStatsSummary:
    _require_existing_account(account_id=account_id, actor=actor, runtime_state=runtime_state)
    try:
        return await template_service.get_stats_summary(
            account_id=account_id,
            waba_id=waba_id,
            phone_number_id=phone_number_id,
            category=category,
            language=language,
            date_from=date_from,
            date_to=date_to,
            allowed_account_ids=None if actor.is_super_admin else set(actor.account_ids),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/stats/rebuild",
    summary="Rebuild template stats",
    description="Rebuild template daily statistics for a date range.",
    tags=["templates"],
)
async def rebuild_template_stats(
    account_id: str | None = None,
    waba_id: str | None = None,
    phone_number_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    template_service: TemplateService = Depends(get_template_service),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("templates.rebuild_stats")),
) -> TemplateStatsRebuildResponse:
    _require_existing_account(account_id=account_id, actor=actor, runtime_state=runtime_state)
    audit_target_id, audit_scope_type = _resolve_rebuild_audit_scope(
        account_id=account_id,
        waba_id=waba_id,
        phone_number_id=phone_number_id,
    )
    try:
        rebuilt_at = await template_service.rebuild_daily_stats(
            account_id=account_id,
            waba_id=waba_id,
            phone_number_id=phone_number_id,
            date_from=date_from,
            date_to=date_to,
            allowed_account_ids=None if actor.is_super_admin else set(actor.account_ids),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    runtime_state.add_audit_log(
        account_id=account_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        action="template_stats_rebuilt",
        target_type="template_daily_stats",
        target_id=audit_target_id,
        payload={
            "scope_type": audit_scope_type,
            "waba_id": waba_id,
            "phone_number_id": phone_number_id,
            "date_from": date_from,
            "date_to": date_to,
        },
    )
    runtime_state.commit()
    return TemplateStatsRebuildResponse(
        account_id=account_id,
        waba_id=waba_id,
        phone_number_id=phone_number_id,
        date_from=date_from,
        date_to=date_to,
        rebuilt_at=rebuilt_at.isoformat(),
    )


@router.get(
    "/stats/daily",
    summary="List template daily stats",
    description="List daily template usage statistics.",
    tags=["templates"],
)
async def list_template_daily_stats(
    account_id: str | None = None,
    waba_id: str | None = None,
    phone_number_id: str | None = None,
    category: TemplateCategory | None = None,
    language: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    template_service: TemplateService = Depends(get_template_service),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("templates.view")),
) -> list[TemplateStatsDailyRow]:
    _require_existing_account(account_id=account_id, actor=actor, runtime_state=runtime_state)
    try:
        return await template_service.list_daily_stats(
            account_id=account_id,
            waba_id=waba_id,
            phone_number_id=phone_number_id,
            category=category,
            language=language,
            date_from=date_from,
            date_to=date_to,
            allowed_account_ids=None if actor.is_super_admin else set(actor.account_ids),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/{template_id}/analytics",
    summary="Get template analytics",
    description="Get detailed analytics for a specific message template.",
    tags=["templates"],
)
async def get_template_analytics(
    template_id: str,
    waba_id: str | None = None,
    phone_number_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    template_service: TemplateService = Depends(get_template_service),
    actor: RequestActor = Depends(require_permission("templates.view")),
) -> TemplateStatsDetailResponse:
    try:
        return await template_service.get_template_analytics(
            template_id=template_id,
            waba_id=waba_id,
            phone_number_id=phone_number_id,
            date_from=date_from,
            date_to=date_to,
            allowed_account_ids=None if actor.is_super_admin else set(actor.account_ids),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/{template_id}/send",
    summary="Send template",
    description="Send a message template to a customer.",
    tags=["templates"],
)
async def send_template(
    template_id: str,
    payload: TemplateSendRequest,
    template_service: TemplateService = Depends(get_template_service),
    actor: RequestActor = Depends(require_permission("templates.send")),
) -> TemplateSendResponse:
    actor.require_account_access(payload.account_id)
    resolved_agent_id = actor.validate_agent_id(payload.agent_id)
    if (
        resolved_agent_id is None
        and actor.role in {ActorRole.OPERATOR, ActorRole.SUPPORT_AGENT}
    ):
        resolved_agent_id = actor.actor_id
    resolved_payload = payload.model_copy(update={"agent_id": resolved_agent_id})
    try:
        return await template_service.send_template(
            template_id=template_id,
            payload=resolved_payload,
            allowed_account_ids=None if actor.is_super_admin else set(actor.account_ids),
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
        _raise_template_send_value_error(exc)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post(
    "/batch-approve",
    summary="Batch approve templates",
    description="Approve multiple template statuses. Independent transactions.",
    tags=["templates"],
)
async def batch_approve_templates(
    payload: BatchTemplateRequest,
    template_service: TemplateService = Depends(get_template_service),
    actor: RequestActor = Depends(require_permission("templates.review")),
) -> BatchOperationResponse:
    results: list[BatchOperationResult] = []
    for tid in payload.template_ids:
        try:
            template = await template_service.update_template_status(
                template_id=tid,
                payload=TemplateStatusUpdateRequest(status=TemplateStatus.APPROVED, reject_reason=None),
                allowed_account_ids=None if actor.is_super_admin else set(actor.account_ids),
                actor_type=actor.actor_type,
                actor_id=actor.actor_id,
            )
            results.append(BatchOperationResult(template_id=tid, status="success"))
        except Exception as exc:
            results.append(BatchOperationResult(template_id=tid, status="failed", error=str(exc)))
    success = sum(1 for r in results if r.status == "success")
    return BatchOperationResponse(success_count=success, failed_count=len(results) - success, results=results)


@router.post(
    "/batch-reject",
    summary="Batch reject templates",
    description="Reject multiple template statuses. Independent transactions.",
    tags=["templates"],
)
async def batch_reject_templates(
    payload: BatchTemplateRequest,
    template_service: TemplateService = Depends(get_template_service),
    actor: RequestActor = Depends(require_permission("templates.review")),
) -> BatchOperationResponse:
    results: list[BatchOperationResult] = []
    for tid in payload.template_ids:
        try:
            template = await template_service.update_template_status(
                template_id=tid,
                payload=TemplateStatusUpdateRequest(status=TemplateStatus.REJECTED, reject_reason=payload.reason),
                allowed_account_ids=None if actor.is_super_admin else set(actor.account_ids),
                actor_type=actor.actor_type,
                actor_id=actor.actor_id,
            )
            results.append(BatchOperationResult(template_id=tid, status="success"))
        except Exception as exc:
            results.append(BatchOperationResult(template_id=tid, status="failed", error=str(exc)))
    success = sum(1 for r in results if r.status == "success")
    return BatchOperationResponse(success_count=success, failed_count=len(results) - success, results=results)


@router.post(
    "/batch-delete",
    summary="Batch delete templates",
    description="Delete multiple templates. Independent transactions.",
    tags=["templates"],
)
async def batch_delete_templates(
    payload: BatchTemplateRequest,
    template_service: TemplateService = Depends(get_template_service),
    actor: RequestActor = Depends(require_permission("templates.delete")),
) -> BatchOperationResponse:
    results: list[BatchOperationResult] = []
    for tid in payload.template_ids:
        try:
            template = await template_service.update_template_status(
                template_id=tid,
                payload=TemplateStatusUpdateRequest(status=TemplateStatus.DELETED, reject_reason=None),
                allowed_account_ids=None if actor.is_super_admin else set(actor.account_ids),
                actor_type=actor.actor_type,
                actor_id=actor.actor_id,
            )
            results.append(BatchOperationResult(template_id=tid, status="success"))
        except Exception as exc:
            results.append(BatchOperationResult(template_id=tid, status="failed", error=str(exc)))
    success = sum(1 for r in results if r.status == "success")
    return BatchOperationResponse(success_count=success, failed_count=len(results) - success, results=results)


@router.post(
    "/batch-sync-meta",
    summary="Batch sync templates to Meta",
    description="Sync multiple templates to Meta. Independent transactions.",
    tags=["templates"],
)
async def batch_sync_meta_templates(
    payload: BatchTemplateRequest,
    template_service: TemplateService = Depends(get_template_service),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("templates.sync_meta")),
) -> BatchOperationResponse:
    results: list[BatchOperationResult] = []
    for tid in payload.template_ids:
        try:
            template = await template_service.submit_template(
                template_id=tid,
                allowed_account_ids=None if actor.is_super_admin else set(actor.account_ids),
                actor_type=actor.actor_type,
                actor_id=actor.actor_id,
            )
            results.append(BatchOperationResult(template_id=tid, status="success"))
        except Exception as exc:
            results.append(BatchOperationResult(template_id=tid, status="failed", error=str(exc)))
    success = sum(1 for r in results if r.status == "success")
    return BatchOperationResponse(success_count=success, failed_count=len(results) - success, results=results)
