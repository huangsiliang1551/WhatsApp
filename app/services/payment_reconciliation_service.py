"""Payment reconciliation service: auto-reconcile and mismatch resolution."""
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.db.models import AppUser, PaymentReconciliation, PaymentReconciliationItem, RechargeRecord
from app.services.payment_channel_service import PaymentChannelService
from app.services.recharge_repair_service import RechargeRepairService


class PaymentReconciliationService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def auto_reconcile(self, channel_id: str, reconcile_date: date) -> PaymentReconciliation:
        platform_records = self._session.scalars(
            select(RechargeRecord).where(
                RechargeRecord.channel_id == channel_id,
                func.date(RechargeRecord.created_at) == reconcile_date,
                RechargeRecord.status == "completed",
            )
        ).all()
        platform_total = sum((Decimal(item.amount or 0) for item in platform_records), Decimal("0"))
        provider = PaymentChannelService(self._session).get_provider(channel_id)
        channel_orders = provider.fetch_reconciliation_bill(channel_id=channel_id, reconcile_date=reconcile_date)
        successful_channel_orders = [
            item for item in channel_orders if str(item.get("status") or "success").lower() in {"success", "paid", "completed"}
        ]
        channel_total = sum((Decimal(str(item.get("amount") or "0")) for item in successful_channel_orders), Decimal("0"))

        existing = self._session.execute(
            select(PaymentReconciliation).where(
                PaymentReconciliation.channel_id == channel_id,
                PaymentReconciliation.reconcile_date == reconcile_date,
            )
        ).scalar_one_or_none()

        if existing:
            existing.platform_amount = platform_total
            existing.channel_amount = channel_total
            rec = existing
        else:
            rec = PaymentReconciliation(
                id=str(uuid4()),
                channel_id=channel_id,
                reconcile_date=reconcile_date,
                platform_amount=platform_total,
                channel_amount=channel_total,
            )
            self._session.add(rec)
        self._session.flush()
        self._replace_reconciliation_items(
            reconciliation_id=rec.id,
            channel_id=channel_id,
            platform_records=platform_records,
            channel_orders=successful_channel_orders,
        )
        open_items = self._session.scalar(
            select(func.count())
            .select_from(PaymentReconciliationItem)
            .where(PaymentReconciliationItem.reconciliation_id == rec.id)
        ) or 0
        diff = platform_total - channel_total
        rec.difference = diff
        rec.status = "matched" if open_items == 0 and diff == Decimal("0") else "mismatched"
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

    def get_reconciliation_items(self, reconciliation_id: str) -> list[dict]:
        rows = self._session.scalars(
            select(PaymentReconciliationItem)
            .where(PaymentReconciliationItem.reconciliation_id == reconciliation_id)
            .order_by(PaymentReconciliationItem.created_at.asc(), PaymentReconciliationItem.id.asc())
        ).all()
        return [
            {
                "id": row.id,
                "reconciliation_id": row.reconciliation_id,
                "channel_id": row.channel_id,
                "item_type": row.item_type,
                "channel_order_no": row.channel_order_no,
                "platform_order_no": row.platform_order_no,
                "user_id": row.user_id,
                "platform_amount": float(row.platform_amount) if row.platform_amount is not None else None,
                "channel_amount": float(row.channel_amount) if row.channel_amount is not None else None,
                "currency": row.currency,
                "status": row.status,
                "repair_order_id": row.repair_order_id,
                "raw_json": row.raw_json or {},
            }
            for row in rows
        ]

    def create_repair_for_item(self, *, item_id: str, operator_id: str) -> PaymentReconciliationItem:
        item = self._session.get(PaymentReconciliationItem, item_id)
        if item is None:
            raise LookupError("Reconciliation item not found")
        if item.item_type != "missing_platform":
            raise ValueError("Only missing_platform items can create repair orders.")
        if item.status == "repair_created" and item.repair_order_id:
            return item
        if not item.user_id:
            raise ValueError("Reconciliation item missing user_id.")
        user = self._session.get(AppUser, item.user_id)
        if user is None:
            raise LookupError("Reconciliation item user not found")
        amount = item.channel_amount if item.channel_amount is not None else item.platform_amount
        if amount is None:
            raise ValueError("Reconciliation item missing amount.")
        repair = RechargeRepairService(self._session).create_repair(
            account_id=user.account_id,
            user_id=user.id,
            amount=Decimal(amount),
            currency=item.currency or "USD",
            repair_type="reconciliation_missing_platform",
            reason="Payment reconciliation missing platform recharge",
            remark=None,
            channel_id=item.channel_id,
            platform_order_no=item.platform_order_no,
            channel_order_no=item.channel_order_no,
            operator_id=operator_id,
        )
        item.status = "repair_created"
        item.repair_order_id = repair.id
        self._session.add(item)
        self._session.flush()
        self._refresh_reconciliation_status(item.reconciliation_id)
        return item

    def update_item_status(
        self,
        *,
        item_id: str,
        target_status: str,
        actor_id: str,
        reason: str | None = None,
    ) -> PaymentReconciliationItem:
        if target_status not in {"ignored", "resolved"}:
            raise ValueError("Unsupported reconciliation item status.")
        item = self._session.get(PaymentReconciliationItem, item_id)
        if item is None:
            raise LookupError("Reconciliation item not found")
        if item.status == target_status:
            return item
        if item.status != "open":
            raise ValueError("Only open reconciliation items can be updated.")

        raw_json = dict(item.raw_json or {})
        raw_json["admin_action"] = {
            "target_status": target_status,
            "actor_id": actor_id,
            "reason": reason,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        item.raw_json = raw_json
        item.status = target_status
        self._session.add(item)
        self._session.flush()
        self._refresh_reconciliation_status(item.reconciliation_id)
        return item

    def _replace_reconciliation_items(
        self,
        *,
        reconciliation_id: str,
        channel_id: str,
        platform_records: list[RechargeRecord],
        channel_orders: list[dict],
    ) -> None:
        existing_rows = self._session.scalars(
            select(PaymentReconciliationItem).where(PaymentReconciliationItem.reconciliation_id == reconciliation_id)
        ).all()
        for row in existing_rows:
            self._session.delete(row)
        self._session.flush()

        platform_by_order = {
            str(item.channel_order_id): item
            for item in platform_records
            if item.channel_order_id
        }
        channel_by_order = {
            str(item.get("order_id") or item.get("channel_order_no")): item
            for item in channel_orders
            if item.get("order_id") or item.get("channel_order_no")
        }

        for order_no, provider_item in channel_by_order.items():
            platform_item = platform_by_order.get(order_no)
            provider_amount = Decimal(str(provider_item.get("amount") or "0"))
            provider_currency = str(provider_item.get("currency") or "USD")
            if platform_item is None:
                self._session.add(
                    PaymentReconciliationItem(
                        reconciliation_id=reconciliation_id,
                        channel_id=channel_id,
                        item_type="missing_platform",
                        channel_order_no=order_no,
                        user_id=str(provider_item.get("user_id")) if provider_item.get("user_id") else None,
                        channel_amount=provider_amount,
                        currency=provider_currency,
                        status="open",
                        raw_json=provider_item,
                    )
                )
                continue
            if Decimal(platform_item.amount or 0) != provider_amount:
                self._session.add(
                    PaymentReconciliationItem(
                        reconciliation_id=reconciliation_id,
                        channel_id=channel_id,
                        item_type="amount_mismatch",
                        channel_order_no=order_no,
                        user_id=platform_item.user_id,
                        platform_amount=Decimal(platform_item.amount or 0),
                        channel_amount=provider_amount,
                        currency=provider_currency,
                        status="open",
                        raw_json={"platform": platform_item.callback_data or {}, "provider": provider_item},
                    )
                )
            elif str(platform_item.currency) != provider_currency:
                self._session.add(
                    PaymentReconciliationItem(
                        reconciliation_id=reconciliation_id,
                        channel_id=channel_id,
                        item_type="currency_mismatch",
                        channel_order_no=order_no,
                        user_id=platform_item.user_id,
                        platform_amount=Decimal(platform_item.amount or 0),
                        channel_amount=provider_amount,
                        currency=provider_currency,
                        status="open",
                        raw_json={"platform": platform_item.callback_data or {}, "provider": provider_item},
                    )
                )

        for order_no, platform_item in platform_by_order.items():
            if order_no in channel_by_order:
                continue
            self._session.add(
                PaymentReconciliationItem(
                    reconciliation_id=reconciliation_id,
                    channel_id=channel_id,
                    item_type="missing_channel",
                    channel_order_no=order_no,
                    user_id=platform_item.user_id,
                    platform_amount=Decimal(platform_item.amount or 0),
                    currency=str(platform_item.currency),
                    status="open",
                    raw_json=platform_item.callback_data or {},
                )
            )

    def _refresh_reconciliation_status(self, reconciliation_id: str) -> None:
        rec = self._session.get(PaymentReconciliation, reconciliation_id)
        if rec is None:
            return
        open_items = self._session.scalar(
            select(func.count())
            .select_from(PaymentReconciliationItem)
            .where(
                PaymentReconciliationItem.reconciliation_id == reconciliation_id,
                PaymentReconciliationItem.status == "open",
            )
        ) or 0
        if open_items == 0:
            rec.status = "matched" if Decimal(rec.difference or 0) == Decimal("0") else "resolved"
        else:
            rec.status = "mismatched"
        self._session.add(rec)
        self._session.flush()
