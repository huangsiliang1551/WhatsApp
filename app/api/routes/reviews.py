from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_review_service, get_runtime_state_service, require_permission
from app.core.auth import RequestActor, filter_account_scoped_items
from app.schemas.task_workflow import (
    ReviewQueueItemResponse,
    TaskReviewDecisionActionRequest,
    TaskReviewDecisionResponse,
)
from app.services.review_service import ReviewService
from app.services.runtime_state import RuntimeStateStore
from pydantic import BaseModel


async def _approve_or_reject_submission(
    review_service: ReviewService,
    runtime_state: RuntimeStateStore,
    actor: RequestActor,
    submission_id: str,
    payload: TaskReviewDecisionActionRequest,
    action: str,
) -> TaskReviewDecisionResponse:
    """Shared logic for approve/reject a submission by ID."""
    try:
        detail = await review_service.get_submission_detail(submission_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    actor.require_account_access(detail.account_id)
    try:
        if action == "approve":
            result = await review_service.approve_submission(
                submission_id=submission_id,
                reviewer_actor_id=actor.actor_id,
                payload=payload,
            )
        else:
            result = await review_service.reject_submission(
                submission_id=submission_id,
                reviewer_actor_id=actor.actor_id,
                payload=payload,
            )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    runtime_state.add_audit_log(
        account_id=result.account_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        action=f"task_submission_{action}d",
        target_type="task_submission",
        target_id=submission_id,
        payload={
            "task_instance_id": result.task_instance_id,
            "reason_code": result.reason_code,
        },
    )
    runtime_state.commit()
    return result


class BatchReviewRequest(BaseModel):
    review_ids: list[str]
    reviewer_note: str | None = None


class BatchOperationResult(BaseModel):
    review_id: str
    status: str
    error: str | None = None


class BatchOperationResponse(BaseModel):
    success_count: int
    failed_count: int
    results: list[BatchOperationResult]


router = APIRouter(prefix="/api/reviews", tags=["reviews"])



@router.get(
    "/queue",
    summary="List review queue",
    description="List task submissions pending review with optional account or agency filter.",
    tags=["reviews"],
)
async def list_review_queue(
    account_id: str | None = None,
    agency_id: str | None = None,
    review_service: ReviewService = Depends(get_review_service),
    actor: RequestActor = Depends(require_permission("reviews.view")),
) -> list[ReviewQueueItemResponse]:
    if account_id is not None:
        actor.require_account_access(account_id)
    items = await review_service.list_review_queue(account_id=account_id)
    return filter_account_scoped_items(actor, items, lambda item: item.account_id)


@router.get(
    "/submissions/{submission_id}",
    summary="Get submission detail",
    description="Get detailed information about a specific task submission.",
    tags=["reviews"],
)
async def get_review_submission_detail(
    submission_id: str,
    review_service: ReviewService = Depends(get_review_service),
    actor: RequestActor = Depends(require_permission("reviews.view")),
) -> ReviewQueueItemResponse:
    try:
        detail = await review_service.get_submission_detail(submission_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    actor.require_account_access(detail.account_id)
    return detail


@router.post(
    "/submissions/{submission_id}/approve",
    summary="Approve submission",
    description="Approve a pending task submission.",
    tags=["reviews"],
)
async def approve_submission(
    submission_id: str,
    payload: TaskReviewDecisionActionRequest,
    review_service: ReviewService = Depends(get_review_service),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("reviews.approve")),
) -> TaskReviewDecisionResponse:
    try:
        detail = await review_service.get_submission_detail(submission_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    actor.require_account_access(detail.account_id)
    try:
        result = await review_service.approve_submission(
            submission_id=submission_id,
            reviewer_actor_id=actor.actor_id,
            payload=payload,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    runtime_state.add_audit_log(
        account_id=result.account_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        action="task_submission_approved",
        target_type="task_submission",
        target_id=submission_id,
        payload={
            "task_instance_id": result.task_instance_id,
            "reason_code": result.reason_code,
        },
    )
    runtime_state.commit()
    return result


@router.post(
    "/submissions/{submission_id}/reject",
    summary="Reject submission",
    description="Reject a pending task submission.",
    tags=["reviews"],
)
async def reject_submission(
    submission_id: str,
    payload: TaskReviewDecisionActionRequest,
    review_service: ReviewService = Depends(get_review_service),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("reviews.reject")),
) -> TaskReviewDecisionResponse:
    try:
        detail = await review_service.get_submission_detail(submission_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    actor.require_account_access(detail.account_id)
    try:
        result = await review_service.reject_submission(
            submission_id=submission_id,
            reviewer_actor_id=actor.actor_id,
            payload=payload,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    runtime_state.add_audit_log(
        account_id=result.account_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        action="task_submission_rejected",
        target_type="task_submission",
        target_id=submission_id,
        payload={
            "task_instance_id": result.task_instance_id,
            "reason_code": result.reason_code,
        },
    )
    runtime_state.commit()
    return result


@router.post(
    "/{review_id}/approve",
    summary="Approve review",
    description="Approve a pending task review.",
    tags=["reviews"],
    include_in_schema=False,
)
async def approve_review_by_id(
    review_id: str,
    payload: TaskReviewDecisionActionRequest,
    review_service: ReviewService = Depends(get_review_service),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("reviews.approve")),
) -> TaskReviewDecisionResponse:
    """Alias for /submissions/{submission_id}/approve."""
    return await _approve_or_reject_submission(
        review_service=review_service,
        runtime_state=runtime_state,
        actor=actor,
        submission_id=review_id,
        payload=payload,
        action="approve",
    )


@router.post(
    "/{review_id}/reject",
    summary="Reject review",
    description="Reject a pending task review.",
    tags=["reviews"],
    include_in_schema=False,
)
async def reject_review_by_id(
    review_id: str,
    payload: TaskReviewDecisionActionRequest,
    review_service: ReviewService = Depends(get_review_service),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("reviews.reject")),
) -> TaskReviewDecisionResponse:
    """Alias for /submissions/{submission_id}/reject."""
    return await _approve_or_reject_submission(
        review_service=review_service,
        runtime_state=runtime_state,
        actor=actor,
        submission_id=review_id,
        payload=payload,
        action="reject",
    )


@router.post(
    "/batch-approve",
    summary="Batch approve reviews",
    description="Approve multiple task submissions in batch. Independent transactions.",
    tags=["reviews"],
)
async def batch_approve_reviews(
    payload: BatchReviewRequest,
    review_service: ReviewService = Depends(get_review_service),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("reviews.approve")),
) -> BatchOperationResponse:
    results: list[BatchOperationResult] = []
    for rid in payload.review_ids:
        try:
            from app.schemas.task_workflow import TaskReviewDecisionActionRequest

            result = await review_service.approve_submission(
                submission_id=rid,
                reviewer_actor_id=actor.actor_id,
                payload=TaskReviewDecisionActionRequest(
                    reason_code="approved",
                    reason_detail=payload.reviewer_note or "Batch approved",
                    actions=[],
                ),
            )
            runtime_state.add_audit_log(
                account_id=result.account_id,
                actor_type=actor.actor_type,
                actor_id=actor.actor_id,
                action="review_batch_approved",
                target_type="task_submission",
                target_id=rid,
                payload={"reviewer_note": payload.reviewer_note},
            )
            results.append(BatchOperationResult(review_id=rid, status="success"))
        except Exception as exc:
            results.append(BatchOperationResult(review_id=rid, status="failed", error=str(exc)))
    runtime_state.commit()
    success = sum(1 for r in results if r.status == "success")
    return BatchOperationResponse(success_count=success, failed_count=len(results) - success, results=results)


@router.post(
    "/batch-reject",
    summary="Batch reject reviews",
    description="Reject multiple task submissions in batch. Independent transactions.",
    tags=["reviews"],
)
async def batch_reject_reviews(
    payload: BatchReviewRequest,
    review_service: ReviewService = Depends(get_review_service),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("reviews.reject")),
) -> BatchOperationResponse:
    results: list[BatchOperationResult] = []
    for rid in payload.review_ids:
        try:
            from app.schemas.task_workflow import TaskReviewDecisionActionRequest

            result = await review_service.reject_submission(
                submission_id=rid,
                reviewer_actor_id=actor.actor_id,
                payload=TaskReviewDecisionActionRequest(
                    reason_code="rejected",
                    reason_detail=payload.reviewer_note or "Batch rejected",
                    actions=[],
                ),
            )
            runtime_state.add_audit_log(
                account_id=result.account_id,
                actor_type=actor.actor_type,
                actor_id=actor.actor_id,
                action="review_batch_rejected",
                target_type="task_submission",
                target_id=rid,
                payload={"reviewer_note": payload.reviewer_note},
            )
            results.append(BatchOperationResult(review_id=rid, status="success"))
        except Exception as exc:
            results.append(BatchOperationResult(review_id=rid, status="failed", error=str(exc)))
    runtime_state.commit()
    success = sum(1 for r in results if r.status == "success")
    return BatchOperationResponse(success_count=success, failed_count=len(results) - success, results=results)
