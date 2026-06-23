from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, require_permission
from app.core.auth import RequestActor
from app.schemas.marketing import ManualPushRequest, StartProductRequest
from app.services.task_engine import InsufficientBalanceError, TaskEngine

router = APIRouter(prefix="/api/task-instances", tags=["marketing"])

# We need a simple fake redis for the engine
_fake_redis = None


@router.get("")
async def list_task_instances(
    account_id: str | None = Query(default=None),
    user_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    rule_id: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    actor: RequestActor = Depends(require_permission("tasks.view")),
    session: Session = Depends(get_db_session),
) -> dict:
    from sqlalchemy import select
    from app.db.models import MktTaskInstance

    query = select(MktTaskInstance).order_by(MktTaskInstance.created_at.desc())

    # Apply account scope filtering
    if actor.is_super_admin:
        # Super admin: filter only if account_id is specified
        if account_id:
            query = query.where(MktTaskInstance.account_id == account_id)
    elif actor.account_ids:
        # Agent / agent_member: scope to their accounts
        query = query.where(MktTaskInstance.account_id.in_(actor.account_ids))
    else:
        # No access scope - return empty
        return {"items": [], "total": 0, "page": page, "size": size}

    if user_id:
        query = query.where(MktTaskInstance.user_id == user_id)
    if status:
        query = query.where(MktTaskInstance.status == status)
    if rule_id:
        query = query.where(MktTaskInstance.rule_id == rule_id)
    total_query = query
    all_items = session.execute(total_query).scalars().all()
    total_count = len(all_items)
    offset = (page - 1) * size
    items = session.execute(query.offset(offset).limit(size)).scalars().all()
    return {
        "items": [
            {
                "id": inst.id,
                "account_id": inst.account_id,
                "user_id": inst.user_id,
                "rule_id": inst.rule_id,
                "package_id": inst.package_id,
                "task_type": inst.task_type,
                "status": inst.status,
                "product_progress": inst.product_progress,
                "total_paid": inst.total_paid,
                "reward_amount": inst.reward_amount,
                "created_at": inst.created_at.isoformat() if inst.created_at else None,
                "started_at": inst.started_at.isoformat() if inst.started_at else None,
                "completed_at": inst.completed_at.isoformat() if inst.completed_at else None,
                "expires_at": inst.expires_at.isoformat() if inst.expires_at else None,
            }
            for inst in items
        ],
        "total": total_count,
    }


@router.post("/manual-push")
async def manual_push(
    payload: ManualPushRequest,
    actor: RequestActor = Depends(require_permission("tasks.push")),
    session: Session = Depends(get_db_session),
) -> dict:
    actor.require_account_access(payload.account_id)
    engine = TaskEngine(session)
    try:
        instances = engine.manual_push(
            rule_id=payload.rule_id,
            user_ids=payload.user_ids,
            account_id=payload.account_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "pushed_count": len(instances),
        "task_instance_ids": [inst.id for inst in instances],
    }


@router.post("/{task_instance_id}/start-product")
async def start_product_task(
    task_instance_id: str,
    payload: StartProductRequest,
    actor: RequestActor = Depends(require_permission("tasks.detail")),
    session: Session = Depends(get_db_session),
) -> dict:
    engine = TaskEngine(session)
    try:
        inst = engine.start_product(task_instance_id, payload.product_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InsufficientBalanceError as exc:
        raise HTTPException(status_code=402, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "id": inst.id,
        "status": inst.status,
        "total_paid": str(inst.total_paid),
        "product_progress": inst.product_progress,
    }


@router.post("/{task_instance_id}/complete-product")
async def complete_product_task(
    task_instance_id: str,
    payload: StartProductRequest,
    actor: RequestActor = Depends(require_permission("tasks.detail")),
    session: Session = Depends(get_db_session),
) -> dict:
    engine = TaskEngine(session)
    try:
        inst = engine.complete_product(task_instance_id, payload.product_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "id": inst.id,
        "status": inst.status,
        "total_paid": str(inst.total_paid),
        "reward_amount": str(inst.reward_amount),
        "product_progress": inst.product_progress,
    }


@router.post("/{task_instance_id}/retry-product")
async def retry_product_task(
    task_instance_id: str,
    payload: StartProductRequest,
    actor: RequestActor = Depends(require_permission("tasks.retry")),
    session: Session = Depends(get_db_session),
) -> dict:
    engine = TaskEngine(session)
    try:
        inst = engine.retry_product(task_instance_id, payload.product_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "id": inst.id,
        "status": inst.status,
        "total_paid": str(inst.total_paid),
    }


@router.get("/{task_instance_id}")
async def get_task_instance(
    task_instance_id: str,
    actor: RequestActor = Depends(require_permission("tasks.detail")),
    session: Session = Depends(get_db_session),
) -> dict:
    from app.db.models import MktTaskInstance
    inst = session.get(MktTaskInstance, task_instance_id)
    if inst is None:
        raise HTTPException(status_code=404, detail=f"Task instance '{task_instance_id}' not found.")
    return {
        "id": inst.id,
        "account_id": inst.account_id,
        "user_id": inst.user_id,
        "rule_id": inst.rule_id,
        "package_id": inst.package_id,
        "task_type": inst.task_type,
        "status": inst.status,
        "product_progress": inst.product_progress,
        "total_paid": inst.total_paid,
        "reward_amount": inst.reward_amount,
        "created_at": inst.created_at.isoformat() if inst.created_at else None,
        "started_at": inst.started_at.isoformat() if inst.started_at else None,
        "completed_at": inst.completed_at.isoformat() if inst.completed_at else None,
        "expires_at": inst.expires_at.isoformat() if inst.expires_at else None,
    }
