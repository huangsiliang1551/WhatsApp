"""Finance management API: recharge, withdrawal, reports, anomaly alerts, reconciliation."""
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from typing import Any

from app.api.deps import get_db_session, require_permission
from app.core.auth import RequestActor
from app.db.models import (
    RechargeRecord,
    WithdrawalRecord,
    WithdrawalSetting,
    PaymentCallback,
    PaymentReconciliation,
)
from app.services.withdrawal_service import WithdrawalService
from app.services.finance_report_service import FinanceReportService
from app.services.payment_reconciliation_service import PaymentReconciliationService
from app.services.channel_health_service import ChannelHealthService

router = APIRouter(prefix="/api/finance", tags=["finance"])


class ApproveRequest(BaseModel):
    approved_by: str


class RejectRequest(BaseModel):
    reason: str


class BatchIdsRequest(BaseModel):
    ids: list[str]


class BatchRejectRequest(BaseModel):
    ids: list[str]
    reason: str


class UnfreezeRequest(BaseModel):
    pass


class ManualRechargeRequest(BaseModel):
    user_id: str
    amount: float
    agency_id: str | None = None
    site_id: str | None = None


class WithdrawalSettingsUpdate(BaseModel):
    auto_approve_below: float | None = None
    min_withdraw_amount: float | None = None
    max_daily_withdraw: float | None = None
    fee_enabled: bool | None = None
    fee_rate: float | None = None
    freeze_enabled: bool | None = None
    freeze_threshold_count: int | None = None
    freeze_threshold_hours: int | None = None


class ReconcileRequest(BaseModel):
    channel_id: str
    date: str


class ResolveRequest(BaseModel):
    resolution: str
    resolved_by: str


# ── Recharge Records ──

@router.get("/recharge-records")
def list_recharge_records(
    session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("finance.view_recharge")),
    agency_id: str | None = None,
    site_id: str | None = None,
    status: str | None = None,
    sort_field: str | None = Query(None, description="排序字段名，如 amount, created_at"),
    sort_order: str | None = Query(None, description="排序方向：asc 或 desc"),
) -> list[dict]:
    svc = FinanceReportService(session)
    filters = {}
    effective_agency = agency_id if actor.is_super_admin else actor.agency_id
    if effective_agency:
        filters["agency_id"] = effective_agency
    elif not actor.is_super_admin:
        return []
    if site_id:
        filters["site_id"] = site_id
    if status:
        filters["status"] = status
    return svc.get_recharge_report(filters or None, sort_field=sort_field, sort_order=sort_order)


# ── Withdrawal Records ──

@router.get("/withdrawal-records")
def list_withdrawal_records(
    session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("finance.view_withdrawal")),
    agency_id: str | None = None,
    site_id: str | None = None,
    status: str | None = None,
    sort_field: str | None = Query(None, description="排序字段名，如 amount, created_at"),
    sort_order: str | None = Query(None, description="排序方向：asc 或 desc"),
) -> list[dict]:
    svc = FinanceReportService(session)
    filters = {}
    effective_agency = agency_id if actor.is_super_admin else actor.agency_id
    if effective_agency:
        filters["agency_id"] = effective_agency
    elif not actor.is_super_admin:
        return []
    if site_id:
        filters["site_id"] = site_id
    if status:
        filters["status"] = status
    return svc.get_withdrawal_report(filters or None, sort_field=sort_field, sort_order=sort_order)


@router.post("/withdrawals/{record_id}/approve")
def approve_withdrawal(
    record_id: str,
    data: ApproveRequest,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("finance.approve_withdrawal")),
) -> dict:
    svc = WithdrawalService(session)
    try:
        record = svc.approve_withdrawal(record_id, data.approved_by)
        return {"id": record.id, "status": record.status}
    except LookupError:
        raise HTTPException(status_code=404, detail="Withdrawal record not found")


@router.post("/withdrawals/{record_id}/reject")
def reject_withdrawal(
    record_id: str,
    data: RejectRequest,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("finance.approve_withdrawal")),
) -> dict:
    svc = WithdrawalService(session)
    try:
        record = svc.reject_withdrawal(record_id, data.reason)
        return {"id": record.id, "status": record.status}
    except LookupError:
        raise HTTPException(status_code=404, detail="Withdrawal record not found")


@router.post("/withdrawals/batch-approve")
def batch_approve_withdrawals(
    data: BatchIdsRequest,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("finance.approve_withdrawal")),
) -> dict:
    svc = WithdrawalService(session)
    count = svc.batch_approve(data.ids, _actor.actor_id)
    return {"approved_count": count}


@router.post("/withdrawals/batch-reject")
def batch_reject_withdrawals(
    data: BatchRejectRequest,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("finance.approve_withdrawal")),
) -> dict:
    svc = WithdrawalService(session)
    count = svc.batch_reject(data.ids, data.reason)
    return {"rejected_count": count}


@router.post("/withdrawals/{record_id}/unfreeze")
def unfreeze_withdrawal(
    record_id: str,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("finance.approve_withdrawal")),
) -> dict:
    svc = WithdrawalService(session)
    try:
        record = svc.unfreeze(record_id)
        return {"id": record.id, "status": record.status}
    except LookupError:
        raise HTTPException(status_code=404, detail="Withdrawal record not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Withdrawal Settings ──

@router.get("/withdrawal-settings/{agency_id}")
def get_withdrawal_settings(
    agency_id: str,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("finance.view_withdrawal")),
) -> dict:
    svc = WithdrawalService(session)
    settings = svc.get_settings(agency_id)
    if settings is None:
        raise HTTPException(status_code=404, detail="Settings not found")
    return settings


@router.put("/withdrawal-settings/{agency_id}")
def update_withdrawal_settings(
    agency_id: str,
    data: WithdrawalSettingsUpdate,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("finance.approve_withdrawal")),
) -> dict:
    svc = WithdrawalService(session)
    return svc.upsert_settings(agency_id, data.model_dump(exclude_none=True))


# ── Reports ──

@router.get("/report/recharge")
def recharge_report(
    session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("reports.finance")),
    agency_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[dict]:
    svc = FinanceReportService(session)
    filters = {}
    if agency_id:
        filters["agency_id"] = agency_id
    if date_from:
        filters["date_from"] = datetime.fromisoformat(date_from)
    if date_to:
        filters["date_to"] = datetime.fromisoformat(date_to)
    return svc.get_recharge_report(filters or None)


@router.get("/report/withdrawal")
def withdrawal_report(
    session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("reports.finance")),
    agency_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[dict]:
    svc = FinanceReportService(session)
    filters = {}
    if agency_id:
        filters["agency_id"] = agency_id
    if date_from:
        filters["date_from"] = datetime.fromisoformat(date_from)
    if date_to:
        filters["date_to"] = datetime.fromisoformat(date_to)
    return svc.get_withdrawal_report(filters or None)


@router.get("/report/summary")
def finance_summary(
    session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("reports.finance")),
    agency_id: str | None = None,
) -> dict:
    svc = FinanceReportService(session)
    effective_agency = agency_id if actor.is_super_admin else actor.agency_id
    if effective_agency:
        return svc.get_finance_summary({"agency_id": effective_agency})
    if not actor.is_super_admin:
        return {"recharge_amount": 0, "recharge_count": 0, "withdrawal_amount": 0, "withdrawal_fee": 0, "withdrawal_count": 0, "net_recharge": 0}
    return svc.get_finance_summary()


# ── Anomaly Alerts ──

@router.get("/anomaly-alerts")
def anomaly_alerts(
    session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("reports.finance")),
) -> list[dict]:
    svc = FinanceReportService(session)
    agency_id = None if actor.is_super_admin else actor.agency_id
    return svc.get_anomaly_alerts(agency_id=agency_id)


# ── Manual Recharge ──

@router.post("/manual-recharge")
def manual_recharge(
    data: ManualRechargeRequest,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("finance.edit_channels")),
) -> dict:
    svc = FinanceReportService(session)
    return svc.manual_recharge(
        user_id=data.user_id,
        amount=Decimal(str(data.amount)),
        agency_id=data.agency_id,
        site_id=data.site_id,
    )


# ── Reconciliation ──

@router.post("/reconcile")
def trigger_reconcile(
    data: ReconcileRequest,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("reports.finance")),
) -> dict:
    svc = PaymentReconciliationService(session)
    from datetime import date
    d = date.fromisoformat(data.date)
    rec = svc.auto_reconcile(data.channel_id, d)
    return {"id": rec.id, "status": rec.status, "difference": float(rec.difference or 0)}


@router.get("/reconciliations")
def list_reconciliations(
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("reports.finance")),
    channel_id: str | None = None,
) -> list[dict]:
    svc = PaymentReconciliationService(session)
    return svc.get_reconciliations(channel_id)


@router.post("/reconciliations/{rec_id}/resolve")
def resolve_reconciliation(
    rec_id: str,
    data: ResolveRequest,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("reports.finance")),
) -> dict:
    svc = PaymentReconciliationService(session)
    try:
        rec = svc.resolve_mismatch(rec_id, data.resolution, data.resolved_by)
        return {"id": rec.id, "status": rec.status}
    except LookupError:
        raise HTTPException(status_code=404, detail="Reconciliation not found")


# ── Channel Health ──

@router.get("/channel-health")
def channel_health(
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("finance.view_channels")),
) -> list[dict]:
    svc = ChannelHealthService(session)
    return svc.get_all_channels_health()


# ── Callback Retry ──

@router.post("/callbacks/{callback_id}/retry")
def retry_callback(
    callback_id: str,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("finance.edit_channels")),
) -> dict:
    cb = session.get(PaymentCallback, callback_id)
    if cb is None:
        raise HTTPException(status_code=404, detail="Callback not found")
    if cb.retry_count >= cb.max_retries:
        raise HTTPException(status_code=400, detail="Max retries reached")
    cb.retry_count += 1
    cb.processed = False
    cb.processed_at = None
    cb.error_message = None
    session.flush()
    return {"callback_id": callback_id, "retry_count": cb.retry_count}
