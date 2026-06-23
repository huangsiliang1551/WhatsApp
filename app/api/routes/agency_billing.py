"""Shared agency billing helpers for scoped agency routes."""

from datetime import date
from http import HTTPStatus
from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AgencyBilling

VALID_BILLING_STATUSES = {"draft", "pending", "paid", "verified", "cancelled"}
AGENCY_BILLING_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"pending", "cancelled"},
    "pending": {"paid", "cancelled"},
    "paid": {"verified"},
    "verified": set(),
    "cancelled": set(),
}


class LineItem(BaseModel):
    description: str
    quantity: int = 1
    unit_price: float


def parse_billing_date(value: str | None) -> date | None:
    if value is None:
        return None
    return date.fromisoformat(value)


def serialize_agency_billing(billing: AgencyBilling) -> dict[str, Any]:
    return {
        "id": billing.id,
        "agency_id": billing.agency_id,
        "billing_type": billing.billing_type,
        "amount": float(billing.amount),
        "billing_period_start": (
            billing.billing_period_start.isoformat()
            if billing.billing_period_start is not None
            else None
        ),
        "billing_period_end": (
            billing.billing_period_end.isoformat()
            if billing.billing_period_end is not None
            else None
        ),
        "status": billing.status,
        "line_items": billing.line_items or [],
        "created_at": billing.created_at.isoformat() if billing.created_at else None,
    }


def build_agency_billing_list_stmt(
    *,
    agency_id: str | None = None,
    status: str | None = None,
    billing_type: str | None = None,
    period_start: date | None = None,
    period_end: date | None = None,
):
    stmt = select(AgencyBilling)
    if agency_id is not None:
        stmt = stmt.where(AgencyBilling.agency_id == agency_id)
    if status is not None:
        stmt = stmt.where(AgencyBilling.status == status)
    if billing_type is not None:
        stmt = stmt.where(AgencyBilling.billing_type == billing_type)
    if period_start is not None:
        stmt = stmt.where(AgencyBilling.billing_period_start >= period_start)
    if period_end is not None:
        stmt = stmt.where(AgencyBilling.billing_period_end <= period_end)
    return stmt.order_by(AgencyBilling.created_at.desc())


def get_agency_billing_or_404(session: Session, billing_id: str) -> AgencyBilling:
    billing = session.get(AgencyBilling, billing_id)
    if billing is None:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Billing record not found")
    return billing


def ensure_billing_matches_agency_scope(billing: AgencyBilling, agency_id: str) -> AgencyBilling:
    if billing.agency_id != agency_id:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Billing record not found")
    return billing


def validate_billing_status_transition(current_status: str, target_status: str) -> None:
    if target_status not in VALID_BILLING_STATUSES:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=(
                "Invalid billing status, must be one of: "
                + ", ".join(sorted(VALID_BILLING_STATUSES))
            ),
        )
    if target_status == current_status:
        return
    allowed_targets = AGENCY_BILLING_STATUS_TRANSITIONS.get(current_status, set())
    if target_status not in allowed_targets:
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail=f"Invalid billing status transition: {current_status} -> {target_status}.",
        )
