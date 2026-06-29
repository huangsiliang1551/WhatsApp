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
    AppUser,
    RechargeRecord,
    WithdrawalRecord,
    WithdrawalSetting,
    PaymentCallback,
    PaymentReconciliation,
)
from app.schemas.finance_bonus import BonusGrantCreateRequest, BonusGrantDecisionRequest
from app.schemas.recharge_repair import RechargeRepairCreateRequest
from app.schemas.wallet_ledger import ManualRechargeRequest
from app.services.withdrawal_service import WithdrawalService
from app.services.finance_report_service import FinanceReportService
from app.services.payment_reconciliation_service import PaymentReconciliationService
from app.services.channel_health_service import ChannelHealthService
from app.services.bonus_grant_service import BonusGrantService
from app.services.recharge_repair_service import RechargeRepairService

router = APIRouter(prefix="/api/finance", tags=["finance"])


def _resolve_effective_finance_account_id(
    actor: RequestActor,
    requested_account_id: str | None,
) -> str | None:
    if actor.is_super_admin:
        return requested_account_id
    if requested_account_id is not None:
        actor.require_account_access(requested_account_id)
        return requested_account_id
    if len(actor.account_ids) == 1:
        return actor.account_ids[0]
    return None


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


class ReconciliationItemActionRequest(BaseModel):
    reason: str | None = None


# ── Recharge Records ──

@router.get("/recharge-records")
def list_recharge_records(
    session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("finance.view_recharge")),
    agency_id: str | None = None,
    site_id: str | None = None,
    status: str | None = None,
    source_type: str | None = None,
    fund_scope: str | None = None,
    include_bonus: bool = True,
    sort_field: str | None = Query(None, description="排序字段名，如 amount, created_at"),
    sort_order: str | None = Query(None, description="排序方向：asc 或 desc"),
) -> list[dict]:
    svc = FinanceReportService(session)
    filters = {}
    effective_account_id = _resolve_effective_finance_account_id(actor, agency_id)
    if effective_account_id:
        filters["agency_id"] = effective_account_id
    elif not actor.is_super_admin:
        return []
    if site_id:
        filters["site_id"] = site_id
    if status:
        filters["status"] = status
    if source_type:
        filters["source_type"] = source_type
    if fund_scope:
        filters["fund_scope"] = fund_scope
    filters["include_bonus"] = include_bonus
    return svc.get_recharge_report(
        filters or None,
        sort_field=sort_field,
        sort_order=sort_order,
        scope_actor=None if actor.is_super_admin else actor,
    )


# ── Withdrawal Records ──

@router.get("/withdrawal-records")
def list_withdrawal_records(
    session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("finance.view_withdrawal")),
    agency_id: str | None = None,
    site_id: str | None = None,
    status: str | None = None,
    fund_scope: str | None = None,
    include_bonus: bool = True,
    sort_field: str | None = Query(None, description="排序字段名，如 amount, created_at"),
    sort_order: str | None = Query(None, description="排序方向：asc 或 desc"),
) -> list[dict]:
    svc = FinanceReportService(session)
    filters = {}
    effective_account_id = _resolve_effective_finance_account_id(actor, agency_id)
    if effective_account_id:
        filters["agency_id"] = effective_account_id
    elif not actor.is_super_admin:
        return []
    if site_id:
        filters["site_id"] = site_id
    if status:
        filters["status"] = status
    if fund_scope:
        filters["fund_scope"] = fund_scope
    filters["include_bonus"] = include_bonus
    return svc.get_withdrawal_report(
        filters or None,
        sort_field=sort_field,
        sort_order=sort_order,
        scope_actor=None if actor.is_super_admin else actor,
    )


@router.get("/wallet-ledgers")
def list_wallet_ledgers(
    session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("reports.finance")),
    agency_id: str | None = None,
    user_id: str | None = None,
    status: str | None = None,
    source_type: str | None = None,
    transaction_type: str | None = None,
    fund_scope: str | None = None,
    sort_field: str | None = Query(None, description="排序字段名，如 amount, created_at"),
    sort_order: str | None = Query(None, description="排序方向：asc 或 desc"),
) -> list[dict]:
    svc = FinanceReportService(session)
    filters = {}
    effective_account_id = _resolve_effective_finance_account_id(actor, agency_id)
    if effective_account_id:
        filters["agency_id"] = effective_account_id
    elif not actor.is_super_admin:
        return []
    if user_id:
        filters["user_id"] = user_id
    if status:
        filters["status"] = status
    if source_type:
        filters["source_type"] = source_type
    if transaction_type:
        filters["transaction_type"] = transaction_type
    if fund_scope:
        filters["fund_scope"] = fund_scope
    return svc.get_wallet_ledger_report(
        filters or None,
        sort_field=sort_field,
        sort_order=sort_order,
        scope_actor=None if actor.is_super_admin else actor,
    )


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
    actor: RequestActor = Depends(require_permission("finance.view_withdrawal")),
) -> dict:
    actor.require_account_access(agency_id)
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
    actor: RequestActor = Depends(require_permission("finance.approve_withdrawal")),
) -> dict:
    actor.require_account_access(agency_id)
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
    source_type: str | None = None,
    fund_scope: str | None = None,
    include_bonus: bool = True,
) -> list[dict]:
    svc = FinanceReportService(session)
    filters = {}
    effective_account_id = _resolve_effective_finance_account_id(actor, agency_id)
    if effective_account_id:
        filters["agency_id"] = effective_account_id
    elif not actor.is_super_admin:
        return []
    if date_from:
        filters["date_from"] = datetime.fromisoformat(date_from)
    if date_to:
        filters["date_to"] = datetime.fromisoformat(date_to)
    if source_type:
        filters["source_type"] = source_type
    if fund_scope:
        filters["fund_scope"] = fund_scope
    filters["include_bonus"] = include_bonus
    return svc.get_recharge_report(filters or None)


@router.get("/report/withdrawal")
def withdrawal_report(
    session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("reports.finance")),
    agency_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    fund_scope: str | None = None,
    include_bonus: bool = True,
) -> list[dict]:
    svc = FinanceReportService(session)
    filters = {}
    effective_account_id = _resolve_effective_finance_account_id(actor, agency_id)
    if effective_account_id:
        filters["agency_id"] = effective_account_id
    elif not actor.is_super_admin:
        return []
    if date_from:
        filters["date_from"] = datetime.fromisoformat(date_from)
    if date_to:
        filters["date_to"] = datetime.fromisoformat(date_to)
    if fund_scope:
        filters["fund_scope"] = fund_scope
    filters["include_bonus"] = include_bonus
    return svc.get_withdrawal_report(filters or None)


@router.get("/report/summary")
def finance_summary(
    session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("reports.finance")),
    agency_id: str | None = None,
    include_bonus: bool = True,
) -> dict:
    svc = FinanceReportService(session)
    effective_account_id = _resolve_effective_finance_account_id(actor, agency_id)
    if effective_account_id:
        return svc.get_finance_summary(
            {"agency_id": effective_account_id, "include_bonus": include_bonus},
            scope_actor=None if actor.is_super_admin else actor,
        )
    if not actor.is_super_admin:
        return {"recharge_amount": 0, "recharge_count": 0, "withdrawal_amount": 0, "withdrawal_fee": 0, "withdrawal_count": 0, "net_recharge": 0}
    return svc.get_finance_summary({"include_bonus": include_bonus})


# ── Anomaly Alerts ──

@router.get("/anomaly-alerts")
def anomaly_alerts(
    session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("reports.finance")),
) -> list[dict]:
    svc = FinanceReportService(session)
    account_id = None if actor.is_super_admin else _resolve_effective_finance_account_id(actor, None)
    if account_id is None and not actor.is_super_admin:
        return []
    return svc.get_anomaly_alerts(agency_id=account_id, scope_actor=None if actor.is_super_admin else actor)


# ── Manual Recharge ──

@router.post("/manual-recharge")
def manual_recharge(
    data: ManualRechargeRequest,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("finance.edit_channels")),
) -> dict:
    svc = FinanceReportService(session)
    try:
        return svc.manual_recharge(
            user_id=data.user_id,
            amount=Decimal(str(data.amount)),
            agency_id=data.agency_id,
            site_id=data.site_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ── Reconciliation ──

def _resolve_public_user_id(session: Session, user_id: str | None) -> str | None:
    if not user_id:
        return None
    return session.execute(
        select(AppUser.public_user_id).where(AppUser.id == user_id)
    ).scalar_one_or_none()


def _serialize_bonus_grant(session: Session, record: Any) -> dict[str, Any]:
    return {
        "id": record.id,
        "account_id": record.account_id,
        "grant_no": record.grant_no,
        "user_id": record.user_id,
        "public_user_id": _resolve_public_user_id(session, record.user_id),
        "amount": float(record.amount),
        "currency": record.currency,
        "source_type": record.source_type,
        "reason": record.reason,
        "remark": record.remark,
        "status": record.status,
        "operator_id": record.operator_id,
        "approved_by": record.approved_by,
        "approved_at": record.approved_at.isoformat() if record.approved_at else None,
        "credited_at": record.credited_at.isoformat() if record.credited_at else None,
        "rejected_at": record.rejected_at.isoformat() if record.rejected_at else None,
        "ledger_id": record.ledger_id,
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }


def _serialize_recharge_repair(session: Session, record: Any) -> dict[str, Any]:
    return {
        "id": record.id,
        "account_id": record.account_id,
        "repair_no": record.repair_no,
        "user_id": record.user_id,
        "public_user_id": _resolve_public_user_id(session, record.user_id),
        "amount": float(record.amount),
        "currency": record.currency,
        "repair_type": record.repair_type,
        "reason": record.reason,
        "remark": record.remark,
        "status": record.status,
        "channel_id": record.channel_id,
        "platform_order_no": record.platform_order_no,
        "channel_order_no": record.channel_order_no,
        "operator_id": record.operator_id,
        "approved_by": record.approved_by,
        "approved_at": record.approved_at.isoformat() if record.approved_at else None,
        "credited_at": record.credited_at.isoformat() if record.credited_at else None,
        "rejected_at": record.rejected_at.isoformat() if record.rejected_at else None,
        "recharge_record_id": record.recharge_record_id,
        "ledger_id": record.ledger_id,
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }


@router.get("/bonus-grants")
def list_bonus_grants(
    session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("reports.finance")),
    account_id: str | None = None,
) -> list[dict[str, Any]]:
    svc = BonusGrantService(session)
    effective_account_id = _resolve_effective_finance_account_id(actor, account_id)
    if effective_account_id is None and not actor.is_super_admin:
        return []
    records = svc.list_grants(account_id=effective_account_id, scope_actor=None if actor.is_super_admin else actor)
    return [_serialize_bonus_grant(session, item) for item in records if actor.can_access_account(item.account_id)]


@router.post("/bonus-grants")
def create_bonus_grant(
    data: BonusGrantCreateRequest,
    session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("finance.edit_channels")),
) -> dict[str, Any]:
    actor.require_account_access(data.account_id)
    svc = BonusGrantService(session)
    try:
        record = svc.create_grant(
            account_id=data.account_id,
            user_id=data.user_id,
            amount=Decimal(str(data.amount)),
            currency=data.currency,
            reason=data.reason,
            remark=data.remark,
            source_type=data.source_type,
            operator_id=actor.actor_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _serialize_bonus_grant(session, record)


@router.post("/bonus-grants/{grant_id}/approve")
def approve_bonus_grant(
    grant_id: str,
    session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("finance.edit_channels")),
) -> dict[str, Any]:
    svc = BonusGrantService(session)
    try:
        record = svc.approve_grant(grant_id=grant_id, actor_id=actor.actor_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _serialize_bonus_grant(session, record)


@router.post("/bonus-grants/{grant_id}/reject")
def reject_bonus_grant(
    grant_id: str,
    data: BonusGrantDecisionRequest,
    session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("finance.edit_channels")),
) -> dict[str, Any]:
    svc = BonusGrantService(session)
    try:
        record = svc.reject_grant(grant_id=grant_id, actor_id=actor.actor_id, reason=data.reason)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _serialize_bonus_grant(session, record)


@router.get("/recharge-repairs")
def list_recharge_repairs(
    session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("reports.finance")),
    account_id: str | None = None,
) -> list[dict[str, Any]]:
    svc = RechargeRepairService(session)
    effective_account_id = _resolve_effective_finance_account_id(actor, account_id)
    if effective_account_id is None and not actor.is_super_admin:
        return []
    records = svc.list_repairs(account_id=effective_account_id, scope_actor=None if actor.is_super_admin else actor)
    return [_serialize_recharge_repair(session, item) for item in records if actor.can_access_account(item.account_id)]


@router.post("/recharge-repairs")
def create_recharge_repair(
    data: RechargeRepairCreateRequest,
    session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("finance.edit_channels")),
) -> dict[str, Any]:
    actor.require_account_access(data.account_id)
    svc = RechargeRepairService(session)
    try:
        record = svc.create_repair(
            account_id=data.account_id,
            user_id=data.user_id,
            amount=Decimal(str(data.amount)),
            currency=data.currency,
            repair_type=data.repair_type,
            reason=data.reason,
            remark=data.remark,
            channel_id=data.channel_id,
            platform_order_no=data.platform_order_no,
            channel_order_no=data.channel_order_no,
            operator_id=actor.actor_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _serialize_recharge_repair(session, record)


@router.post("/recharge-repairs/{repair_id}/approve")
def approve_recharge_repair(
    repair_id: str,
    session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("finance.edit_channels")),
) -> dict[str, Any]:
    svc = RechargeRepairService(session)
    try:
        record = svc.approve_repair(repair_id=repair_id, actor_id=actor.actor_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _serialize_recharge_repair(session, record)


@router.post("/recharge-repairs/{repair_id}/reject")
def reject_recharge_repair(
    repair_id: str,
    data: BonusGrantDecisionRequest,
    session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("finance.edit_channels")),
) -> dict[str, Any]:
    svc = RechargeRepairService(session)
    try:
        record = svc.reject_repair(repair_id=repair_id, actor_id=actor.actor_id, reason=data.reason)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _serialize_recharge_repair(session, record)


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
    session.commit()
    return {"id": rec.id, "status": rec.status, "difference": float(rec.difference or 0)}


@router.get("/reconciliations")
def list_reconciliations(
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("reports.finance")),
    channel_id: str | None = None,
) -> list[dict]:
    svc = PaymentReconciliationService(session)
    return svc.get_reconciliations(channel_id)


@router.get("/reconciliations/{rec_id}/items")
def list_reconciliation_items(
    rec_id: str,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("reports.finance")),
) -> list[dict]:
    svc = PaymentReconciliationService(session)
    return svc.get_reconciliation_items(rec_id)


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


@router.post("/reconciliation-items/{item_id}/create-repair")
def create_reconciliation_repair(
    item_id: str,
    session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("finance.edit_channels")),
) -> dict:
    svc = PaymentReconciliationService(session)
    try:
        item = svc.create_repair_for_item(item_id=item_id, operator_id=actor.actor_id or "system")
        session.commit()
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "id": item.id,
        "status": item.status,
        "repair_order_id": item.repair_order_id,
    }


@router.post("/reconciliation-items/{item_id}/ignore")
def ignore_reconciliation_item(
    item_id: str,
    data: ReconciliationItemActionRequest,
    session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("finance.edit_channels")),
) -> dict:
    svc = PaymentReconciliationService(session)
    try:
        item = svc.update_item_status(
            item_id=item_id,
            target_status="ignored",
            actor_id=actor.actor_id or "system",
            reason=data.reason,
        )
        session.commit()
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"id": item.id, "status": item.status}


@router.post("/reconciliation-items/{item_id}/resolve")
def resolve_reconciliation_item(
    item_id: str,
    data: ReconciliationItemActionRequest,
    session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("finance.edit_channels")),
) -> dict:
    svc = PaymentReconciliationService(session)
    try:
        item = svc.update_item_status(
            item_id=item_id,
            target_status="resolved",
            actor_id=actor.actor_id or "system",
            reason=data.reason,
        )
        session.commit()
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"id": item.id, "status": item.status}


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
