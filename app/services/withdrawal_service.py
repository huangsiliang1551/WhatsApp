"""Withdrawal management service with auto-approve, freeze detection and fee calculation."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4
from typing import Any

from sqlalchemy import select, func, and_
from sqlalchemy.orm import Session

from app.db.models import WithdrawalRecord, WithdrawalSetting


class WithdrawalService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_withdrawal(
        self, user_id: str, amount: Decimal, site_id: str | None = None, agency_id: str | None = None
    ) -> WithdrawalRecord:
        settings = None
        if agency_id:
            settings = self._session.execute(
                select(WithdrawalSetting).where(WithdrawalSetting.agency_id == agency_id)
            ).scalar_one_or_none()

        # Validate minimum
        min_amount = settings.min_withdraw_amount if settings else Decimal("10")
        if amount < min_amount:
            raise ValueError(f"Withdrawal amount below minimum ({min_amount})")

        # Fee calculation
        fee = Decimal("0")
        if settings and settings.fee_enabled:
            fee = (amount * settings.fee_rate).quantize(Decimal("0.01"))
        net_amount = (amount - fee).quantize(Decimal("0.01"))

        # Freeze check
        frozen = False
        frozen_reason = None
        if settings and settings.freeze_enabled:
            freeze_info = self.check_freeze(user_id, agency_id)
            if freeze_info.get("is_frozen"):
                frozen = True
                frozen_reason = freeze_info.get("reason")

        # Auto-approve check
        auto_approved = False
        status = "pending"
        if settings and settings.auto_approve_below and amount <= settings.auto_approve_below:
            auto_approved = True
            status = "approved"

        record = WithdrawalRecord(
            id=str(uuid4()),
            user_id=user_id,
            agency_id=agency_id,
            site_id=site_id,
            amount=amount,
            fee=fee,
            net_amount=net_amount,
            status="frozen" if frozen else status,
            auto_approved=auto_approved,
            frozen_reason=frozen_reason,
            frozen_at=datetime.now(timezone.utc) if frozen else None,
        )
        self._session.add(record)
        self._session.flush()
        return record

    def approve_withdrawal(self, record_id: str, approved_by: str) -> WithdrawalRecord:
        record = self._session.get(WithdrawalRecord, record_id)
        if record is None:
            raise LookupError("Withdrawal record not found")
        record.status = "approved"
        record.approved_by = approved_by
        record.approved_at = datetime.now(timezone.utc)
        self._session.flush()
        return record

    def reject_withdrawal(self, record_id: str, reason: str) -> WithdrawalRecord:
        record = self._session.get(WithdrawalRecord, record_id)
        if record is None:
            raise LookupError("Withdrawal record not found")
        record.status = "rejected"
        record.reject_reason = reason
        self._session.flush()
        return record

    def batch_approve(self, record_ids: list[str], approved_by: str) -> int:
        count = 0
        for rid in record_ids:
            try:
                self.approve_withdrawal(rid, approved_by)
                count += 1
            except LookupError:
                continue
        return count

    def batch_reject(self, record_ids: list[str], reason: str) -> int:
        count = 0
        for rid in record_ids:
            try:
                self.reject_withdrawal(rid, reason)
                count += 1
            except LookupError:
                continue
        return count

    def check_freeze(self, user_id: str, agency_id: str | None) -> dict:
        settings = None
        if agency_id:
            settings = self._session.execute(
                select(WithdrawalSetting).where(WithdrawalSetting.agency_id == agency_id)
            ).scalar_one_or_none()
        if not settings or not settings.freeze_enabled:
            return {"is_frozen": False}

        threshold_hours = settings.freeze_threshold_hours or 24
        threshold_count = settings.freeze_threshold_count or 5
        since = datetime.now(timezone.utc) - timedelta(hours=threshold_hours)

        recent_count = self._session.scalar(
            select(func.count()).select_from(WithdrawalRecord).where(
                WithdrawalRecord.user_id == user_id,
                WithdrawalRecord.created_at >= since,
                WithdrawalRecord.status.in_(["pending", "approved"]),
            )
        ) or 0

        if recent_count >= threshold_count:
            return {
                "is_frozen": True,
                "reason": f"超过 {threshold_hours} 小时内 {threshold_count} 次提现限制",
                "recent_count": recent_count,
            }
        return {"is_frozen": False, "recent_count": recent_count}

    def unfreeze(self, record_id: str) -> WithdrawalRecord:
        record = self._session.get(WithdrawalRecord, record_id)
        if record is None:
            raise LookupError("Withdrawal record not found")
        if record.status != "frozen":
            raise ValueError("Record is not frozen")
        record.status = "pending"
        record.frozen_at = None
        record.frozen_reason = None
        self._session.flush()
        return record

    def get_settings(self, agency_id: str) -> dict | None:
        s = self._session.execute(
            select(WithdrawalSetting).where(WithdrawalSetting.agency_id == agency_id)
        ).scalar_one_or_none()
        if s is None:
            return None
        return {
            "agency_id": s.agency_id,
            "auto_approve_below": float(s.auto_approve_below) if s.auto_approve_below else None,
            "min_withdraw_amount": float(s.min_withdraw_amount),
            "max_daily_withdraw": float(s.max_daily_withdraw) if s.max_daily_withdraw else None,
            "fee_enabled": s.fee_enabled,
            "fee_rate": float(s.fee_rate),
            "freeze_enabled": s.freeze_enabled,
            "freeze_threshold_count": s.freeze_threshold_count,
            "freeze_threshold_hours": s.freeze_threshold_hours,
        }

    def upsert_settings(self, agency_id: str, data: dict[str, Any]) -> dict:
        existing = self._session.execute(
            select(WithdrawalSetting).where(WithdrawalSetting.agency_id == agency_id)
        ).scalar_one_or_none()
        if existing:
            for key in ("auto_approve_below", "min_withdraw_amount", "max_daily_withdraw",
                        "fee_enabled", "fee_rate", "freeze_enabled", "freeze_threshold_count", "freeze_threshold_hours"):
                if key in data:
                    setattr(existing, key, data[key])
            existing.updated_at = datetime.now(timezone.utc)
            obj = existing
        else:
            obj = WithdrawalSetting(
                id=str(uuid4()),
                agency_id=agency_id,
                auto_approve_below=data.get("auto_approve_below"),
                min_withdraw_amount=data.get("min_withdraw_amount", 10),
                max_daily_withdraw=data.get("max_daily_withdraw"),
                fee_enabled=data.get("fee_enabled", False),
                fee_rate=data.get("fee_rate", 0),
                freeze_enabled=data.get("freeze_enabled", True),
                freeze_threshold_count=data.get("freeze_threshold_count", 5),
                freeze_threshold_hours=data.get("freeze_threshold_hours", 24),
            )
            self._session.add(obj)
        self._session.flush()
        return self.get_settings(agency_id) or {}
