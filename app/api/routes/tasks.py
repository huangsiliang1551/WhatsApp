from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import (
    get_db_session,
    get_review_service,
    get_runtime_state_service,
    get_task_service,
    get_task_submission_service,
    require_permission,
)
from app.core.auth import RequestActor, filter_account_scoped_items
from app.db.models import AppUser
from app.schemas.tasks import (
    TaskInstanceClaimRequest,
    TaskInstanceCreateRequest,
    TaskTemplateCreateRequest,
)
from app.schemas.task_workflow import (
    TaskReviewDecisionActionRequest,
    TaskSubmissionCreateRequest,
    TaskSubmissionResponse,
)
from app.services.review_service import ReviewService
from app.services.runtime_state import RuntimeStateStore
from app.services.task_submission_service import TaskSubmissionService
from app.services.task_service import TaskService

router = APIRouter(prefix="/api/tasks", tags=["tasks"])



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
