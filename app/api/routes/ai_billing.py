"""AI billing API routes: rates, quotas, usage, bills, warnings."""
from decimal import Decimal
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, require_permission
from app.core.auth import RequestActor
from app.db.models import AiProviderRate, AgencyFreeQuota, AgencyMonthlyBill
from app.services.ai_usage_service import AiUsageService

router = APIRouter(prefix="/api/ai-billing", tags=["ai-billing"])


class RateUpdateRequest(BaseModel):
    cost_per_message: float
    currency: str = "CNY"
    is_enabled: bool = True


class QuotaUpdateRequest(BaseModel):
    free_ai_messages: int = 0
    free_translations: int = 0


# ── Rates ──

@router.get("/rates")
def list_rates(
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("ai_billing.view_rates")),
) -> list[dict]:
    rows = session.execute(select(AiProviderRate)).scalars().all()
    return [
        {
            "id": r.id,
            "provider_name": r.provider_name,
            "cost_per_message": float(r.cost_per_message),
            "currency": r.currency,
            "is_enabled": r.is_enabled,
        }
        for r in rows
    ]


@router.put("/rates/{provider_name}")
def update_rate(
    provider_name: str,
    data: RateUpdateRequest,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("ai_billing.edit_rates")),
) -> dict:
    existing = session.execute(
        select(AiProviderRate).where(AiProviderRate.provider_name == provider_name)
    ).scalar_one_or_none()
    if existing:
        existing.cost_per_message = Decimal(str(data.cost_per_message))
        existing.currency = data.currency
        existing.is_enabled = data.is_enabled
    else:
        existing = AiProviderRate(
            id=str(uuid4()),
            provider_name=provider_name,
            cost_per_message=Decimal(str(data.cost_per_message)),
            currency=data.currency,
            is_enabled=data.is_enabled,
        )
        session.add(existing)
    session.flush()
    return {"provider_name": provider_name, "cost_per_message": data.cost_per_message}


# ── Quotas ──

@router.get("/quotas")
def list_quotas(
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("ai_billing.view_quotas")),
    agency_id: str | None = None,
) -> list[dict]:
    query = select(AgencyFreeQuota)
    if agency_id:
        query = query.where(AgencyFreeQuota.agency_id == agency_id)
    rows = session.execute(query).scalars().all()
    return [
        {
            "id": r.id,
            "agency_id": r.agency_id,
            "billing_month": r.billing_month,
            "free_ai_messages": r.free_ai_messages,
            "free_translations": r.free_translations,
            "used_ai_messages": r.used_ai_messages,
            "used_translations": r.used_translations,
        }
        for r in rows
    ]


@router.put("/quotas/{agency_id}")
def update_quota(
    agency_id: str,
    data: QuotaUpdateRequest,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("ai_billing.edit_quotas")),
) -> dict:
    import datetime
    month = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m")
    existing = session.execute(
        select(AgencyFreeQuota).where(
            AgencyFreeQuota.agency_id == agency_id,
            AgencyFreeQuota.billing_month == month,
        )
    ).scalar_one_or_none()
    if existing:
        existing.free_ai_messages = data.free_ai_messages
        existing.free_translations = data.free_translations
    else:
        existing = AgencyFreeQuota(
            id=str(uuid4()),
            agency_id=agency_id,
            billing_month=month,
            free_ai_messages=data.free_ai_messages,
            free_translations=data.free_translations,
        )
        session.add(existing)
    session.flush()
    return {"agency_id": agency_id, "month": month, "free_ai_messages": data.free_ai_messages, "free_translations": data.free_translations}


# ── Usage ──

@router.get("/usage")
def get_usage(
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("ai_billing.view_usage")),
    agency_id: str | None = None,
    month: str | None = None,
) -> list[dict]:
    import datetime
    month = month or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m")
    svc = AiUsageService(session)
    if agency_id:
        return [svc.get_monthly_usage(agency_id, month)]
    # All agencies
    rows = session.execute(select(AgencyFreeQuota)).scalars().all()
    agency_ids = set(r.agency_id for r in rows)
    results = []
    for aid in agency_ids:
        results.append(svc.get_monthly_usage(aid, month))
    return results


@router.get("/usage/{site_id}")
def get_site_usage(
    site_id: str,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("ai_billing.view_usage")),
    month: str | None = None,
) -> dict:
    import datetime
    month = month or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m")
    svc = AiUsageService(session)
    return svc.get_site_usage(site_id, month)


# ── Bills ──

@router.get("/bills")
def list_bills(
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("ai_billing.view_bills")),
    agency_id: str | None = None,
) -> list[dict]:
    query = select(AgencyMonthlyBill).order_by(AgencyMonthlyBill.billing_month.desc())
    if agency_id:
        query = query.where(AgencyMonthlyBill.agency_id == agency_id)
    rows = session.execute(query).scalars().all()
    return [
        {
            "id": r.id,
            "agency_id": r.agency_id,
            "billing_month": r.billing_month,
            "ai_cost": float(r.ai_cost),
            "translation_cost": float(r.translation_cost),
            "total_cost": float(r.total_cost),
            "free_ai_used": r.free_ai_used,
            "free_translation_used": r.free_translation_used,
            "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@router.get("/bills/{agency_id}/{month}")
def get_bill_detail(
    agency_id: str,
    month: str,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("ai_billing.view_bills")),
) -> dict:
    bill = session.execute(
        select(AgencyMonthlyBill).where(
            AgencyMonthlyBill.agency_id == agency_id,
            AgencyMonthlyBill.billing_month == month,
        )
    ).scalar_one_or_none()
    if bill is None:
        raise HTTPException(status_code=404, detail="Bill not found")
    return {
        "id": bill.id,
        "agency_id": bill.agency_id,
        "billing_month": bill.billing_month,
        "ai_cost": float(bill.ai_cost),
        "translation_cost": float(bill.translation_cost),
        "total_cost": float(bill.total_cost),
        "free_ai_used": bill.free_ai_used,
        "free_translation_used": bill.free_translation_used,
        "status": bill.status,
        "details": bill.details,
        "created_at": bill.created_at.isoformat() if bill.created_at else None,
    }


# ── Warnings ──

@router.get("/warnings")
def get_warnings(
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("ai_billing.view_usage")),
) -> list[dict]:
    svc = AiUsageService(session)
    agencies = session.execute(select(AgencyFreeQuota.agency_id).distinct()).scalars().all()
    warnings = []
    for aid in agencies:
        w = svc.check_quota_warning(aid)
        if w:
            warnings.append(w)
    return warnings
