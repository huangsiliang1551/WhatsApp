"""Payment reconciliation service: auto-reconcile and mismatch resolution."""
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.db.models import PaymentReconciliation, RechargeRecord


class PaymentReconciliationService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def auto_reconcile(self, channel_id: str, reconcile_date: date) -> PaymentReconciliation:
        platform_total = self._session.scalar(
            select(func.sum(RechargeRecord.amount)).where(
                RechargeRecord.channel_id == channel_id,
                func.date(RechargeRecord.created_at) == reconcile_date,
                RechargeRecord.status == "completed",
            )
        ) or Decimal("0")

        # In production, channel_amount would come from the payment provider API
        channel_amount = Decimal("0")

        diff = platform_total - channel_amount
        status = "matched" if diff == 0 else "mismatched"

        existing = self._session.execute(
            select(PaymentReconciliation).where(
                PaymentReconciliation.channel_id == channel_id,
                PaymentReconciliation.reconcile_date == reconcile_date,
            )
        ).scalar_one_or_none()

        if existing:
            existing.platform_amount = platform_total
            existing.channel_amount = channel_amount
            existing.difference = diff
            existing.status = status
            rec = existing
        else:
            rec = PaymentReconciliation(
                id=str(uuid4()),
                channel_id=channel_id,
                reconcile_date=reconcile_date,
                platform_amount=platform_total,
                channel_amount=channel_amount,
                difference=diff,
                status=status,
            )
            self._session.add(rec)
        self._session.flush()
        return rec

    def resolve_mismatch(self, reconciliation_id: str, resolution: str, resolved_by: str) -> PaymentReconciliation:
        rec = self._session.get(PaymentReconciliation, reconciliation_id)
        if rec is None:
            raise LookupError("Reconciliation record not found")
        rec.resolution = resolution
        rec.resolved_by = resolved_by
        rec.resolved_at = datetime.now(timezone.utc)
        rec.status = "resolved"
        self._session.flush()
        return rec

    def get_reconciliations(self, channel_id: str | None = None) -> list[dict]:
        query = select(PaymentReconciliation).order_by(PaymentReconciliation.reconcile_date.desc())
        if channel_id:
            query = query.where(PaymentReconciliation.channel_id == channel_id)
        rows = self._session.execute(query).scalars().all()
        return [
            {
                "id": r.id,
                "channel_id": r.channel_id,
                "reconcile_date": r.reconcile_date.isoformat(),
                "platform_amount": float(r.platform_amount) if r.platform_amount else 0,
                "channel_amount": float(r.channel_amount) if r.channel_amount else 0,
                "difference": float(r.difference) if r.difference else 0,
                "status": r.status,
                "resolution": r.resolution,
                "resolved_by": r.resolved_by,
                "resolved_at": r.resolved_at.isoformat() if r.resolved_at else None,
            }
            for r in rows
        ]
