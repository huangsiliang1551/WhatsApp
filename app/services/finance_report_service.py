"""Finance reports: recharge, withdrawal, summary and anomaly alerts."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select, func, and_
from sqlalchemy.orm import Session

from app.db.models import RechargeRecord, WithdrawalRecord


class FinanceReportService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_recharge_report(
        self,
        filters: dict | None = None,
        sort_field: str | None = None,
        sort_order: str | None = None,
    ) -> list[dict]:
        query = select(RechargeRecord)
        if filters:
            if filters.get("agency_id"):
                query = query.where(RechargeRecord.agency_id == filters["agency_id"])
            if filters.get("site_id"):
                query = query.where(RechargeRecord.site_id == filters["site_id"])
            if filters.get("status"):
                query = query.where(RechargeRecord.status == filters["status"])
            if filters.get("date_from"):
                query = query.where(RechargeRecord.created_at >= filters["date_from"])
            if filters.get("date_to"):
                query = query.where(RechargeRecord.created_at <= filters["date_to"])
        # 动态排序：优先使用请求参数，否则默认按 created_at 降序
        if sort_field and hasattr(RechargeRecord, sort_field):
            column = getattr(RechargeRecord, sort_field)
            query = query.order_by(column.asc() if sort_order == "asc" else column.desc())
        else:
            query = query.order_by(RechargeRecord.created_at.desc())
        rows = self._session.execute(query).scalars().all()
        return [self._recharge_to_dict(r) for r in rows]

    def get_withdrawal_report(
        self,
        filters: dict | None = None,
        sort_field: str | None = None,
        sort_order: str | None = None,
    ) -> list[dict]:
        query = select(WithdrawalRecord)
        if filters:
            if filters.get("agency_id"):
                query = query.where(WithdrawalRecord.agency_id == filters["agency_id"])
            if filters.get("site_id"):
                query = query.where(WithdrawalRecord.site_id == filters["site_id"])
            if filters.get("status"):
                query = query.where(WithdrawalRecord.status == filters["status"])
            if filters.get("date_from"):
                query = query.where(WithdrawalRecord.created_at >= filters["date_from"])
            if filters.get("date_to"):
                query = query.where(WithdrawalRecord.created_at <= filters["date_to"])
        # 动态排序：优先使用请求参数，否则默认按 created_at 降序
        if sort_field and hasattr(WithdrawalRecord, sort_field):
            column = getattr(WithdrawalRecord, sort_field)
            query = query.order_by(column.asc() if sort_order == "asc" else column.desc())
        else:
            query = query.order_by(WithdrawalRecord.created_at.desc())
        rows = self._session.execute(query).scalars().all()
        return [self._withdrawal_to_dict(r) for r in rows]

    def get_finance_summary(self, filters: dict | None = None) -> dict:
        recharge_query = select(func.sum(RechargeRecord.amount), func.count(RechargeRecord.id))
        withdrawal_query = select(func.sum(WithdrawalRecord.amount), func.sum(WithdrawalRecord.fee), func.count(WithdrawalRecord.id))

        if filters:
            if filters.get("agency_id"):
                recharge_query = recharge_query.where(RechargeRecord.agency_id == filters["agency_id"])
                withdrawal_query = withdrawal_query.where(WithdrawalRecord.agency_id == filters["agency_id"])
            if filters.get("date_from"):
                recharge_query = recharge_query.where(RechargeRecord.created_at >= filters["date_from"])
                withdrawal_query = withdrawal_query.where(WithdrawalRecord.created_at >= filters["date_from"])
            if filters.get("date_to"):
                recharge_query = recharge_query.where(RechargeRecord.created_at <= filters["date_to"])
                withdrawal_query = withdrawal_query.where(WithdrawalRecord.created_at <= filters["date_to"])

        recharge_row = self._session.execute(recharge_query).one()
        recharge_total = recharge_row[0] or Decimal("0")
        recharge_count = recharge_row[1] or 0

        withdrawal_row = self._session.execute(withdrawal_query).one()
        withdrawal_total = withdrawal_row[0] or Decimal("0")
        withdrawal_fee = withdrawal_row[1] or Decimal("0")
        withdrawal_count = withdrawal_row[2] or 0

        return {
            "recharge_amount": float(recharge_total),
            "recharge_count": recharge_count,
            "withdrawal_amount": float(withdrawal_total),
            "withdrawal_fee": float(withdrawal_fee),
            "withdrawal_count": withdrawal_count,
            "net_recharge": float(recharge_total - withdrawal_total),
        }

    def get_anomaly_alerts(self, agency_id: str | None = None) -> list[dict]:
        alerts = []
        now = datetime.now(timezone.utc)

        # Large recharges (> 10000) in last 24h
        since = now - timedelta(hours=24)
        recharge_query = select(RechargeRecord).where(
            RechargeRecord.created_at >= since,
            RechargeRecord.amount >= 10000,
        )
        if agency_id:
            recharge_query = recharge_query.where(RechargeRecord.agency_id == agency_id)
        large = self._session.execute(recharge_query).scalars().all()
        for r in large:
            alerts.append({
                "type": "large_recharge",
                "record_id": r.id,
                "amount": float(r.amount),
                "time": r.created_at.isoformat(),
                "message": f"大额充值: {float(r.amount)} 元",
            })

        # Frequent withdrawals (>3) in last 24h per user
        withdrawal_query = select(WithdrawalRecord.user_id, func.count().label("cnt"))
        withdrawal_query = withdrawal_query.where(WithdrawalRecord.created_at >= since)
        if agency_id:
            withdrawal_query = withdrawal_query.where(WithdrawalRecord.agency_id == agency_id)
        freq = self._session.execute(
            withdrawal_query.group_by(WithdrawalRecord.user_id).having(func.count() > 3)
        ).all()
        for row in freq:
            alerts.append({
                "type": "frequent_withdrawal",
                "user_id": row[0],
                "count": row[1],
                "message": f"频繁提现: 用户 {row[0][:12]}... 在 24h 内提现 {row[1]} 次",
            })

        # Callback failures in last 24h
        from app.db.models import PaymentCallback
        failed_callbacks = self._session.execute(
            select(PaymentCallback).where(
                PaymentCallback.created_at >= since,
                PaymentCallback.signature_valid.is_(False),
            )
        ).scalars().all()
        for cb in failed_callbacks:
            alerts.append({
                "type": "callback_failure",
                "record_id": cb.id,
                "message": f"回调签名验证失败: {cb.id[:12]}...",
            })

        return alerts

    def manual_recharge(self, user_id: str, amount: Decimal, agency_id: str | None = None, site_id: str | None = None) -> dict:
        record = RechargeRecord(
            id=__import__("uuid").uuid4().hex[:36],
            user_id=user_id,
            agency_id=agency_id,
            site_id=site_id,
            amount=amount,
            currency="CNY",
            status="completed",
        )
        self._session.add(record)
        self._session.flush()
        return self._recharge_to_dict(record)

    def _recharge_to_dict(self, r: RechargeRecord) -> dict:
        return {
            "id": r.id,
            "user_id": r.user_id,
            "agency_id": r.agency_id,
            "site_id": r.site_id,
            "amount": float(r.amount),
            "currency": r.currency,
            "converted_amount": float(r.converted_amount) if r.converted_amount else None,
            "status": r.status,
            "channel_order_id": r.channel_order_id,
            "callback_verified": r.callback_verified,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }

    def _withdrawal_to_dict(self, w: WithdrawalRecord) -> dict:
        return {
            "id": w.id,
            "user_id": w.user_id,
            "agency_id": w.agency_id,
            "site_id": w.site_id,
            "amount": float(w.amount),
            "fee": float(w.fee),
            "net_amount": float(w.net_amount) if w.net_amount else None,
            "status": w.status,
            "auto_approved": w.auto_approved,
            "approved_by": w.approved_by,
            "approved_at": w.approved_at.isoformat() if w.approved_at else None,
            "reject_reason": w.reject_reason,
            "frozen_reason": w.frozen_reason,
            "created_at": w.created_at.isoformat() if w.created_at else None,
        }
