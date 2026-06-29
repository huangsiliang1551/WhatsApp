import asyncio
import json

from decimal import Decimal
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import (
    get_db_session,
    get_db_session_factory,
    get_member_task_quota_service,
    get_review_service,
    get_runtime_state_service,
    get_task_service,
    get_task_submission_service,
    require_permission,
    SessionFactory,
)
from app.core.auth import RequestActor, filter_account_scoped_items
from app.db.models import AppUser, H5Site, MemberTaskBatch, TaskProductGenerationRun
from app.schemas.tasks import (
    TaskInstanceClaimRequest,
    TaskInstanceCreateRequest,
    TaskTemplateCreateRequest,
)
from app.schemas.member_task_quota import (
    MemberTaskQuotaBatchCreateRequest,
    MemberTaskQuotaBatchPreviewResponse,
    MemberTaskQuotaCancelRequest,
    MemberTaskDayQuotaResponse,
    MemberTaskQuotaCreateRequest,
    MemberTaskQuotaPreviewRequest,
    MemberTaskQuotaPreviewResponse,
    MemberTaskQuotaPlanIssueRequest,
    MemberTaskQuotaUpdateRequest,
)
from app.schemas.audit import AuditLogEntry
from app.schemas.task_issue_plan import (
    TaskIssuePlanCreateRequest,
    TaskIssuePlanGenerateDaysRequest,
    TaskIssuePlanPreviewResponse,
    TaskIssuePlanResponse,
    TaskIssuePlanUpdateRequest,
)
from app.schemas.task_system_config import TaskSystemConfigResponse, TaskSystemConfigUpsertRequest
from app.schemas.task_monitor import (
    TaskMonitorAlertEventResponse,
    TaskAlertRuleCreateRequest,
    TaskAlertRuleResponse,
    TaskAlertRuleUpdateRequest,
    TaskMonitorQueryRowResponse,
    TaskMonitorSavedViewCreateRequest,
    TaskMonitorSavedViewResponse,
    TaskMonitorSavedViewUpdateRequest,
    TaskMonitorSummaryResponse,
)
from app.schemas.h5_member_commerce import H5TaskPackageItemPayload
from app.schemas.task_product_pool import (
    TaskProductPoolCreateRequest,
    TaskProductPoolImportRequest,
    TaskProductPoolItemsRequest,
    TaskProductPoolItemResponse,
    TaskProductPoolItemUpdateRequest,
    TaskProductPoolResponse,
    TaskProductPoolUpdateRequest,
)
from app.schemas.task_manual_add import (
    TaskManualAddLogResponse,
    TaskManualAddCandidateResponse,
    TaskGenerationRunResponse,
    TaskPackageAdminDetailResponse,
    TaskPackageAdminListItemResponse,
    TaskManualAddCreateRequest,
    TaskManualAddPreviewResponse,
    TaskPackageStatusActionRequest,
    TaskManualAddResponse,
)
from app.schemas.task_workflow import (
    TaskReviewDecisionActionRequest,
    TaskSubmissionCreateRequest,
    TaskSubmissionResponse,
)
from app.services.member_task_quota_service import MemberTaskQuotaService
from app.services.review_service import ReviewService
from app.services.runtime_state import RuntimeStateStore
from app.services.task_amount_allocation_service import TaskAmountAllocationService
from app.services.task_issue_plan_service import TaskIssuePlanService
from app.services.task_manual_add_service import TaskManualAddService
from app.services.task_monitor_service import TaskMonitorService
from app.services.task_batch_scheduler_service import TaskBatchSchedulerService
from app.services.task_product_pool_service import TaskProductPoolService
from app.services.task_submission_service import TaskSubmissionService
from app.services.task_service import TaskService
from app.services.task_system_config_service import TaskSystemConfigService

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _serialize_task_manual_add_log(log: Any) -> TaskManualAddLogResponse:
    return TaskManualAddLogResponse(
        id=log.id,
        package_id=log.package_instance_id,
        batch_id=log.batch_id,
        operator_id=log.operator_id,
        reason_text=log.reason_text,
        notify_user=log.notify_user,
        user_notice_text=log.user_notice_text,
        user_notified_at=log.user_notified_at,
        added_item_count=log.added_item_count,
        added_amount=float(log.added_amount),
        before_manual_added_amount=float(log.before_manual_added_amount),
        after_manual_added_amount=float(log.after_manual_added_amount),
        before_effective_amount=float(log.before_effective_amount),
        after_effective_amount=float(log.after_effective_amount),
        created_at=log.created_at,
    )


def _serialize_task_package_item(item: Any) -> H5TaskPackageItemPayload:
    return H5TaskPackageItemPayload(
        id=item.id,
        product_name=item.product_name,
        image_url=item.image_url,
        price=float(item.price),
        currency=item.currency,
        origin=item.item_origin,
        status=item.status,
        completed_at=item.completed_at,
        order_id=item.order_id,
    )


def _serialize_task_generation_run(
    run: TaskProductGenerationRun,
    public_user_id: str,
    site_key: str | None,
) -> TaskGenerationRunResponse:
    return TaskGenerationRunResponse(
        id=run.id,
        account_id=run.account_id,
        site_id=run.site_id,
        site_key=site_key,
        user_id=run.user_id,
        public_user_id=public_user_id,
        quota_id=run.quota_id,
        batch_id=run.batch_id,
        product_pool_id=run.product_pool_id,
        selection_algorithm=run.selection_algorithm,
        target_day_amount=float(run.target_day_amount),
        actual_day_system_amount=float(run.actual_day_system_amount),
        tolerance_amount=float(run.tolerance_amount),
        generated_package_count=run.generated_package_count,
        generated_item_count=run.generated_item_count,
        status=run.status,
        failure_reason=run.failure_reason,
        created_at=run.created_at,
    )


class LegacyTaskSubmissionRequest(BaseModel):
    submitted_by_user_id: str = Field(min_length=1, max_length=36)
    submission_text: str | None = Field(default=None, max_length=4000)
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    proof_file_ids: list[str] = Field(default_factory=list)
    payload_json: dict[str, Any] = Field(default_factory=dict)


class LegacyTaskReviewActionRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=64)
    comment: str | None = Field(default=None, max_length=2000)
    evidence_json: dict[str, Any] = Field(default_factory=dict)


class LegacyTaskReviewFollowUpContract(BaseModel):
    contract: Literal["completed", "appeal_or_help_only"]
    direct_resubmit_allowed: bool = False
    allowed_ticket_types: list[Literal["appeal", "help"]] = Field(default_factory=list)
    next_action: Literal["task_completed", "appeal_or_help_ticket"]
    guidance: str


class LegacyTaskReviewStatusResponse(BaseModel):
    id: str | None = None
    review_decision_id: str | None = None
    task_instance_id: str
    submission_id: str
    account_id: str | None = None
    status: Literal["approved", "rejected"]
    decision: Literal["approved", "rejected"]
    reason_code: str | None = None
    reason_text: str | None = None
    direct_resubmit_allowed: bool = False
    next_action: Literal["task_completed", "appeal_or_help_ticket"]
    next_action_hint: str
    follow_up_contract: LegacyTaskReviewFollowUpContract


def _resolve_public_user_id(session: Session, submitted_by_user_id: str) -> str:
    public_user_id = session.scalar(
        select(AppUser.public_user_id).where(AppUser.id == submitted_by_user_id)
    )
    if public_user_id is None:
        raise LookupError(f"User '{submitted_by_user_id}' was not found.")
    return public_user_id


def _build_submission_payload(
    session: Session,
    payload: LegacyTaskSubmissionRequest,
) -> TaskSubmissionCreateRequest:
    payload_json = dict(payload.payload_json)
    if payload.submission_text is not None:
        payload_json.setdefault("submission_text", payload.submission_text)
    if payload.attachments:
        payload_json.setdefault("attachments", payload.attachments)
    return TaskSubmissionCreateRequest(
        public_user_id=_resolve_public_user_id(session, payload.submitted_by_user_id),
        proof_file_ids=payload.proof_file_ids,
        notes=payload.submission_text,
        payload_json=payload_json,
    )


def _build_review_payload(payload: LegacyTaskReviewActionRequest) -> TaskReviewDecisionActionRequest:
    return TaskReviewDecisionActionRequest(
        reason_code=payload.reason,
        reason_text=payload.comment,
        evidence_json=payload.evidence_json,
    )


def _build_legacy_review_response(
    *,
    review_decision_id: str | None,
    task_instance_id: str,
    submission_id: str,
    account_id: str | None,
    status: Literal["approved", "rejected"],
    payload: TaskReviewDecisionActionRequest,
) -> LegacyTaskReviewStatusResponse:
    follow_up_contract = _build_legacy_review_follow_up_contract(status)
    return LegacyTaskReviewStatusResponse(
        id=review_decision_id,
        review_decision_id=review_decision_id,
        task_instance_id=task_instance_id,
        submission_id=submission_id,
        account_id=account_id,
        status=status,
        decision=status,
        reason_code=payload.reason_code,
        reason_text=payload.reason_text,
        direct_resubmit_allowed=follow_up_contract.direct_resubmit_allowed,
        next_action=follow_up_contract.next_action,
        next_action_hint=follow_up_contract.guidance,
        follow_up_contract=follow_up_contract,
    )


def _build_legacy_review_follow_up_contract(
    status: Literal["approved", "rejected"],
) -> LegacyTaskReviewFollowUpContract:
    if status == "approved":
        return LegacyTaskReviewFollowUpContract(
            contract="completed",
            direct_resubmit_allowed=False,
            allowed_ticket_types=[],
            next_action="task_completed",
            guidance=(
                "Task approved. Treat this review flow as completed; no direct resubmission, appeal, "
                "or help ticket is required."
            ),
        )
    if status == "rejected":
        return LegacyTaskReviewFollowUpContract(
            contract="appeal_or_help_only",
            direct_resubmit_allowed=False,
            allowed_ticket_types=["appeal", "help"],
            next_action="appeal_or_help_ticket",
            guidance=(
                "Task rejected. Direct resubmission is not allowed; continue with an appeal ticket or "
                "a help ticket for follow-up."
            ),
        )
    raise ValueError(f"Unsupported legacy review status '{status}'.")


@router.get(
    "/system-config",
    summary="Get task system config",
    description="Get the task system configuration for an account and optional site scope.",
    tags=["tasks"],
)
async def get_task_system_config(
    account_id: str,
    site_id: str | None = None,
    session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("tasks.config.view")),
) -> TaskSystemConfigResponse:
    actor.require_account_access(account_id)
    service = TaskSystemConfigService(session)
    try:
        return service.get_config(account_id=account_id, site_id=site_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.put(
    "/system-config",
    summary="Upsert task system config",
    description="Create or update the task system configuration for an account and optional site scope.",
    tags=["tasks"],
)
async def upsert_task_system_config(
    payload: TaskSystemConfigUpsertRequest,
    session: Session = Depends(get_db_session),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("tasks.config.manage")),
) -> TaskSystemConfigResponse:
    actor.require_account_access(payload.account_id)
    service = TaskSystemConfigService(session)
    try:
        config = service.upsert_config(payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    runtime_state.add_audit_log(
        account_id=config.account_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        action="task_system_config_updated",
        target_type="task_system_config",
        target_id=config.site_id or config.account_id,
        payload={
            "site_id": config.site_id,
            "status": config.status,
            "newbie_plan_id": config.newbie_plan_id,
            "official_plan_id": config.official_plan_id,
            "max_active_batches_per_user": config.max_active_batches_per_user,
            "max_active_packages_per_user": config.max_active_packages_per_user,
        },
    )
    runtime_state.commit()
    return config


@router.patch(
    "/system-config",
    summary="Patch task system config",
    description="Compatibility alias for creating or updating the task system configuration.",
    tags=["tasks"],
)
async def patch_task_system_config(
    payload: TaskSystemConfigUpsertRequest,
    session: Session = Depends(get_db_session),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("tasks.config.manage")),
) -> TaskSystemConfigResponse:
    return await upsert_task_system_config(
        payload=payload,
        session=session,
        runtime_state=runtime_state,
        actor=actor,
    )


@router.get(
    "/system-config/audit-logs",
    summary="List task system config audit logs",
    description="List audit logs related to task system configuration updates.",
    tags=["tasks"],
)
async def list_task_system_config_audit_logs(
    account_id: str,
    site_id: str | None = None,
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("tasks.config.view")),
) -> list[dict[str, object]]:
    actor.require_account_access(account_id)
    audit_logs = await runtime_state.list_audit_logs(
        account_id=account_id,
        action="task_system_config_updated",
        target_type="task_system_config",
        target_id=site_id or account_id,
        limit=100,
        allowed_account_ids=None if actor.is_super_admin else set(actor.account_ids),
    )
    return [
        AuditLogEntry.model_validate(
            {
                "id": item.id,
                "account_id": item.account_id,
                "waba_id": runtime_state._extract_audit_waba_id(item),
                "phone_number_id": runtime_state._extract_audit_phone_number_id(item.payload),
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


@router.get(
    "/monitor-saved-views",
    summary="List task monitor saved views",
    description="List saved views for task real-time monitoring.",
    tags=["tasks"],
)
@router.get(
    "/monitor/saved-views",
    summary="List task monitor saved views",
    description="Compatibility alias for listing saved views for task real-time monitoring.",
    tags=["tasks"],
    include_in_schema=False,
)
async def list_task_monitor_saved_views(
    account_id: str | None = None,
    session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("tasks.monitor.view")),
) -> list[TaskMonitorSavedViewResponse]:
    if account_id is not None:
        actor.require_account_access(account_id)
    service = TaskMonitorService(session)
    return service.list_saved_views(account_id=account_id, owner_staff_id=actor.actor_id)


@router.post(
    "/monitor-saved-views",
    summary="Create task monitor saved view",
    description="Create a saved filter/column view for task monitoring.",
    tags=["tasks"],
)
@router.post(
    "/monitor/saved-views",
    summary="Create task monitor saved view",
    description="Compatibility alias for creating a saved filter/column view for task monitoring.",
    tags=["tasks"],
    include_in_schema=False,
)
async def create_task_monitor_saved_view(
    payload: TaskMonitorSavedViewCreateRequest,
    session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("tasks.monitor.manage_saved_view")),
) -> TaskMonitorSavedViewResponse:
    actor.require_account_access(payload.account_id)
    service = TaskMonitorService(session)
    return service.create_saved_view(payload, owner_staff_id=actor.actor_id)


@router.patch(
    "/monitor-saved-views/{saved_view_id}",
    summary="Update task monitor saved view",
    description="Update a saved filter/column view for task monitoring.",
    tags=["tasks"],
)
@router.patch(
    "/monitor/saved-views/{saved_view_id}",
    summary="Update task monitor saved view",
    description="Compatibility alias for updating a saved filter/column view for task monitoring.",
    tags=["tasks"],
    include_in_schema=False,
)
async def update_task_monitor_saved_view(
    saved_view_id: str,
    payload: TaskMonitorSavedViewUpdateRequest,
    session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("tasks.monitor.manage_saved_view")),
) -> TaskMonitorSavedViewResponse:
    service = TaskMonitorService(session)
    try:
        row = service.update_saved_view(saved_view_id, payload, owner_staff_id=actor.actor_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    actor.require_account_access(row.account_id)
    return row


@router.delete(
    "/monitor-saved-views/{saved_view_id}",
    status_code=204,
    summary="Delete task monitor saved view",
    description="Delete a saved filter/column view for task monitoring.",
    tags=["tasks"],
)
@router.delete(
    "/monitor/saved-views/{saved_view_id}",
    status_code=204,
    summary="Delete task monitor saved view",
    description="Compatibility alias for deleting a saved filter/column view for task monitoring.",
    tags=["tasks"],
    include_in_schema=False,
)
async def delete_task_monitor_saved_view(
    saved_view_id: str,
    session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("tasks.monitor.manage_saved_view")),
) -> None:
    service = TaskMonitorService(session)
    try:
        rows = service.list_saved_views(owner_staff_id=actor.actor_id)
        target = next((item for item in rows if item.id == saved_view_id), None)
        if target is None:
            raise LookupError(f"Task monitor saved view '{saved_view_id}' was not found.")
        actor.require_account_access(target.account_id)
        service.delete_saved_view(saved_view_id, owner_staff_id=actor.actor_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/alert-rules",
    summary="List task alert rules",
    description="List task monitoring alert rules.",
    tags=["tasks"],
)
@router.get(
    "/monitor/alert-rules",
    summary="List task alert rules",
    description="Compatibility alias for listing task monitoring alert rules.",
    tags=["tasks"],
    include_in_schema=False,
)
async def list_task_alert_rules(
    account_id: str | None = None,
    session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("tasks.monitor.manage_alert_rule")),
) -> list[TaskAlertRuleResponse]:
    if account_id is not None:
        actor.require_account_access(account_id)
    service = TaskMonitorService(session)
    rules = service.list_alert_rules(account_id=account_id)
    return filter_account_scoped_items(actor, rules, lambda item: item.account_id)


@router.post(
    "/alert-rules",
    summary="Create task alert rule",
    description="Create a task monitoring alert rule.",
    tags=["tasks"],
)
@router.post(
    "/monitor/alert-rules",
    summary="Create task alert rule",
    description="Compatibility alias for creating a task monitoring alert rule.",
    tags=["tasks"],
    include_in_schema=False,
)
async def create_task_alert_rule(
    payload: TaskAlertRuleCreateRequest,
    session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("tasks.monitor.manage_alert_rule")),
) -> TaskAlertRuleResponse:
    actor.require_account_access(payload.account_id)
    service = TaskMonitorService(session)
    return service.create_alert_rule(payload, created_by=actor.actor_id)


@router.get(
    "/monitor/query",
    summary="Query task monitor rows",
    description="Query task packages with monitor-oriented filters and wallet enrichments.",
    tags=["tasks"],
)
async def query_task_monitor_rows(
    account_id: str | None = None,
    user_id: str | None = None,
    user_query: str | None = None,
    status: str | None = None,
    day_planned_amount_min: Decimal | None = None,
    day_planned_amount_max: Decimal | None = None,
    day_manual_added_amount_min: Decimal | None = None,
    day_manual_added_amount_max: Decimal | None = None,
    day_effective_amount_min: Decimal | None = None,
    day_effective_amount_max: Decimal | None = None,
    planned_amount_min: Decimal | None = None,
    planned_amount_max: Decimal | None = None,
    manual_added_amount_min: Decimal | None = None,
    manual_added_amount_max: Decimal | None = None,
    effective_amount_min: Decimal | None = None,
    effective_amount_max: Decimal | None = None,
    has_manual_add: bool | None = None,
    latest_manual_add_operator_id: str | None = None,
    current_product_amount_min: Decimal | None = None,
    current_product_amount_max: Decimal | None = None,
    total_recharge_amount_min: Decimal | None = None,
    total_recharge_amount_max: Decimal | None = None,
    total_withdraw_amount_min: Decimal | None = None,
    total_withdraw_amount_max: Decimal | None = None,
    session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("tasks.monitor.view")),
) -> list[TaskMonitorQueryRowResponse]:
    if account_id is not None:
        actor.require_account_access(account_id)
    service = TaskMonitorService(session)
    items = service.query_packages(
        account_id=account_id,
        user_id=user_id,
        user_query=user_query,
        status=status,
        day_planned_amount_min=day_planned_amount_min,
        day_planned_amount_max=day_planned_amount_max,
        day_manual_added_amount_min=day_manual_added_amount_min,
        day_manual_added_amount_max=day_manual_added_amount_max,
        day_effective_amount_min=day_effective_amount_min,
        day_effective_amount_max=day_effective_amount_max,
        planned_amount_min=planned_amount_min,
        planned_amount_max=planned_amount_max,
        manual_added_amount_min=manual_added_amount_min,
        manual_added_amount_max=manual_added_amount_max,
        effective_amount_min=effective_amount_min,
        effective_amount_max=effective_amount_max,
        has_manual_add=has_manual_add,
        latest_manual_add_operator_id=latest_manual_add_operator_id,
        current_product_amount_min=current_product_amount_min,
        current_product_amount_max=current_product_amount_max,
        total_recharge_amount_min=total_recharge_amount_min,
        total_recharge_amount_max=total_recharge_amount_max,
        total_withdraw_amount_min=total_withdraw_amount_min,
        total_withdraw_amount_max=total_withdraw_amount_max,
    )
    return filter_account_scoped_items(actor, items, lambda item: item.account_id)


@router.get(
    "/monitor/summary",
    summary="Summarize task monitor rows",
    description="Summarize task monitor rows under the same filters as the monitor query API.",
    tags=["tasks"],
)
async def summarize_task_monitor_rows(
    account_id: str | None = None,
    user_id: str | None = None,
    user_query: str | None = None,
    status: str | None = None,
    day_planned_amount_min: Decimal | None = None,
    day_planned_amount_max: Decimal | None = None,
    day_manual_added_amount_min: Decimal | None = None,
    day_manual_added_amount_max: Decimal | None = None,
    day_effective_amount_min: Decimal | None = None,
    day_effective_amount_max: Decimal | None = None,
    planned_amount_min: Decimal | None = None,
    planned_amount_max: Decimal | None = None,
    manual_added_amount_min: Decimal | None = None,
    manual_added_amount_max: Decimal | None = None,
    effective_amount_min: Decimal | None = None,
    effective_amount_max: Decimal | None = None,
    has_manual_add: bool | None = None,
    latest_manual_add_operator_id: str | None = None,
    current_product_amount_min: Decimal | None = None,
    current_product_amount_max: Decimal | None = None,
    total_recharge_amount_min: Decimal | None = None,
    total_recharge_amount_max: Decimal | None = None,
    total_withdraw_amount_min: Decimal | None = None,
    total_withdraw_amount_max: Decimal | None = None,
    session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("tasks.monitor.view")),
) -> TaskMonitorSummaryResponse:
    if account_id is not None:
        actor.require_account_access(account_id)
    service = TaskMonitorService(session)
    return service.summarize_packages(
        account_id=account_id,
        user_id=user_id,
        user_query=user_query,
        status=status,
        day_planned_amount_min=day_planned_amount_min,
        day_planned_amount_max=day_planned_amount_max,
        day_manual_added_amount_min=day_manual_added_amount_min,
        day_manual_added_amount_max=day_manual_added_amount_max,
        day_effective_amount_min=day_effective_amount_min,
        day_effective_amount_max=day_effective_amount_max,
        planned_amount_min=planned_amount_min,
        planned_amount_max=planned_amount_max,
        manual_added_amount_min=manual_added_amount_min,
        manual_added_amount_max=manual_added_amount_max,
        effective_amount_min=effective_amount_min,
        effective_amount_max=effective_amount_max,
        has_manual_add=has_manual_add,
        latest_manual_add_operator_id=latest_manual_add_operator_id,
        current_product_amount_min=current_product_amount_min,
        current_product_amount_max=current_product_amount_max,
        total_recharge_amount_min=total_recharge_amount_min,
        total_recharge_amount_max=total_recharge_amount_max,
        total_withdraw_amount_min=total_withdraw_amount_min,
        total_withdraw_amount_max=total_withdraw_amount_max,
    )


@router.get(
    "/monitor/alerts",
    summary="List task monitor alert events",
    description="Evaluate active alert rules and list generated task monitor alert events.",
    tags=["tasks"],
)
async def list_task_monitor_alert_events(
    account_id: str | None = None,
    status: str | None = None,
    session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("tasks.monitor.view")),
) -> list[TaskMonitorAlertEventResponse]:
    if account_id is not None:
        actor.require_account_access(account_id)
    service = TaskMonitorService(session)
    items = service.list_alert_events(account_id=account_id, status=status)
    return filter_account_scoped_items(actor, items, lambda item: item.account_id)


@router.get(
    "/monitor/alerts/stream",
    summary="Stream task monitor alert events",
    description="Stream task monitor alert snapshots as a server-sent events feed.",
    tags=["tasks"],
)
async def stream_task_monitor_alert_events(
    request: Request,
    account_id: str | None = None,
    status: str | None = None,
    snapshot_interval_seconds: float = 3.0,
    heartbeat_interval_seconds: float = 15.0,
    max_events: int | None = None,
    session_factory: SessionFactory = Depends(get_db_session_factory),
    actor: RequestActor = Depends(require_permission("tasks.monitor.view")),
) -> StreamingResponse:
    if account_id is not None:
        actor.require_account_access(account_id)

    async def event_generator():
        last_snapshot: str | None = None
        last_snapshot_at = 0.0
        emitted_event_count = 0
        loop = asyncio.get_running_loop()
        heartbeat_interval = max(heartbeat_interval_seconds, 0.01)
        snapshot_interval = max(snapshot_interval_seconds, 0.01)

        while True:
            if await request.is_disconnected():
                break

            now = loop.time()
            should_refresh_snapshot = (
                last_snapshot is None or (now - last_snapshot_at) >= snapshot_interval
            )
            if should_refresh_snapshot:
                session = session_factory()
                try:
                    service = TaskMonitorService(session)
                    items = service.list_alert_events(account_id=account_id, status=status)
                    filtered_items = filter_account_scoped_items(actor, items, lambda item: item.account_id)
                    payload = [
                        item.model_dump(mode="json", by_alias=True)
                        for item in filtered_items
                    ]
                    snapshot = json.dumps(payload, ensure_ascii=False, default=str)
                finally:
                    session.close()

                if snapshot != last_snapshot:
                    yield f"event: snapshot\ndata: {snapshot}\n\n"
                    emitted_event_count += 1
                    last_snapshot = snapshot
                last_snapshot_at = now
            else:
                yield ": heartbeat\n\n"
                emitted_event_count += 1

            if max_events is not None and emitted_event_count >= max_events:
                break

            await asyncio.sleep(min(snapshot_interval, heartbeat_interval))

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post(
    "/monitor/alerts/{alert_event_id}/ack",
    summary="Acknowledge task monitor alert event",
    description="Acknowledge a generated task monitor alert event.",
    tags=["tasks"],
)
async def acknowledge_task_monitor_alert_event(
    alert_event_id: str,
    session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("tasks.monitor.execute_action")),
) -> TaskMonitorAlertEventResponse:
    service = TaskMonitorService(session)
    try:
        item = service.acknowledge_alert_event(alert_event_id, actor_id=actor.actor_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    actor.require_account_access(item.account_id)
    return item


@router.post(
    "/monitor/alerts/{alert_event_id}/resolve",
    summary="Resolve task monitor alert event",
    description="Resolve a generated task monitor alert event.",
    tags=["tasks"],
)
async def resolve_task_monitor_alert_event(
    alert_event_id: str,
    session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("tasks.monitor.execute_action")),
) -> TaskMonitorAlertEventResponse:
    service = TaskMonitorService(session)
    try:
        item = service.resolve_alert_event(alert_event_id, actor_id=actor.actor_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    actor.require_account_access(item.account_id)
    return item


@router.patch(
    "/alert-rules/{alert_rule_id}",
    summary="Update task alert rule",
    description="Update a task monitoring alert rule.",
    tags=["tasks"],
)
@router.patch(
    "/monitor/alert-rules/{alert_rule_id}",
    summary="Update task alert rule",
    description="Compatibility alias for updating a task monitoring alert rule.",
    tags=["tasks"],
    include_in_schema=False,
)
async def update_task_alert_rule(
    alert_rule_id: str,
    payload: TaskAlertRuleUpdateRequest,
    session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("tasks.monitor.manage_alert_rule")),
) -> TaskAlertRuleResponse:
    service = TaskMonitorService(session)
    existing_rules = service.list_alert_rules()
    existing = next((item for item in existing_rules if item.id == alert_rule_id), None)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"Task alert rule '{alert_rule_id}' was not found.")
    actor.require_account_access(existing.account_id)
    return service.update_alert_rule(alert_rule_id, payload)


@router.delete(
    "/alert-rules/{alert_rule_id}",
    status_code=204,
    summary="Delete task alert rule",
    description="Delete a task monitoring alert rule.",
    tags=["tasks"],
)
@router.delete(
    "/monitor/alert-rules/{alert_rule_id}",
    status_code=204,
    summary="Delete task alert rule",
    description="Compatibility alias for deleting a task monitoring alert rule.",
    tags=["tasks"],
    include_in_schema=False,
)
async def delete_task_alert_rule(
    alert_rule_id: str,
    session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("tasks.monitor.manage_alert_rule")),
) -> None:
    service = TaskMonitorService(session)
    existing_rules = service.list_alert_rules()
    existing = next((item for item in existing_rules if item.id == alert_rule_id), None)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"Task alert rule '{alert_rule_id}' was not found.")
    actor.require_account_access(existing.account_id)
    service.delete_alert_rule(alert_rule_id)


@router.get(
    "/issue-plans",
    summary="List task issue plans",
    description="List task issue plans with optional filters.",
    tags=["tasks"],
)
async def list_task_issue_plans(
    account_id: str | None = None,
    site_id: str | None = None,
    status: str | None = None,
    session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("tasks.issue_plan.view")),
) -> list[TaskIssuePlanResponse]:
    if account_id is not None:
        actor.require_account_access(account_id)
    service = TaskIssuePlanService(session)
    plans = service.list_plans(account_id=account_id, site_id=site_id, status=status)
    return filter_account_scoped_items(actor, plans, lambda item: item.account_id)


@router.post(
    "/issue-plans",
    summary="Create task issue plan",
    description="Create a task issue plan with optional day rules.",
    tags=["tasks"],
)
async def create_task_issue_plan(
    payload: TaskIssuePlanCreateRequest,
    session: Session = Depends(get_db_session),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("tasks.issue_plan.manage")),
) -> TaskIssuePlanResponse:
    actor.require_account_access(payload.account_id)
    service = TaskIssuePlanService(session)
    try:
        plan = service.create_plan(payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    runtime_state.add_audit_log(
        account_id=plan.account_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        action="task_issue_plan_created",
        target_type="task_issue_plan",
        target_id=plan.id,
        payload={
            "site_id": plan.site_id,
            "plan_type": plan.plan_type,
            "status": plan.status,
            "day_rule_count": len(plan.day_rules),
        },
    )
    runtime_state.commit()
    return plan


@router.get(
    "/issue-plans/{plan_id}",
    summary="Get task issue plan detail",
    description="Fetch a single task issue plan by id.",
    tags=["tasks"],
)
async def get_task_issue_plan(
    plan_id: str,
    session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("tasks.issue_plan.view")),
) -> TaskIssuePlanResponse:
    service = TaskIssuePlanService(session)
    try:
        plan = service.get_plan(plan_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    actor.require_account_access(plan.account_id)
    return plan


@router.patch(
    "/issue-plans/{plan_id}",
    summary="Update task issue plan",
    description="Update an existing task issue plan and optional day rules.",
    tags=["tasks"],
)
async def update_task_issue_plan(
    plan_id: str,
    payload: TaskIssuePlanUpdateRequest,
    session: Session = Depends(get_db_session),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("tasks.issue_plan.manage")),
) -> TaskIssuePlanResponse:
    service = TaskIssuePlanService(session)
    try:
        existing = service.get_plan(plan_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    actor.require_account_access(existing.account_id)
    try:
        plan = service.update_plan(plan_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    runtime_state.add_audit_log(
        account_id=plan.account_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        action="task_issue_plan_updated",
        target_type="task_issue_plan",
        target_id=plan.id,
        payload={
            "site_id": plan.site_id,
            "plan_type": plan.plan_type,
            "status": plan.status,
            "day_rule_count": len(plan.day_rules),
        },
    )
    runtime_state.commit()
    return plan


@router.post(
    "/issue-plans/{plan_id}/enable",
    summary="Enable task issue plan",
    description="Set a task issue plan to active status.",
    tags=["tasks"],
)
async def enable_task_issue_plan(
    plan_id: str,
    session: Session = Depends(get_db_session),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("tasks.issue_plan.enable")),
) -> TaskIssuePlanResponse:
    service = TaskIssuePlanService(session)
    try:
        existing = service.get_plan(plan_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    actor.require_account_access(existing.account_id)
    plan = service.set_plan_status(plan_id, "active")
    runtime_state.add_audit_log(
        account_id=plan.account_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        action="task_issue_plan_enabled",
        target_type="task_issue_plan",
        target_id=plan.id,
        payload={"status": plan.status},
    )
    runtime_state.commit()
    return plan


@router.post(
    "/issue-plans/{plan_id}/disable",
    summary="Disable task issue plan",
    description="Set a task issue plan to disabled status.",
    tags=["tasks"],
)
async def disable_task_issue_plan(
    plan_id: str,
    session: Session = Depends(get_db_session),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("tasks.issue_plan.enable")),
) -> TaskIssuePlanResponse:
    service = TaskIssuePlanService(session)
    try:
        existing = service.get_plan(plan_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    actor.require_account_access(existing.account_id)
    plan = service.set_plan_status(plan_id, "disabled")
    runtime_state.add_audit_log(
        account_id=plan.account_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        action="task_issue_plan_disabled",
        target_type="task_issue_plan",
        target_id=plan.id,
        payload={"status": plan.status},
    )
    runtime_state.commit()
    return plan


@router.post(
    "/issue-plans/{plan_id}/preview",
    summary="Preview generated task issue plan days",
    description="Preview resolved day rules for a day range without persisting them.",
    tags=["tasks"],
)
async def preview_task_issue_plan_days(
    plan_id: str,
    payload: TaskIssuePlanGenerateDaysRequest,
    session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("tasks.issue_plan.view")),
) -> TaskIssuePlanPreviewResponse:
    service = TaskIssuePlanService(session)
    try:
        existing = service.get_plan(plan_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    actor.require_account_access(existing.account_id)
    try:
        return service.preview_days(plan_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post(
    "/issue-plans/{plan_id}/generate-days",
    summary="Generate task issue plan day rules",
    description="Persist generated day rules for a day range based on the plan growth strategy.",
    tags=["tasks"],
)
async def generate_task_issue_plan_days(
    plan_id: str,
    payload: TaskIssuePlanGenerateDaysRequest,
    session: Session = Depends(get_db_session),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("tasks.issue_plan.manage")),
) -> TaskIssuePlanResponse:
    service = TaskIssuePlanService(session)
    try:
        existing = service.get_plan(plan_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    actor.require_account_access(existing.account_id)
    try:
        plan = service.generate_days(plan_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    runtime_state.add_audit_log(
        account_id=plan.account_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        action="task_issue_plan_days_generated",
        target_type="task_issue_plan",
        target_id=plan.id,
        payload={
            "start_day_no": payload.start_day_no,
            "end_day_no": payload.end_day_no,
            "day_rule_count": len(plan.day_rules),
        },
    )
    runtime_state.commit()
    return plan


@router.get(
    "/generation-runs",
    summary="List task product generation runs",
    description="List task product generation runs for monitoring and troubleshooting.",
    tags=["tasks"],
)
async def list_task_generation_runs(
    account_id: str | None = None,
    user_id: str | None = None,
    status: str | None = None,
    session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("tasks.instance.view")),
) -> list[TaskGenerationRunResponse]:
    if account_id is not None:
        actor.require_account_access(account_id)

    stmt = (
        select(TaskProductGenerationRun, AppUser.public_user_id, H5Site.site_key)
        .join(AppUser, AppUser.id == TaskProductGenerationRun.user_id)
        .join(H5Site, H5Site.id == TaskProductGenerationRun.site_id, isouter=True)
        .order_by(TaskProductGenerationRun.created_at.desc())
    )
    if account_id is not None:
        stmt = stmt.where(TaskProductGenerationRun.account_id == account_id)
    if user_id is not None:
        stmt = stmt.where(TaskProductGenerationRun.user_id == user_id)
    if status is not None:
        stmt = stmt.where(TaskProductGenerationRun.status == status)

    rows = session.execute(stmt).all()
    items: list[TaskGenerationRunResponse] = []
    for run, public_user_id, site_key in rows:
        items.append(_serialize_task_generation_run(run, public_user_id, site_key))
    return filter_account_scoped_items(actor, items, lambda item: item.account_id)


@router.post(
    "/member-day-quotas/{quota_id}/generate-batch",
    summary="Generate task batch for a quota",
    description="Explicitly generate the member task batch/packages for a locked quota from the admin side.",
    tags=["tasks"],
)
async def generate_task_batch_for_quota(
    quota_id: str,
    session: Session = Depends(get_db_session),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("tasks.quota.update")),
) -> TaskGenerationRunResponse:
    quota_service = MemberTaskQuotaService(session)
    try:
        quota = quota_service.get_quota(quota_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    actor.require_account_access(quota.account_id)

    scheduler = TaskBatchSchedulerService(session)
    try:
        run = scheduler.generate_batch_for_quota(
            quota_id=quota_id,
            requested_by=actor.actor_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    runtime_state.add_audit_log(
        account_id=run.account_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        action="member_task_batch_generated",
        target_type="member_task_day_quota",
        target_id=quota_id,
        payload={"run_id": run.id},
    )
    runtime_state.commit()

    public_user_id, site_key = session.execute(
        select(AppUser.public_user_id, H5Site.site_key)
        .join(H5Site, H5Site.id == run.site_id, isouter=True)
        .where(AppUser.id == run.user_id)
        .limit(1)
    ).one()
    return _serialize_task_generation_run(run, public_user_id, site_key)


@router.post(
    "/generation-runs/{run_id}/retry",
    summary="Retry a failed task generation run",
    description="Retry task product generation for a previously failed generation run.",
    tags=["tasks"],
)
async def retry_task_generation_run(
    run_id: str,
    session: Session = Depends(get_db_session),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("tasks.quota.update")),
) -> TaskGenerationRunResponse:
    scheduler = TaskBatchSchedulerService(session)
    try:
        existing_run = scheduler.get_run(run_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    actor.require_account_access(existing_run.account_id)

    try:
        run = scheduler.retry_generation_run(
            run_id=run_id,
            requested_by=actor.actor_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    runtime_state.add_audit_log(
        account_id=run.account_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        action="task_generation_run_retried",
        target_type="task_product_generation_run",
        target_id=run_id,
        payload={"result_run_id": run.id},
    )
    runtime_state.commit()

    public_user_id, site_key = session.execute(
        select(AppUser.public_user_id, H5Site.site_key)
        .join(H5Site, H5Site.id == run.site_id, isouter=True)
        .where(AppUser.id == run.user_id)
        .limit(1)
    ).one()
    return _serialize_task_generation_run(run, public_user_id, site_key)


@router.post(
    "/member-day-quotas/preview-allocation",
    summary="Preview member task day quota allocation",
    description="Preview package amount allocation before saving a task quota.",
    tags=["tasks"],
)
@router.post(
    "/quotas/preview",
    summary="Preview member task day quota allocation",
    description="Preview package amount allocation before saving a task quota.",
    tags=["tasks"],
)
async def preview_member_task_day_quota(
    payload: MemberTaskQuotaPreviewRequest,
    _actor: RequestActor = Depends(require_permission("tasks.quota.create")),
) -> MemberTaskQuotaPreviewResponse:
    try:
        amounts = TaskAmountAllocationService.allocate(
            mode=payload.amount_allocation_mode,
            package_count=payload.package_count,
            day_total_amount=payload.day_total_amount,
            manual_amounts=payload.package_amounts,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return MemberTaskQuotaPreviewResponse(
        package_amounts=[str(amount) for amount in amounts],
        computed_total_amount=sum(amounts),
    )


@router.get(
    "/member-day-quotas",
    summary="List member task day quotas",
    description="List task day quotas with optional filters.",
    tags=["tasks"],
)
@router.get(
    "/quotas",
    summary="List member task day quotas",
    description="List task day quotas with optional filters.",
    tags=["tasks"],
)
async def list_member_task_day_quotas(
    account_id: str | None = None,
    user_id: str | None = None,
    plan_id: str | None = None,
    day_no: int | None = None,
    quota_service: MemberTaskQuotaService = Depends(get_member_task_quota_service),
    actor: RequestActor = Depends(require_permission("tasks.quota.view")),
) -> list[MemberTaskDayQuotaResponse]:
    if account_id is not None:
        actor.require_account_access(account_id)
    quotas = quota_service.list_quotas(
        account_id=account_id,
        user_id=user_id,
        plan_id=plan_id,
        day_no=day_no,
    )
    return filter_account_scoped_items(actor, quotas, lambda item: item.account_id)


@router.post(
    "/member-day-quotas",
    summary="Create member task day quota",
    description="Create a manual member task day quota.",
    tags=["tasks"],
)
@router.post(
    "/quotas",
    summary="Create member task day quota",
    description="Create a manual member task day quota.",
    tags=["tasks"],
)
async def create_member_task_day_quota(
    payload: MemberTaskQuotaCreateRequest,
    quota_service: MemberTaskQuotaService = Depends(get_member_task_quota_service),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("tasks.quota.create")),
) -> MemberTaskDayQuotaResponse:
    actor.require_account_access(payload.account_id)
    try:
        quota = quota_service.create_quota(payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    runtime_state.add_audit_log(
        account_id=quota.account_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        action="member_task_day_quota_created",
        target_type="member_task_day_quota",
        target_id=quota.id,
        payload={
            "user_id": quota.user_id,
            "plan_id": quota.plan_id,
            "day_no": quota.day_no,
            "package_count": quota.package_count,
            "day_total_amount": str(quota.day_total_amount),
        },
    )
    runtime_state.commit()
    return quota


@router.post(
    "/member-day-quotas/batch-preview",
    summary="Preview batch member task day quotas",
    description="Preview the aggregated impact before batch-creating task day quotas.",
    tags=["tasks"],
)
@router.post(
    "/quotas/batch-preview",
    summary="Preview batch member task day quotas",
    description="Preview the aggregated impact before batch-creating task day quotas.",
    tags=["tasks"],
)
async def preview_batch_member_task_day_quotas(
    payload: MemberTaskQuotaBatchCreateRequest,
    quota_service: MemberTaskQuotaService = Depends(get_member_task_quota_service),
    actor: RequestActor = Depends(require_permission("tasks.quota.batch_create")),
) -> MemberTaskQuotaBatchPreviewResponse:
    if payload.items:
        for item in payload.items:
            actor.require_account_access(item.account_id)
    elif payload.account_id is not None:
        actor.require_account_access(payload.account_id)
    try:
        return quota_service.preview_batch_create_quotas(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post(
    "/member-day-quotas/batch-create",
    summary="Batch create member task day quotas",
    description="Create multiple manual member task day quotas in a single request.",
    tags=["tasks"],
)
async def batch_create_member_task_day_quotas(
    payload: MemberTaskQuotaBatchCreateRequest,
    quota_service: MemberTaskQuotaService = Depends(get_member_task_quota_service),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("tasks.quota.batch_create")),
) -> list[MemberTaskDayQuotaResponse]:
    if payload.items:
        for item in payload.items:
            actor.require_account_access(item.account_id)
    elif payload.account_id is not None:
        actor.require_account_access(payload.account_id)
    try:
        quotas = quota_service.batch_create_quotas(payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    for quota in quotas:
        runtime_state.add_audit_log(
            account_id=quota.account_id,
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
            action="member_task_day_quota_created",
            target_type="member_task_day_quota",
            target_id=quota.id,
            payload={
                "user_id": quota.user_id,
                "plan_id": quota.plan_id,
                "day_no": quota.day_no,
                "package_count": quota.package_count,
                "day_total_amount": str(quota.day_total_amount),
                "batch_create": True,
            },
        )
    runtime_state.commit()
    return quotas


@router.get(
    "/member-day-quotas/{quota_id}",
    summary="Get member task day quota detail",
    description="Fetch a single task day quota by id.",
    tags=["tasks"],
)
async def get_member_task_day_quota(
    quota_id: str,
    quota_service: MemberTaskQuotaService = Depends(get_member_task_quota_service),
    actor: RequestActor = Depends(require_permission("tasks.quota.view")),
) -> MemberTaskDayQuotaResponse:
    try:
        quota = quota_service.get_quota(quota_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    actor.require_account_access(quota.account_id)
    return quota


@router.patch(
    "/member-day-quotas/{quota_id}",
    summary="Update member task day quota",
    description="Update a mutable pending task day quota.",
    tags=["tasks"],
)
async def update_member_task_day_quota(
    quota_id: str,
    payload: MemberTaskQuotaUpdateRequest,
    quota_service: MemberTaskQuotaService = Depends(get_member_task_quota_service),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("tasks.quota.update")),
) -> MemberTaskDayQuotaResponse:
    try:
        existing = quota_service.get_quota(quota_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    actor.require_account_access(existing.account_id)
    try:
        quota = quota_service.update_quota(quota_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    runtime_state.add_audit_log(
        account_id=quota.account_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        action="member_task_day_quota_updated",
        target_type="member_task_day_quota",
        target_id=quota.id,
        payload={"day_no": quota.day_no, "plan_id": quota.plan_id},
    )
    runtime_state.commit()
    return quota


@router.post(
    "/member-day-quotas/{quota_id}/cancel",
    summary="Cancel member task day quota",
    description="Cancel a pending task day quota before it is issued.",
    tags=["tasks"],
)
async def cancel_member_task_day_quota(
    quota_id: str,
    payload: MemberTaskQuotaCancelRequest,
    quota_service: MemberTaskQuotaService = Depends(get_member_task_quota_service),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("tasks.quota.cancel")),
) -> MemberTaskDayQuotaResponse:
    try:
        existing = quota_service.get_quota(quota_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    actor.require_account_access(existing.account_id)
    try:
        quota = quota_service.cancel_quota(quota_id, payload, cancelled_by=actor.actor_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    runtime_state.add_audit_log(
        account_id=quota.account_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        action="member_task_day_quota_cancelled",
        target_type="member_task_day_quota",
        target_id=quota.id,
        payload={"reason": payload.reason},
    )
    runtime_state.commit()
    return quota


@router.post(
    "/quotas/issue-from-plan",
    summary="Issue member task day quota from plan",
    description="Create a member task day quota using a task issue plan and day rule.",
    tags=["tasks"],
)
async def issue_member_task_day_quota_from_plan(
    payload: MemberTaskQuotaPlanIssueRequest,
    quota_service: MemberTaskQuotaService = Depends(get_member_task_quota_service),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("tasks.quota.create")),
) -> MemberTaskDayQuotaResponse:
    try:
        plan = quota_service._require_plan(payload.plan_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    actor.require_account_access(plan.account_id)
    try:
        quota = quota_service.issue_quota_from_plan(payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    runtime_state.add_audit_log(
        account_id=quota.account_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        action="member_task_day_quota_issued_from_plan",
        target_type="member_task_day_quota",
        target_id=quota.id,
        payload={
            "user_id": quota.user_id,
            "plan_id": quota.plan_id,
            "day_no": quota.day_no,
        },
    )
    runtime_state.commit()
    return quota


@router.get(
    "/product-pools",
    summary="List task product pools",
    description="List task product pools with optional filters.",
    tags=["tasks"],
)
async def list_task_product_pools(
    account_id: str | None = None,
    site_id: str | None = None,
    status: str | None = None,
    session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("tasks.product_pool.view")),
) -> list[TaskProductPoolResponse]:
    if account_id is not None:
        actor.require_account_access(account_id)
    service = TaskProductPoolService(session)
    pools = service.list_pools(account_id=account_id, site_id=site_id, status=status)
    return filter_account_scoped_items(actor, pools, lambda item: item.account_id)


@router.post(
    "/product-pools",
    summary="Create task product pool",
    description="Create a task product pool and optional pool items.",
    tags=["tasks"],
)
async def create_task_product_pool(
    payload: TaskProductPoolCreateRequest,
    session: Session = Depends(get_db_session),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("tasks.product_pool.manage")),
) -> TaskProductPoolResponse:
    actor.require_account_access(payload.account_id)
    service = TaskProductPoolService(session)
    try:
        pool = service.create_pool(payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    runtime_state.add_audit_log(
        account_id=pool.account_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        action="task_product_pool_created",
        target_type="task_product_pool",
        target_id=pool.id,
        payload={
            "site_id": pool.site_id,
            "pool_type": pool.pool_type,
            "status": pool.status,
            "item_count": len(pool.items),
        },
    )
    runtime_state.commit()
    return pool


@router.get(
    "/product-pools/{pool_id}",
    summary="Get task product pool detail",
    description="Fetch a single task product pool with its items.",
    tags=["tasks"],
)
async def get_task_product_pool(
    pool_id: str,
    session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("tasks.product_pool.view")),
) -> TaskProductPoolResponse:
    service = TaskProductPoolService(session)
    try:
        pool = service.get_pool(pool_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    actor.require_account_access(pool.account_id)
    return pool


@router.patch(
    "/product-pools/{pool_id}",
    summary="Update task product pool",
    description="Update a task product pool base configuration.",
    tags=["tasks"],
)
async def update_task_product_pool(
    pool_id: str,
    payload: TaskProductPoolUpdateRequest,
    session: Session = Depends(get_db_session),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("tasks.product_pool.manage")),
) -> TaskProductPoolResponse:
    service = TaskProductPoolService(session)
    try:
        pool = service.get_pool(pool_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    actor.require_account_access(pool.account_id)
    try:
        updated = service.update_pool(pool_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    runtime_state.add_audit_log(
        account_id=updated.account_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        action="task_product_pool_updated",
        target_type="task_product_pool",
        target_id=updated.id,
        payload={
            "site_id": updated.site_id,
            "pool_type": updated.pool_type,
            "status": updated.status,
            "item_count": len(updated.items),
        },
    )
    runtime_state.commit()
    return updated


@router.post(
    "/product-pools/{pool_id}/items",
    summary="Add items to task product pool",
    description="Append product items into a task product pool.",
    tags=["tasks"],
)
async def add_task_product_pool_items(
    pool_id: str,
    payload: TaskProductPoolItemsRequest,
    session: Session = Depends(get_db_session),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("tasks.product_pool.manage")),
) -> TaskProductPoolResponse:
    service = TaskProductPoolService(session)
    try:
        pool = service.get_pool(pool_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    actor.require_account_access(pool.account_id)
    try:
        updated = service.add_items(pool_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    runtime_state.add_audit_log(
        account_id=updated.account_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        action="task_product_pool_items_added",
        target_type="task_product_pool",
        target_id=updated.id,
        payload={
            "added_item_count": len(payload.items),
            "item_count": len(updated.items),
        },
    )
    runtime_state.commit()
    return updated


@router.post(
    "/product-pools/{pool_id}/import",
    summary="Import task product pool items",
    description="Bulk import product items into a task product pool, with optional replace behavior.",
    tags=["tasks"],
)
async def import_task_product_pool_items(
    pool_id: str,
    payload: TaskProductPoolImportRequest,
    session: Session = Depends(get_db_session),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("tasks.product_pool.manage")),
) -> TaskProductPoolResponse:
    service = TaskProductPoolService(session)
    try:
        pool = service.get_pool(pool_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    actor.require_account_access(pool.account_id)
    try:
        updated = service.import_items(pool_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    runtime_state.add_audit_log(
        account_id=updated.account_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        action="task_product_pool_items_imported",
        target_type="task_product_pool",
        target_id=updated.id,
        payload={
            "replace_existing": payload.replace_existing,
            "import_item_count": len(payload.items),
            "item_count": len(updated.items),
        },
    )
    runtime_state.commit()
    return updated


@router.patch(
    "/product-pool-items/{item_id}",
    summary="Update task product pool item",
    description="Update a single product item within a task product pool.",
    tags=["tasks"],
)
async def update_task_product_pool_item(
    item_id: str,
    payload: TaskProductPoolItemUpdateRequest,
    session: Session = Depends(get_db_session),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("tasks.product_pool.manage")),
) -> TaskProductPoolItemResponse:
    service = TaskProductPoolService(session)
    try:
        item = service._require_pool_item(item_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    actor.require_account_access(item.account_id)
    account_id = item.account_id
    pool_id = item.pool_id
    try:
        updated = service.update_pool_item(item_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    runtime_state.add_audit_log(
        account_id=account_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        action="task_product_pool_item_updated",
        target_type="task_product_pool_item",
        target_id=updated.id,
        payload={
            "pool_id": pool_id,
            "product_id": updated.product_id,
            "status": updated.status,
        },
    )
    runtime_state.commit()
    return updated


@router.delete(
    "/product-pool-items/{item_id}",
    status_code=204,
    summary="Delete task product pool item",
    description="Delete a single product item from a task product pool.",
    tags=["tasks"],
)
async def delete_task_product_pool_item(
    item_id: str,
    session: Session = Depends(get_db_session),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("tasks.product_pool.manage")),
) -> None:
    service = TaskProductPoolService(session)
    try:
        item = service._require_pool_item(item_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    actor.require_account_access(item.account_id)
    account_id = item.account_id
    pool_id = item.pool_id
    product_id = item.product_id
    service.delete_pool_item(item_id)
    runtime_state.add_audit_log(
        account_id=account_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        action="task_product_pool_item_deleted",
        target_type="task_product_pool_item",
        target_id=item_id,
        payload={
            "pool_id": pool_id,
            "product_id": product_id,
        },
    )
    runtime_state.commit()


@router.get(
    "/templates",
    summary="List task templates",
    description="List task templates with optional filters.",
    tags=["tasks"],
)
async def list_task_templates(
    account_id: str | None = None,
    status: str | None = None,
    task_type: str | None = None,
    task_service: TaskService = Depends(get_task_service),
    actor: RequestActor = Depends(require_permission("tasks.view")),
) -> list[dict[str, object]]:
    if account_id is not None:
        actor.require_account_access(account_id)
    items = await task_service.list_task_templates(
        status=status,
        task_type=task_type,
        account_id=account_id,
    )
    return [
        item.model_dump(mode="json")
        for item in filter_account_scoped_items(actor, items, lambda item: item.account_id)
    ]


@router.post(
    "/templates",
    summary="Create task template",
    description="Create a new task template.",
    tags=["tasks"],
)
async def create_task_template(
    payload: TaskTemplateCreateRequest,
    task_service: TaskService = Depends(get_task_service),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("tasks.create")),
) -> dict[str, object]:
    actor.require_account_access(task_service.resolve_create_template_account_id(payload))
    try:
        template = await task_service.create_task_template(payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    runtime_state.add_audit_log(
        account_id=template.account_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        action="task_template_created",
        target_type="task_template",
        target_id=template.task_key,
        payload={
            "task_type": template.task_type,
            "status": template.status,
            "audience_rule_set_id": template.audience_rule_set_id,
        },
    )
    runtime_state.commit()
    return template.model_dump(mode="json")


@router.get(
    "/instances",
    summary="List task instances",
    description="List task instances with optional filters.",
    tags=["tasks"],
)
async def list_task_instances(
    account_id: str | None = None,
    status: str | None = None,
    template_id: str | None = None,
    user_id: str | None = None,
    task_service: TaskService = Depends(get_task_service),
    actor: RequestActor = Depends(require_permission("tasks.view")),
) -> list[dict[str, object]]:
    if account_id is not None:
        actor.require_account_access(account_id)
    items = await task_service.list_task_instances(
        status=status,
        template_id=template_id,
        user_id=user_id,
        account_id=account_id,
    )
    return [
        item.model_dump(mode="json")
        for item in filter_account_scoped_items(actor, items, lambda item: item.account_id)
    ]


@router.post(
    "/instances",
    summary="Create task instance",
    description="Create a new task instance from a template.",
    tags=["tasks"],
)
async def create_task_instance(
    payload: TaskInstanceCreateRequest,
    task_service: TaskService = Depends(get_task_service),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("tasks.push")),
) -> dict[str, object]:
    try:
        actor.require_account_access(await task_service.resolve_create_instance_account_id(payload))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    try:
        instance = await task_service.create_task_instance(payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    runtime_state.add_audit_log(
        account_id=instance.account_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        action="task_instance_created",
        target_type="task_instance",
        target_id=instance.id,
        payload={
            "task_key": instance.template_task_key,
            "public_user_id": instance.public_user_id,
            "status": instance.status,
        },
    )
    runtime_state.commit()
    return instance.model_dump(mode="json")


@router.post(
    "/instances/{task_instance_id}/claim",
    summary="Claim task instance",
    description="Claim a task instance for processing.",
    tags=["tasks"],
)
async def claim_task_instance(
    task_instance_id: str,
    payload: TaskInstanceClaimRequest,
    task_service: TaskService = Depends(get_task_service),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("tasks.claim")),
) -> dict[str, object]:
    _ = payload
    try:
        actor.require_account_access(await task_service.resolve_task_instance_account_id(task_instance_id))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        instance = await task_service.claim_task_instance(task_instance_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    runtime_state.add_audit_log(
        account_id=instance.account_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        action="task_instance_claimed",
        target_type="task_instance",
        target_id=instance.id,
        payload={
            "task_key": instance.template_task_key,
            "public_user_id": instance.public_user_id,
            "claim_deadline_at": instance.claim_deadline_at.isoformat() if instance.claim_deadline_at else None,
        },
    )
    runtime_state.commit()
    return instance.model_dump(mode="json")


@router.get(
    "/instances/{task_instance_id}/submission",
    summary="Get task submission",
    description="Get the latest submission for a task instance.",
    tags=["tasks"],
)
async def get_task_instance_submission(
    task_instance_id: str,
    task_submission_service: TaskSubmissionService = Depends(get_task_submission_service),
    actor: RequestActor = Depends(require_permission("tasks.detail")),
) -> TaskSubmissionResponse:
    try:
        submission = await task_submission_service.get_latest_submission_for_task(task_instance_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    actor.require_account_access(submission.account_id)
    return submission


@router.post(
    "/instances/{task_instance_id}/submit",
    summary="Submit task instance",
    description="Submit a task instance with proof and notes (legacy compatible).",
    tags=["tasks"],
)
async def submit_task_instance_compat(
    task_instance_id: str,
    payload: LegacyTaskSubmissionRequest,
    session: Session = Depends(get_db_session),
    task_submission_service: TaskSubmissionService = Depends(get_task_submission_service),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("tasks.submit")),
) -> TaskSubmissionResponse:
    try:
        actor.require_account_access(
            task_submission_service.resolve_task_instance_account_id(task_instance_id)
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    try:
        submission = await task_submission_service.create_submission(
            task_instance_id=task_instance_id,
            payload=_build_submission_payload(session, payload),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    runtime_state.add_audit_log(
        account_id=submission.account_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        action="task_instance_submitted",
        target_type="task_instance",
        target_id=task_instance_id,
        payload={
            "submission_id": submission.id,
            "submission_no": submission.submission_no,
            "status": submission.status,
        },
    )
    runtime_state.commit()
    return submission


@router.post(
    "/reviews/{task_instance_id}/approve",
    summary="Approve task review",
    description="Approve a task instance submission review (legacy compatible).",
    tags=["tasks"],
)
async def approve_task_instance_compat(
    task_instance_id: str,
    payload: LegacyTaskReviewActionRequest,
    task_submission_service: TaskSubmissionService = Depends(get_task_submission_service),
    review_service: ReviewService = Depends(get_review_service),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("reviews.approve")),
) -> LegacyTaskReviewStatusResponse:
    try:
        submission = await task_submission_service.get_latest_submission_for_task(task_instance_id)
        actor.require_account_access(submission.account_id)
        decision_payload = _build_review_payload(payload)
        decision = await review_service.approve_submission(
            submission_id=submission.id,
            reviewer_actor_id=actor.actor_id,
            payload=decision_payload,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    runtime_state.add_audit_log(
        account_id=submission.account_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        action="task_instance_approved",
        target_type="task_instance",
        target_id=task_instance_id,
        payload={
            "submission_id": submission.id,
            "reason_code": decision_payload.reason_code,
        },
    )
    runtime_state.commit()
    return _build_legacy_review_response(
        review_decision_id=decision.id,
        task_instance_id=task_instance_id,
        submission_id=submission.id,
        account_id=submission.account_id,
        status="approved",
        payload=decision_payload,
    )


@router.post(
    "/reviews/{task_instance_id}/reject",
    summary="Reject task review",
    description="Reject a task instance submission review (legacy compatible).",
    tags=["tasks"],
)
async def reject_task_instance_compat(
    task_instance_id: str,
    payload: LegacyTaskReviewActionRequest,
    task_submission_service: TaskSubmissionService = Depends(get_task_submission_service),
    review_service: ReviewService = Depends(get_review_service),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("reviews.reject")),
) -> LegacyTaskReviewStatusResponse:
    try:
        submission = await task_submission_service.get_latest_submission_for_task(task_instance_id)
        actor.require_account_access(submission.account_id)
        decision_payload = _build_review_payload(payload)
        decision = await review_service.reject_submission(
            submission_id=submission.id,
            reviewer_actor_id=actor.actor_id,
            payload=decision_payload,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    runtime_state.add_audit_log(
        account_id=submission.account_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        action="task_instance_rejected",
        target_type="task_instance",
        target_id=task_instance_id,
        payload={
            "submission_id": submission.id,
            "reason_code": decision_payload.reason_code,
        },
    )
    runtime_state.commit()
    return _build_legacy_review_response(
        review_decision_id=decision.id,
        task_instance_id=task_instance_id,
        submission_id=submission.id,
        account_id=submission.account_id,
        status="rejected",
        payload=decision_payload,
    )


@router.get(
    "/member-instances",
    summary="List task member instances",
    description="List task package member instances for the new H5 task system.",
    tags=["tasks"],
)
@router.get(
    "/packages",
    summary="List task packages",
    description="List task package instances for the new H5 task system.",
    tags=["tasks"],
)
async def list_task_packages(
    account_id: str | None = None,
    status: str | None = None,
    user_id: str | None = None,
    session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("tasks.instance.view")),
) -> list[TaskPackageAdminListItemResponse]:
    if account_id is not None:
        actor.require_account_access(account_id)
    service = TaskManualAddService(session=session)
    rows = service.list_packages(account_id=account_id, status=status, user_id=user_id)
    items: list[TaskPackageAdminListItemResponse] = []
    for package, public_user_id, site_key in rows:
        batch_index = package.batch_index or 1
        batch_total = package.batch_total or 1
        items.append(
            TaskPackageAdminListItemResponse(
                id=package.id,
                account_id=package.account_id,
                user_id=package.user_id,
                public_user_id=public_user_id,
                site_id=package.site_id,
                site_key=site_key,
                batch_id=package.batch_id,
                day_no=package.batch_day_no,
                batch_index=batch_index,
                batch_total=batch_total,
                progress_label=f"{batch_index}/{batch_total}",
                status=package.status,
                planned_amount=float(package.planned_amount),
                system_generated_amount=float(package.system_generated_amount),
                manual_added_amount=float(package.manual_added_amount),
                effective_amount=float(package.effective_amount),
                estimated_reward_amount=float(package.effective_amount * package.reward_ratio_snapshot),
                has_manual_add=float(package.manual_added_amount) > 0,
                claimed_at=package.claimed_at,
                completed_at=package.completed_at,
            )
        )
    return filter_account_scoped_items(actor, items, lambda item: item.account_id)


@router.get(
    "/member-instances/{package_id}",
    summary="Get task member instance detail",
    description="Get task member instance detail with amount breakdown, items, and manual add logs.",
    tags=["tasks"],
)
@router.get(
    "/packages/{package_id}",
    summary="Get task package detail",
    description="Get task package detail with amount breakdown, items, and manual add logs.",
    tags=["tasks"],
)
async def get_task_package_detail(
    package_id: str,
    session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("tasks.instance.view")),
) -> TaskPackageAdminDetailResponse:
    service = TaskManualAddService(session=session)
    try:
        package, logs = service.get_package_detail(package_id=package_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    actor.require_account_access(package.account_id)
    batch_index = package.batch_index or 1
    batch_total = package.batch_total or 1
    batch = session.get(MemberTaskBatch, package.batch_id) if package.batch_id is not None else None
    return TaskPackageAdminDetailResponse(
        id=package.id,
        batch_id=package.batch_id,
        day_no=package.batch_day_no,
        batch_index=batch_index,
        batch_total=batch_total,
        progress_label=f"{batch_index}/{batch_total}",
        status=package.status,
        day_planned_amount=float(batch.planned_amount) if batch is not None else float(package.planned_amount),
        day_system_generated_amount=(
            float(batch.system_generated_amount) if batch is not None else float(package.system_generated_amount)
        ),
        day_manual_added_amount=float(batch.manual_added_amount) if batch is not None else float(package.manual_added_amount),
        day_effective_amount=float(batch.effective_day_amount) if batch is not None else float(package.effective_amount),
        planned_amount=float(package.planned_amount),
        system_generated_amount=float(package.system_generated_amount),
        manual_added_amount=float(package.manual_added_amount),
        effective_amount=float(package.effective_amount),
        reward_ratio=float(package.reward_ratio_snapshot),
        estimated_reward_amount=float(package.effective_amount * package.reward_ratio_snapshot),
        claimed_at=package.claimed_at,
        completed_at=package.completed_at,
        items=[_serialize_task_package_item(item) for item in sorted(package.items, key=lambda entry: entry.sort_order)],
        manual_add_logs=[_serialize_task_manual_add_log(log) for log in logs],
    )


@router.get(
    "/member-instances/{package_id}/manual-add-logs",
    summary="List task member instance manual-add logs",
    description="List manual-add logs for a task member instance package.",
    tags=["tasks"],
)
@router.get(
    "/manual-add/logs",
    summary="List task manual-add logs",
    description="List manual-add logs for a task package.",
    tags=["tasks"],
)
async def list_task_manual_add_logs(
    package_id: str,
    session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("tasks.manual_add.view")),
) -> list[TaskManualAddLogResponse]:
    service = TaskManualAddService(session=session)
    try:
        package = service._require_package(package_id=package_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    actor.require_account_access(package.account_id)
    return [_serialize_task_manual_add_log(log) for log in service.list_logs(package_id=package_id)]


@router.get(
    "/member-instances/{package_id}/available-add-items",
    summary="List available manual-add items",
    description="List candidate products that can still be manually added to the member instance batch.",
    tags=["tasks"],
)
@router.get(
    "/packages/{package_id}/manual-add/candidates",
    summary="List manual-add product candidates",
    description="List candidate products that can still be manually added to the package batch.",
    tags=["tasks"],
)
async def list_task_package_manual_add_candidates(
    package_id: str,
    session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("tasks.manual_add.view")),
) -> list[TaskManualAddCandidateResponse]:
    service = TaskManualAddService(session=session)
    try:
        package = service._require_package(package_id=package_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    actor.require_account_access(package.account_id)
    return [
        TaskManualAddCandidateResponse(
            id=item.id,
            product_id=item.product_id,
            product_name=item.product_name,
            image_url=item.image_url,
            price=float(item.price),
            currency=item.currency,
        )
        for item in service.list_available_pool_items(package_id=package_id)
    ]


@router.post(
    "/member-instances/{package_id}/pause",
    summary="Pause task package instance",
    description="Pause a task package instance so it cannot continue until resumed.",
    tags=["tasks"],
)
async def pause_task_member_instance(
    package_id: str,
    payload: TaskPackageStatusActionRequest,
    session: Session = Depends(get_db_session),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("tasks.instance.pause")),
) -> TaskPackageAdminDetailResponse:
    service = TaskManualAddService(session=session)
    try:
        package = service._require_package(package_id=package_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    actor.require_account_access(package.account_id)
    try:
        package = service.pause_package(package_id=package_id, reason_text=payload.reason_text)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    runtime_state.add_audit_log(
        account_id=package.account_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        action="task_package_paused",
        target_type="task_package_instance",
        target_id=package.id,
        payload={
            "batch_id": package.batch_id,
            "day_no": package.batch_day_no,
            "reason_text": payload.reason_text,
        },
    )
    runtime_state.commit()
    logs = service.list_logs(package_id=package_id)
    batch_index = package.batch_index or 1
    batch_total = package.batch_total or 1
    batch = session.get(MemberTaskBatch, package.batch_id) if package.batch_id is not None else None
    return TaskPackageAdminDetailResponse(
        id=package.id,
        batch_id=package.batch_id,
        day_no=package.batch_day_no,
        batch_index=batch_index,
        batch_total=batch_total,
        progress_label=f"{batch_index}/{batch_total}",
        status=package.status,
        day_planned_amount=float(batch.planned_amount) if batch is not None else float(package.planned_amount),
        day_system_generated_amount=(
            float(batch.system_generated_amount) if batch is not None else float(package.system_generated_amount)
        ),
        day_manual_added_amount=float(batch.manual_added_amount) if batch is not None else float(package.manual_added_amount),
        day_effective_amount=float(batch.effective_day_amount) if batch is not None else float(package.effective_amount),
        planned_amount=float(package.planned_amount),
        system_generated_amount=float(package.system_generated_amount),
        manual_added_amount=float(package.manual_added_amount),
        effective_amount=float(package.effective_amount),
        reward_ratio=float(package.reward_ratio_snapshot),
        estimated_reward_amount=float(package.effective_amount * package.reward_ratio_snapshot),
        claimed_at=package.claimed_at,
        completed_at=package.completed_at,
        items=[_serialize_task_package_item(item) for item in sorted(package.items, key=lambda entry: entry.sort_order)],
        manual_add_logs=[_serialize_task_manual_add_log(log) for log in logs],
    )


@router.post(
    "/member-instances/{package_id}/resume",
    summary="Resume task package instance",
    description="Resume a paused task package instance back to its runnable status.",
    tags=["tasks"],
)
async def resume_task_member_instance(
    package_id: str,
    payload: TaskPackageStatusActionRequest,
    session: Session = Depends(get_db_session),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("tasks.instance.resume")),
) -> TaskPackageAdminDetailResponse:
    service = TaskManualAddService(session=session)
    try:
        package = service._require_package(package_id=package_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    actor.require_account_access(package.account_id)
    try:
        package = service.resume_package(package_id=package_id, reason_text=payload.reason_text)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    runtime_state.add_audit_log(
        account_id=package.account_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        action="task_package_resumed",
        target_type="task_package_instance",
        target_id=package.id,
        payload={
            "batch_id": package.batch_id,
            "day_no": package.batch_day_no,
            "reason_text": payload.reason_text,
        },
    )
    runtime_state.commit()
    logs = service.list_logs(package_id=package_id)
    batch_index = package.batch_index or 1
    batch_total = package.batch_total or 1
    batch = session.get(MemberTaskBatch, package.batch_id) if package.batch_id is not None else None
    return TaskPackageAdminDetailResponse(
        id=package.id,
        batch_id=package.batch_id,
        day_no=package.batch_day_no,
        batch_index=batch_index,
        batch_total=batch_total,
        progress_label=f"{batch_index}/{batch_total}",
        status=package.status,
        day_planned_amount=float(batch.planned_amount) if batch is not None else float(package.planned_amount),
        day_system_generated_amount=(
            float(batch.system_generated_amount) if batch is not None else float(package.system_generated_amount)
        ),
        day_manual_added_amount=float(batch.manual_added_amount) if batch is not None else float(package.manual_added_amount),
        day_effective_amount=float(batch.effective_day_amount) if batch is not None else float(package.effective_amount),
        planned_amount=float(package.planned_amount),
        system_generated_amount=float(package.system_generated_amount),
        manual_added_amount=float(package.manual_added_amount),
        effective_amount=float(package.effective_amount),
        reward_ratio=float(package.reward_ratio_snapshot),
        estimated_reward_amount=float(package.effective_amount * package.reward_ratio_snapshot),
        claimed_at=package.claimed_at,
        completed_at=package.completed_at,
        items=[_serialize_task_package_item(item) for item in sorted(package.items, key=lambda entry: entry.sort_order)],
        manual_add_logs=[_serialize_task_manual_add_log(log) for log in logs],
    )


@router.post(
    "/member-instances/{package_id}/cancel",
    summary="Cancel task package instance",
    description="Cancel a task package instance and stop further progress.",
    tags=["tasks"],
)
async def cancel_task_member_instance(
    package_id: str,
    payload: TaskPackageStatusActionRequest,
    session: Session = Depends(get_db_session),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("tasks.instance.cancel")),
) -> TaskPackageAdminDetailResponse:
    service = TaskManualAddService(session=session)
    try:
        package = service._require_package(package_id=package_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    actor.require_account_access(package.account_id)
    try:
        package = service.cancel_package(package_id=package_id, reason_text=payload.reason_text)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    runtime_state.add_audit_log(
        account_id=package.account_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        action="task_package_cancelled",
        target_type="task_package_instance",
        target_id=package.id,
        payload={
            "batch_id": package.batch_id,
            "day_no": package.batch_day_no,
            "reason_text": payload.reason_text,
        },
    )
    runtime_state.commit()
    logs = service.list_logs(package_id=package_id)
    batch_index = package.batch_index or 1
    batch_total = package.batch_total or 1
    batch = session.get(MemberTaskBatch, package.batch_id) if package.batch_id is not None else None
    return TaskPackageAdminDetailResponse(
        id=package.id,
        batch_id=package.batch_id,
        day_no=package.batch_day_no,
        batch_index=batch_index,
        batch_total=batch_total,
        progress_label=f"{batch_index}/{batch_total}",
        status=package.status,
        day_planned_amount=float(batch.planned_amount) if batch is not None else float(package.planned_amount),
        day_system_generated_amount=(
            float(batch.system_generated_amount) if batch is not None else float(package.system_generated_amount)
        ),
        day_manual_added_amount=float(batch.manual_added_amount) if batch is not None else float(package.manual_added_amount),
        day_effective_amount=float(batch.effective_day_amount) if batch is not None else float(package.effective_amount),
        planned_amount=float(package.planned_amount),
        system_generated_amount=float(package.system_generated_amount),
        manual_added_amount=float(package.manual_added_amount),
        effective_amount=float(package.effective_amount),
        reward_ratio=float(package.reward_ratio_snapshot),
        estimated_reward_amount=float(package.effective_amount * package.reward_ratio_snapshot),
        claimed_at=package.claimed_at,
        completed_at=package.completed_at,
        items=[_serialize_task_package_item(item) for item in sorted(package.items, key=lambda entry: entry.sort_order)],
        manual_add_logs=[_serialize_task_manual_add_log(log) for log in logs],
    )


@router.post(
    "/member-instances/{package_id}/pause-next-batch",
    summary="Pause next task batch issuance",
    description="Cancel the next pending task quota for the same user and issue plan chain.",
    tags=["tasks"],
)
async def pause_next_task_member_batch(
    package_id: str,
    payload: MemberTaskQuotaCancelRequest,
    session: Session = Depends(get_db_session),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("tasks.quota.cancel")),
) -> MemberTaskDayQuotaResponse:
    service = TaskManualAddService(session=session)
    try:
        package = service._require_package(package_id=package_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    actor.require_account_access(package.account_id)
    try:
        quota = service.cancel_next_pending_quota_for_package(
            package_id=package_id,
            reason=payload.reason,
            cancelled_by=actor.actor_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    runtime_state.add_audit_log(
        account_id=quota.account_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        action="member_task_day_quota_cancelled_from_monitor",
        target_type="member_task_day_quota",
        target_id=quota.id,
        payload={
            "package_id": package_id,
            "reason": payload.reason,
            "day_no": quota.day_no,
            "plan_id": quota.plan_id,
        },
    )
    runtime_state.commit()
    return quota


@router.post(
    "/member-instances/{package_id}/preview-add-items",
    summary="Preview member instance manual-add items",
    description="Preview amount and reward impact before appending products to the tail of a task member instance.",
    tags=["tasks"],
)
@router.post(
    "/packages/{package_id}/manual-add/preview",
    summary="Preview manual-add task products",
    description="Preview amount and reward impact before appending products to the tail of a task package.",
    tags=["tasks"],
)
async def preview_task_package_manual_add(
    package_id: str,
    payload: TaskManualAddCreateRequest,
    session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("tasks.manual_add.view")),
) -> TaskManualAddPreviewResponse:
    service = TaskManualAddService(session=session)
    try:
        package = service._require_package(package_id=package_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    actor.require_account_access(package.account_id)
    try:
        package, pool_items, added_amount = service.preview_add_items(
            package_id=package_id,
            pool_item_ids=payload.pool_item_ids,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    before_manual_added_amount = Decimal(package.manual_added_amount)
    before_effective_amount = Decimal(package.effective_amount)
    after_manual_added_amount = before_manual_added_amount + added_amount
    after_effective_amount = before_effective_amount + added_amount
    return TaskManualAddPreviewResponse(
        package_id=package.id,
        candidate_count=len(pool_items),
        added_item_count=len(pool_items),
        added_amount=float(added_amount),
        package_planned_amount=float(package.planned_amount),
        package_system_generated_amount=float(package.system_generated_amount),
        package_manual_added_amount_before=float(before_manual_added_amount),
        package_manual_added_amount_after=float(after_manual_added_amount),
        package_effective_amount_before=float(before_effective_amount),
        package_effective_amount_after=float(after_effective_amount),
        reward_ratio=float(package.reward_ratio_snapshot),
        estimated_reward_amount_before=float(
            service.estimate_reward_amount(package=package, effective_amount=before_effective_amount)
        ),
        estimated_reward_amount_after=float(
            service.estimate_reward_amount(package=package, effective_amount=after_effective_amount)
        ),
        items=[
            TaskManualAddCandidateResponse(
                id=item.id,
                product_id=item.product_id,
                product_name=item.product_name,
                image_url=item.image_url,
                price=float(item.price),
                currency=item.currency,
            )
            for item in pool_items
        ],
    )


@router.post(
    "/member-instances/{package_id}/add-items",
    summary="Add member instance manual-add items",
    description="Append operator-selected products to the tail of a task member instance.",
    tags=["tasks"],
)
@router.post(
    "/packages/{package_id}/manual-add",
    summary="Add manual task products",
    description="Append operator-selected products to the tail of a task package.",
    tags=["tasks"],
)
async def create_task_package_manual_add(
    package_id: str,
    payload: TaskManualAddCreateRequest,
    session: Session = Depends(get_db_session),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("tasks.manual_add.create")),
) -> TaskManualAddResponse:
    service = TaskManualAddService(session=session)
    try:
        package = service._require_package(package_id=package_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    actor.require_account_access(package.account_id)
    try:
        log = service.add_items(
            package_id=package_id,
            pool_item_ids=payload.pool_item_ids,
            operator_id=actor.actor_id,
            reason_text=payload.reason_text,
            notify_user=payload.notify_user,
            user_notice_text=payload.user_notice_text,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    refreshed_package = service._require_package(package_id=package_id)
    batch_manual_added_amount = 0.0
    batch_effective_day_amount = 0.0
    if refreshed_package.batch_id is not None:
        batch = session.get(MemberTaskBatch, refreshed_package.batch_id)
        if batch is not None:
            batch_manual_added_amount = float(batch.manual_added_amount)
            batch_effective_day_amount = float(batch.effective_day_amount)

    runtime_state.add_audit_log(
        account_id=refreshed_package.account_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        action="task_package_manual_add_created",
        target_type="task_package_instance",
        target_id=package_id,
        payload={
            "log_id": log.id,
            "batch_id": refreshed_package.batch_id,
            "reason_text": log.reason_text,
            "added_item_count": log.added_item_count,
            "added_amount": float(log.added_amount),
            "before_manual_added_amount": float(log.before_manual_added_amount),
            "after_manual_added_amount": float(log.after_manual_added_amount),
            "before_effective_amount": float(log.before_effective_amount),
            "after_effective_amount": float(log.after_effective_amount),
            "notify_user": log.notify_user,
            "user_notice_text": log.user_notice_text,
            "user_notified_at": log.user_notified_at.isoformat() if log.user_notified_at is not None else None,
        },
    )
    runtime_state.commit()

    return TaskManualAddResponse(
        id=log.id,
        package_id=package_id,
        added_item_count=log.added_item_count,
        added_amount=float(log.added_amount),
        package_manual_added_amount=float(refreshed_package.manual_added_amount),
        package_effective_amount=float(refreshed_package.effective_amount),
        batch_manual_added_amount=batch_manual_added_amount,
        batch_effective_day_amount=batch_effective_day_amount,
    )
