"""Finance reports: recharge, withdrawal, summary and anomaly alerts."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.auth import RequestActor
from app.db.models import (
    AppUser,
    PaymentCallback,
    RechargeRecord,
    WalletAccount,
    WalletLedgerEntry,
    WalletRechargeOrder,
    WithdrawalRecord,
    WithdrawalRequest,
    utc_now,
)
from app.services.data_scope_filter_service import DataScopeFilterService
from app.services.wallet_ledger_service import WalletLedgerService


class FinanceReportService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._wallet_ledger_service = WalletLedgerService(session=session)

    def get_recharge_report(
        self,
        filters: dict | None = None,
        sort_field: str | None = None,
        sort_order: str | None = None,
        scope_actor: RequestActor | None = None,
    ) -> list[dict]:
        query = select(WalletLedgerEntry).where(
            WalletLedgerEntry.ledger_type == "system",
            WalletLedgerEntry.direction == "credit",
            WalletLedgerEntry.status == "paid",
        )
        if filters:
            if filters.get("agency_id"):
                query = query.where(WalletLedgerEntry.account_id == filters["agency_id"])
            if filters.get("site_id"):
                query = query.join(AppUser, AppUser.id == WalletLedgerEntry.user_id).where(
                    AppUser.registration_site_id == filters["site_id"]
                )
            if filters.get("status"):
                query = query.where(WalletLedgerEntry.status == filters["status"])
            if filters.get("date_from"):
                query = query.where(WalletLedgerEntry.created_at >= filters["date_from"])
            if filters.get("date_to"):
                query = query.where(WalletLedgerEntry.created_at <= filters["date_to"])
            if filters.get("source_type"):
                query = query.where(WalletLedgerEntry.source_type == filters["source_type"])
            include_bonus = filters.get("include_bonus")
            if include_bonus is False:
                query = query.where(WalletLedgerEntry.is_bonus.is_(False))
            fund_scope = filters.get("fund_scope")
            if fund_scope == "cash":
                query = query.where(WalletLedgerEntry.cash_amount > 0)
            elif fund_scope == "bonus":
                query = query.where(WalletLedgerEntry.bonus_amount > 0)
        if scope_actor is not None:
            query = DataScopeFilterService(self._session).filter_wallet_ledger_entries(query, scope_actor, mode="current")

        allowed_sort_fields = {
            "amount": WalletLedgerEntry.amount,
            "cash_amount": WalletLedgerEntry.cash_amount,
            "bonus_amount": WalletLedgerEntry.bonus_amount,
            "status": WalletLedgerEntry.status,
            "source_type": WalletLedgerEntry.source_type,
            "created_at": WalletLedgerEntry.created_at,
            "user_id": WalletLedgerEntry.user_id,
        }
        if sort_field in allowed_sort_fields:
            column = allowed_sort_fields[sort_field]
            query = query.order_by(column.asc() if sort_order == "asc" else column.desc())
        else:
            query = query.order_by(WalletLedgerEntry.created_at.desc(), WalletLedgerEntry.id.desc())
        rows = self._session.execute(query).scalars().all()
        return [self._wallet_credit_to_dict(r) for r in rows]

    def get_withdrawal_report(
        self,
        filters: dict | None = None,
        sort_field: str | None = None,
        sort_order: str | None = None,
        scope_actor: RequestActor | None = None,
    ) -> list[dict]:
        query = select(WithdrawalRequest)
        if filters:
            if filters.get("agency_id"):
                query = query.where(WithdrawalRequest.account_id == filters["agency_id"])
            if filters.get("site_id"):
                query = query.join(AppUser, AppUser.id == WithdrawalRequest.user_id).where(
                    AppUser.registration_site_id == filters["site_id"]
                )
            if filters.get("status"):
                query = query.where(WithdrawalRequest.status == filters["status"])
            if filters.get("date_from"):
                query = query.where(WithdrawalRequest.created_at >= filters["date_from"])
            if filters.get("date_to"):
                query = query.where(WithdrawalRequest.created_at <= filters["date_to"])
            fund_scope = filters.get("fund_scope")
            if fund_scope == "cash":
                query = query.where(WithdrawalRequest.cash_amount > 0)
            elif fund_scope == "bonus":
                query = query.where(WithdrawalRequest.bonus_amount > 0)
        if scope_actor is not None:
            query = DataScopeFilterService(self._session).filter_withdrawals(query, scope_actor, mode="current")

        allowed_sort_fields = {
            "amount": WithdrawalRequest.amount,
            "cash_amount": WithdrawalRequest.cash_amount,
            "bonus_amount": WithdrawalRequest.bonus_amount,
            "status": WithdrawalRequest.status,
            "created_at": WithdrawalRequest.created_at,
            "reviewed_at": WithdrawalRequest.reviewed_at,
            "paid_at": WithdrawalRequest.paid_at,
            "user_id": WithdrawalRequest.user_id,
        }
        if sort_field in allowed_sort_fields:
            column = allowed_sort_fields[sort_field]
            query = query.order_by(column.asc() if sort_order == "asc" else column.desc())
        else:
            query = query.order_by(WithdrawalRequest.created_at.desc(), WithdrawalRequest.id.desc())
        rows = self._session.execute(query).scalars().all()
        items = [self._withdrawal_request_to_dict(r) for r in rows]
        if filters and filters.get("include_bonus") is False:
            for item in items:
                item["amount"] = item["cash_amount"]
                item["bonus_amount"] = 0.0
        return items

    def get_wallet_ledger_report(
        self,
        filters: dict | None = None,
        sort_field: str | None = None,
        sort_order: str | None = None,
        scope_actor: RequestActor | None = None,
    ) -> list[dict]:
        query = select(WalletLedgerEntry).where(WalletLedgerEntry.ledger_type == "system")
        if filters:
            if filters.get("agency_id"):
                query = query.where(WalletLedgerEntry.account_id == filters["agency_id"])
            if filters.get("user_id"):
                query = query.where(WalletLedgerEntry.user_id == filters["user_id"])
            if filters.get("status"):
                query = query.where(WalletLedgerEntry.status == filters["status"])
            if filters.get("date_from"):
                query = query.where(WalletLedgerEntry.created_at >= filters["date_from"])
            if filters.get("date_to"):
                query = query.where(WalletLedgerEntry.created_at <= filters["date_to"])
            if filters.get("source_type"):
                query = query.where(WalletLedgerEntry.source_type == filters["source_type"])
            if filters.get("transaction_type"):
                query = query.where(WalletLedgerEntry.transaction_type == filters["transaction_type"])
            fund_scope = filters.get("fund_scope")
            if fund_scope == "cash":
                query = query.where(WalletLedgerEntry.cash_amount > 0)
            elif fund_scope == "bonus":
                query = query.where(WalletLedgerEntry.bonus_amount > 0)
        if scope_actor is not None:
            query = DataScopeFilterService(self._session).filter_wallet_ledger_entries(query, scope_actor, mode="current")

        allowed_sort_fields = {
            "amount": WalletLedgerEntry.amount,
            "cash_amount": WalletLedgerEntry.cash_amount,
            "bonus_amount": WalletLedgerEntry.bonus_amount,
            "status": WalletLedgerEntry.status,
            "source_type": WalletLedgerEntry.source_type,
            "transaction_type": WalletLedgerEntry.transaction_type,
            "direction": WalletLedgerEntry.direction,
            "created_at": WalletLedgerEntry.created_at,
            "user_id": WalletLedgerEntry.user_id,
            "balance_after": WalletLedgerEntry.balance_after,
        }
        if sort_field in allowed_sort_fields:
            column = allowed_sort_fields[sort_field]
            query = query.order_by(column.asc() if sort_order == "asc" else column.desc())
        else:
            query = query.order_by(WalletLedgerEntry.created_at.desc(), WalletLedgerEntry.id.desc())
        rows = self._session.execute(query).scalars().all()
        return [self._wallet_ledger_to_dict(r) for r in rows]

    def get_finance_summary(
        self,
        filters: dict | None = None,
        scope_actor: RequestActor | None = None,
    ) -> dict:
        recharge_filters = [
            WalletLedgerEntry.ledger_type == "system",
            WalletLedgerEntry.direction == "credit",
            WalletLedgerEntry.status == "paid",
            WalletLedgerEntry.is_real_recharge.is_(True),
        ]
        bonus_filters = [
            WalletLedgerEntry.ledger_type == "system",
            WalletLedgerEntry.direction == "credit",
            WalletLedgerEntry.status == "paid",
            WalletLedgerEntry.is_bonus.is_(True),
        ]
        withdrawal_filters = [WithdrawalRequest.status.in_(["approved", "paid"])]

        if filters:
            if filters.get("agency_id"):
                recharge_filters.append(WalletLedgerEntry.account_id == filters["agency_id"])
                bonus_filters.append(WalletLedgerEntry.account_id == filters["agency_id"])
                withdrawal_filters.append(WithdrawalRequest.account_id == filters["agency_id"])
            if filters.get("date_from"):
                recharge_filters.append(WalletLedgerEntry.created_at >= filters["date_from"])
                bonus_filters.append(WalletLedgerEntry.created_at >= filters["date_from"])
                withdrawal_filters.append(WithdrawalRequest.created_at >= filters["date_from"])
            if filters.get("date_to"):
                recharge_filters.append(WalletLedgerEntry.created_at <= filters["date_to"])
                bonus_filters.append(WalletLedgerEntry.created_at <= filters["date_to"])
                withdrawal_filters.append(WithdrawalRequest.created_at <= filters["date_to"])
        include_bonus = not (filters and filters.get("include_bonus") is False)

        recharge_query = select(
            func.sum(WalletLedgerEntry.cash_amount),
            func.count(WalletLedgerEntry.id),
        ).select_from(WalletLedgerEntry).where(*recharge_filters)
        if scope_actor is not None:
            recharge_query = DataScopeFilterService(self._session).filter_wallet_ledger_entries(
                recharge_query,
                scope_actor,
                mode="current",
            )
        recharge_row = self._session.execute(recharge_query).one()
        recharge_total = recharge_row[0] or Decimal("0")
        recharge_count = recharge_row[1] or 0

        bonus_query = select(
            func.sum(WalletLedgerEntry.bonus_amount),
            func.count(WalletLedgerEntry.id),
        ).select_from(WalletLedgerEntry).where(*bonus_filters)
        if scope_actor is not None:
            bonus_query = DataScopeFilterService(self._session).filter_wallet_ledger_entries(
                bonus_query,
                scope_actor,
                mode="current",
            )
        bonus_row = self._session.execute(bonus_query).one()
        bonus_total = bonus_row[0] or Decimal("0")

        withdrawal_query = select(
                func.sum(WithdrawalRequest.amount),
                func.sum(WithdrawalRequest.cash_amount),
                func.sum(WithdrawalRequest.bonus_amount),
                func.count(WithdrawalRequest.id),
            ).select_from(WithdrawalRequest).where(*withdrawal_filters)
        if scope_actor is not None:
            withdrawal_query = DataScopeFilterService(self._session).filter_withdrawals(
                withdrawal_query,
                scope_actor,
                mode="current",
            )
        withdrawal_row = self._session.execute(withdrawal_query).one()
        withdrawal_total = withdrawal_row[0] or Decimal("0")
        withdrawal_cash_total = withdrawal_row[1] or Decimal("0")
        withdrawal_bonus_total = withdrawal_row[2] or Decimal("0")
        withdrawal_count = withdrawal_row[3] or 0

        if not include_bonus:
            bonus_total = Decimal("0")
            withdrawal_total = withdrawal_cash_total
            withdrawal_bonus_total = Decimal("0")

        return {
            "recharge_amount": float(recharge_total),
            "recharge_count": recharge_count,
            "bonus_amount": float(bonus_total),
            "withdrawal_amount": float(withdrawal_total),
            "withdrawal_cash_amount": float(withdrawal_cash_total),
            "withdrawal_bonus_amount": float(withdrawal_bonus_total),
            "withdrawal_fee": 0.0,
            "withdrawal_count": withdrawal_count,
            "net_recharge": float(recharge_total - withdrawal_cash_total),
        }

    def get_anomaly_alerts(
        self,
        agency_id: str | None = None,
        scope_actor: RequestActor | None = None,
    ) -> list[dict]:
        alerts = []
        now = datetime.now(timezone.utc)
        since = now - timedelta(hours=24)

        recharge_query = select(WalletLedgerEntry).where(
            WalletLedgerEntry.created_at >= since,
            WalletLedgerEntry.ledger_type == "system",
            WalletLedgerEntry.direction == "credit",
            WalletLedgerEntry.amount >= Decimal("10000"),
        )
        if agency_id:
            recharge_query = recharge_query.where(WalletLedgerEntry.account_id == agency_id)
        if scope_actor is not None:
            recharge_query = DataScopeFilterService(self._session).filter_wallet_ledger_entries(
                recharge_query,
                scope_actor,
                mode="current",
            )
        large = self._session.execute(recharge_query).scalars().all()
        for r in large:
            alerts.append(
                {
                    "type": "large_recharge",
                    "record_id": r.id,
                    "account_id": r.account_id,
                    "user_id": r.user_id,
                    "public_user_id": self._resolve_public_user_id(r.user_id),
                    "amount": float(r.amount),
                    "time": r.created_at.isoformat(),
                    "message": f"Large recharge detected: {float(r.amount)}.",
                }
            )

        withdrawal_query = select(WithdrawalRequest.user_id, func.count().label("cnt")).where(
            WithdrawalRequest.created_at >= since
        )
        if agency_id:
            withdrawal_query = withdrawal_query.where(WithdrawalRequest.account_id == agency_id)
        if scope_actor is not None:
            withdrawal_query = DataScopeFilterService(self._session).filter_withdrawals(
                withdrawal_query,
                scope_actor,
                mode="current",
            )
        freq = self._session.execute(
            withdrawal_query.group_by(WithdrawalRequest.user_id).having(func.count() > 3)
        ).all()
        for row in freq:
            alerts.append(
                {
                    "type": "frequent_withdrawal",
                    "account_id": agency_id,
                    "user_id": row[0],
                    "public_user_id": self._resolve_public_user_id(row[0]),
                    "count": row[1],
                    "message": f"Frequent withdrawal detected for user {row[0]}.",
                }
            )

        if agency_id is None:
            failed_callbacks = self._session.execute(
                select(PaymentCallback).where(
                    PaymentCallback.created_at >= since,
                    PaymentCallback.signature_valid.is_(False),
                )
            ).scalars().all()
            for cb in failed_callbacks:
                alerts.append(
                    {
                        "type": "callback_failure",
                        "record_id": cb.id,
                        "message": f"Callback signature verification failed: {cb.id[:12]}...",
                    }
                )

        return alerts

    def _resolve_public_user_id(self, user_id: str | None) -> str | None:
        if not user_id:
            return None
        return self._resolve_user_identity(user_id)[1]

    def _resolve_user_identity(self, user_id: str | None) -> tuple[str | None, str | None]:
        if not user_id:
            return None, None
        row = self._session.execute(
            select(AppUser.id, AppUser.public_user_id).where(AppUser.id == user_id)
        ).one_or_none()
        if row is None:
            return user_id, None
        return row[0], row[1]

    def manual_recharge(
        self,
        user_id: str,
        amount: Decimal,
        agency_id: str | None = None,
        site_id: str | None = None,
    ) -> dict:
        user = self._session.get(AppUser, user_id)
        if user is None:
            raise LookupError(f"User '{user_id}' not found.")
        wallet = self._session.scalars(
            select(WalletAccount).where(
                WalletAccount.account_id == user.account_id,
                WalletAccount.user_id == user.id,
            )
        ).first()
        if wallet is None:
            wallet = WalletAccount(
                account_id=user.account_id,
                user_id=user.id,
                currency="CNY",
            )
            self._session.add(wallet)
            self._session.flush()

        sanitized_amount = amount.quantize(Decimal("0.01"))
        record = RechargeRecord(
            id=uuid4().hex[:36],
            user_id=user_id,
            agency_id=agency_id,
            site_id=site_id,
            amount=sanitized_amount,
            currency="CNY",
            status="completed",
        )
        self._session.add(record)
        self._session.flush()
        recharge_order = WalletRechargeOrder(
            account_id=user.account_id,
            wallet_account_id=wallet.id,
            user_id=user.id,
            amount=sanitized_amount,
            currency=wallet.currency,
            status="paid",
            credited_at=utc_now(),
        )
        self._session.add(recharge_order)
        self._session.flush()
        self._wallet_ledger_service.credit_system_balance(
            wallet=wallet,
            account_id=user.account_id,
            user_id=user.id,
            amount=sanitized_amount,
            currency=wallet.currency,
            transaction_type="manual_recharge",
            source_type="manual_real_recharge",
            note="Manual recharge credited",
            reference_type="wallet_recharge_order",
            reference_id=recharge_order.id,
            fund_type="cash",
            is_real_recharge=True,
        )
        self._session.commit()
        return self._recharge_to_dict(record)

    def _recharge_to_dict(self, r: RechargeRecord) -> dict:
        _, public_user_id = self._resolve_user_identity(r.user_id)
        return {
            "id": r.id,
            "user_id": r.user_id,
            "public_user_id": public_user_id,
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

    def _wallet_credit_to_dict(self, entry: WalletLedgerEntry) -> dict:
        _, public_user_id = self._resolve_user_identity(entry.user_id)
        return {
            "id": entry.id,
            "account_id": entry.account_id,
            "user_id": entry.user_id,
            "public_user_id": public_user_id,
            "amount": float(entry.amount),
            "cash_amount": float(entry.cash_amount),
            "bonus_amount": float(entry.bonus_amount),
            "currency": entry.currency,
            "status": entry.status,
            "source_type": entry.source_type,
            "transaction_type": entry.transaction_type,
            "fund_type": entry.fund_type,
            "is_bonus": entry.is_bonus,
            "is_real_recharge": entry.is_real_recharge,
            "reference_type": entry.reference_type,
            "reference_id": entry.reference_id,
            "created_at": entry.created_at.isoformat() if entry.created_at else None,
        }

    def _wallet_ledger_to_dict(self, entry: WalletLedgerEntry) -> dict:
        _, public_user_id = self._resolve_user_identity(entry.user_id)
        return {
            "id": entry.id,
            "account_id": entry.account_id,
            "user_id": entry.user_id,
            "public_user_id": public_user_id,
            "ledger_type": entry.ledger_type,
            "transaction_type": entry.transaction_type,
            "direction": entry.direction,
            "amount": float(entry.amount),
            "currency": entry.currency,
            "status": entry.status,
            "source_type": entry.source_type,
            "fund_type": entry.fund_type,
            "cash_amount": float(entry.cash_amount),
            "bonus_amount": float(entry.bonus_amount),
            "task_amount": float(entry.task_amount),
            "balance_after": float(entry.balance_after) if entry.balance_after is not None else None,
            "cash_balance_after": float(entry.cash_balance_after) if entry.cash_balance_after is not None else None,
            "bonus_balance_after": float(entry.bonus_balance_after) if entry.bonus_balance_after is not None else None,
            "task_balance_after": float(entry.task_balance_after) if entry.task_balance_after is not None else None,
            "display_category": entry.display_category,
            "display_title": entry.display_title,
            "note": entry.note,
            "reference_type": entry.reference_type,
            "reference_id": entry.reference_id,
            "created_at": entry.created_at.isoformat() if entry.created_at else None,
        }

    def _withdrawal_to_dict(self, w: WithdrawalRecord) -> dict:
        _, public_user_id = self._resolve_user_identity(w.user_id)
        return {
            "id": w.id,
            "user_id": w.user_id,
            "public_user_id": public_user_id,
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

    def _withdrawal_request_to_dict(self, w: WithdrawalRequest) -> dict:
        actual_payout = w.actual_payout_amount if w.actual_payout_amount is not None else w.amount
        _, public_user_id = self._resolve_user_identity(w.user_id)
        return {
            "id": w.id,
            "account_id": w.account_id,
            "user_id": w.user_id,
            "public_user_id": public_user_id,
            "member_profile_id": w.member_profile_id,
            "request_no": w.request_no,
            "amount": float(w.amount),
            "cash_amount": float(w.cash_amount),
            "bonus_amount": float(w.bonus_amount),
            "fee": 0.0,
            "net_amount": float(actual_payout),
            "actual_payout_amount": float(actual_payout),
            "withdraw_account_type": w.withdraw_account_type,
            "account_no_masked": w.account_no_masked,
            "account_fingerprint": w.account_fingerprint,
            "duplicate_account_count": w.duplicate_account_count or 0,
            "duplicate_member_ids": self._resolve_duplicate_public_user_ids(w),
            "risk_level": w.risk_level,
            "risk_flags": list(w.risk_flags or []),
            "currency": w.currency,
            "status": w.status,
            "approved_by": None,
            "approved_at": w.reviewed_at.isoformat() if w.reviewed_at else None,
            "reject_reason": w.rejection_reason,
            "frozen_reason": None,
            "created_at": w.created_at.isoformat() if w.created_at else None,
            "reviewed_at": w.reviewed_at.isoformat() if w.reviewed_at else None,
            "paid_at": w.paid_at.isoformat() if w.paid_at else None,
        }

    def _resolve_duplicate_public_user_ids(self, withdrawal: WithdrawalRequest) -> list[str]:
        if not withdrawal.account_fingerprint:
            return []
        rows = self._session.execute(
            select(AppUser.public_user_id)
            .select_from(WithdrawalRequest)
            .join(AppUser, AppUser.id == WithdrawalRequest.user_id)
            .where(
                WithdrawalRequest.account_id == withdrawal.account_id,
                WithdrawalRequest.account_fingerprint == withdrawal.account_fingerprint,
                WithdrawalRequest.user_id != withdrawal.user_id,
            )
            .distinct()
            .order_by(AppUser.public_user_id.asc())
        ).all()
        return [row[0] for row in rows if row[0]]
