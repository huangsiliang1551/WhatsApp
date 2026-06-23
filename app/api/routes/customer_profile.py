"""Customer profile and auto-tag rules API — IV-BE-004.

Endpoints:
  GET   /api/customers/{id}/profile         — customer profile
  GET   /api/auto-tag-rules                 — list rules
  POST  /api/auto-tag-rules                 — create rule
  PATCH /api/auto-tag-rules/{id}            — update rule
  DELETE /api/auto-tag-rules/{id}           — delete rule
  POST  /api/auto-tag-rules/{id}/evaluate   — evaluate rule for a user
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, require_permission
from app.core.auth import RequestActor
from app.services.customer_profile_service import CustomerProfileService

router = APIRouter(tags=["customer_profile"])


class CreateRuleRequest(BaseModel):
    name: str
    condition_type: str  # recharge_total / sign_in_count / conversation_count
    condition_operator: str  # gt / lt / eq / gte / lte
    condition_value: float
    tag_name: str


class UpdateRuleRequest(BaseModel):
    name: str | None = None
    condition_type: str | None = None
    condition_operator: str | None = None
    condition_value: float | None = None
    tag_name: str | None = None
    is_enabled: bool | None = None


class EvaluateRequest(BaseModel):
    user_id: str


# ─── Profile ────────────────────────────────────────────────────────────────


@router.get("/api/customers/{customer_id}/profile", summary="客户画像")
def get_customer_profile(
    customer_id: str,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("customer_profile.view")),
):
    svc = CustomerProfileService(session)
    return svc.get_profile(customer_id)


# ─── Auto-tag rules ─────────────────────────────────────────────────────────


@router.get("/api/auto-tag-rules", summary="自动打标规则列表")
def list_rules(
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("customer_profile.view")),
):
    svc = CustomerProfileService(session)
    rules = svc.list_rules()
    return [
        {
            "id": r.id,
            "name": r.name,
            "condition_type": r.condition_type,
            "condition_operator": r.condition_operator,
            "condition_value": float(r.condition_value),
            "tag_name": r.tag_name,
            "is_enabled": r.is_enabled,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rules
    ]


@router.post("/api/auto-tag-rules", summary="创建打标规则", status_code=201)
def create_rule(
    body: CreateRuleRequest,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("customer_profile.view")),
):
    svc = CustomerProfileService(session)
    rule = svc.create_rule(
        agency_id=None,
        name=body.name,
        condition_type=body.condition_type,
        condition_operator=body.condition_operator,
        condition_value=body.condition_value,
        tag_name=body.tag_name,
    )
    return {
        "id": rule.id,
        "name": rule.name,
        "condition_type": rule.condition_type,
        "condition_operator": rule.condition_operator,
        "condition_value": float(rule.condition_value),
        "tag_name": rule.tag_name,
    }


@router.patch("/api/auto-tag-rules/{rule_id}", summary="编辑打标规则")
def update_rule(
    rule_id: str,
    body: UpdateRuleRequest,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("customer_profile.view")),
):
    svc = CustomerProfileService(session)
    kwargs = {k: v for k, v in body.model_dump().items() if v is not None}
    rule = svc.update_rule(rule_id, **kwargs)
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")
    return {
        "id": rule.id,
        "name": rule.name,
        "is_enabled": rule.is_enabled,
    }


@router.delete("/api/auto-tag-rules/{rule_id}", summary="删除打标规则")
def delete_rule(
    rule_id: str,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("customer_profile.view")),
):
    svc = CustomerProfileService(session)
    if not svc.delete_rule(rule_id):
        raise HTTPException(status_code=404, detail="规则不存在")
    return {"success": True}


@router.post("/api/auto-tag-rules/{rule_id}/evaluate", summary="评估打标规则")
def evaluate_rule(
    rule_id: str,
    body: EvaluateRequest,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("customer_profile.view")),
):
    svc = CustomerProfileService(session)
    # Evaluate all rules; not just one
    tags = svc.evaluate_auto_tags(body.user_id)
    return {
        "user_id": body.user_id,
        "matched_tags": tags,
    }
