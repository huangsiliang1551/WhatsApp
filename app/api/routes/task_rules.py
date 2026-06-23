from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, require_permission
from app.core.auth import RequestActor
from app.schemas.marketing import TaskRuleCreateRequest, TaskRuleUpdateRequest, TaskRuleToggleRequest
from app.services.task_rule_service import TaskRuleService

router = APIRouter(prefix="/api/task-rules", tags=["marketing"])



@router.get("")
async def list_task_rules(
    account_id: str | None = Query(default=None),
    agency_id: str | None = Query(default=None),
    rule_type: str | None = Query(default=None),
    trigger_type: str | None = Query(default=None),
    actor: RequestActor = Depends(require_permission("task_rules.view")),
    session: Session = Depends(get_db_session),
) -> dict:
    svc = TaskRuleService(session)
    # If super admin, pass through as-is (service supports account_id=None -> all)
    # For non-super admin, scope by their account_ids if no specific account_id given
    resolved_account_id = account_id
    if not actor.is_super_admin and account_id is None:
        if actor.account_ids:
            # Collect rules across all accessible accounts
            from app.db.models import TaskRule
            from sqlalchemy import select
            all_rules = []
            for aid in dict.fromkeys(actor.account_ids):
                result = svc.list_rules(account_id=aid, rule_type=rule_type, trigger_type=trigger_type)
                items = result.get("items", result) if isinstance(result, dict) else result
                all_rules.extend(items if isinstance(items, list) else [items])
            return {"items": all_rules, "total": len(all_rules)}
        return {"items": [], "total": 0}
    return svc.list_rules(account_id=resolved_account_id, rule_type=rule_type, trigger_type=trigger_type)


@router.post("", status_code=201)
async def create_task_rule(
    payload: TaskRuleCreateRequest,
    actor: RequestActor = Depends(require_permission("task_rules.create")),
    session: Session = Depends(get_db_session),
) -> dict:
    svc = TaskRuleService(session)
    rule = svc.create_rule(payload)
    return {
        "id": rule.id,
        "account_id": rule.account_id,
        "name": rule.name,
        "rule_type": rule.rule_type,
        "trigger_type": rule.trigger_type,
        "trigger_config": rule.trigger_config,
        "package_id": rule.package_id,
        "follow_up_chain": rule.follow_up_chain,
        "expiry_config": rule.expiry_config,
        "is_enabled": rule.is_enabled,
        "created_at": rule.created_at.isoformat() if rule.created_at else None,
        "updated_at": rule.updated_at.isoformat() if rule.updated_at else None,
    }


@router.patch("/{rule_id}")
async def update_task_rule(
    rule_id: str,
    payload: TaskRuleUpdateRequest,
    actor: RequestActor = Depends(require_permission("task_rules.edit")),
    session: Session = Depends(get_db_session),
) -> dict:
    svc = TaskRuleService(session)
    try:
        rule = svc.update_rule(rule_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "id": rule.id,
        "account_id": rule.account_id,
        "name": rule.name,
        "rule_type": rule.rule_type,
        "trigger_type": rule.trigger_type,
        "trigger_config": rule.trigger_config,
        "package_id": rule.package_id,
        "follow_up_chain": rule.follow_up_chain,
        "expiry_config": rule.expiry_config,
        "is_enabled": rule.is_enabled,
        "created_at": rule.created_at.isoformat() if rule.created_at else None,
        "updated_at": rule.updated_at.isoformat() if rule.updated_at else None,
    }


@router.patch("/{rule_id}/toggle")
async def toggle_task_rule(
    rule_id: str,
    payload: TaskRuleToggleRequest,
    actor: RequestActor = Depends(require_permission("task_rules.toggle")),
    session: Session = Depends(get_db_session),
) -> dict:
    svc = TaskRuleService(session)
    try:
        rule = svc.toggle_rule(rule_id, payload.is_enabled)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"id": rule.id, "is_enabled": rule.is_enabled}


@router.delete("/{rule_id}", status_code=204)
async def delete_task_rule(
    rule_id: str,
    actor: RequestActor = Depends(require_permission("task_rules.delete")),
    session: Session = Depends(get_db_session),
) -> Response:
    svc = TaskRuleService(session)
    try:
        svc.delete_rule(rule_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return Response(status_code=204)
