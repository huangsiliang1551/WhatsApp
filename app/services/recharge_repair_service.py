from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    AppUser,
    RechargeRecord,
    RechargeRepairOrder,
    WalletAccount,
    WalletRechargeOrder,
    utc_now,
)
from app.services.wallet_ledger_service import WalletLedgerService


class RechargeRepairService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._wallet_ledger_service = WalletLedgerService(session=session)

    def create_repair(
        self,
        *,
        account_id: str,
        user_id: str,
        amount: Decimal,
        currency: str,
        repair_type: str,
        reason: str,
        remark: str | None,
        channel_id: str | None,
        platform_order_no: str | None,
        channel_order_no: str | None,
        operator_id: str,
    ) -> RechargeRepairOrder:
        user = self._require_user(user_id=user_id, account_id=account_id)
        repair = RechargeRepairOrder(
            account_id=account_id,
            repair_no=f"RPR-{utc_now().strftime('%Y%m%d%H%M%S%f')}",
            user_id=user.id,
            channel_id=channel_id,
            platform_order_no=platform_order_no,
            channel_order_no=channel_order_no,
            amount=amount,
            currency=currency,
            repair_type=repair_type,
            status="pending",
            reason=reason,
            remark=remark,
            operator_id=operator_id,
        )
        self._session.add(repair)
        self._session.commit()
        return repair

    def approve_repair(self, *, repair_id: str, actor_id: str) -> RechargeRepairOrder:
        repair = self._require_repair_for_update(repair_id=repair_id)
        if repair.status == "credited":
            return repair
        if repair.status != "pending":
            raise ValueError(f"Recharge repair '{repair.id}' cannot be approved from '{repair.status}'.")

        if repair.channel_order_no:
            existing = self._session.scalars(
                select(RechargeRepairOrder).where(
                    RechargeRepairOrder.account_id == repair.account_id,
                    RechargeRepairOrder.channel_order_no == repair.channel_order_no,
                    RechargeRepairOrder.status == "credited",
                    RechargeRepairOrder.id != repair.id,
                )
            ).first()
            if existing is not None:
                raise ValueError("A credited repair already exists for this channel order.")

        wallet = self._require_wallet(account_id=repair.account_id, user_id=repair.user_id)
        now = utc_now()
        recharge_record = RechargeRecord(
            user_id=repair.user_id,
            agency_id=repair.account_id,
            amount=repair.amount,
            currency=repair.currency,
            status="completed",
            channel_id=repair.channel_id,
            channel_order_id=repair.channel_order_no,
            callback_verified=True,
            callback_data={
                "repair_id": repair.id,
                "repair_no": repair.repair_no,
                "platform_order_no": repair.platform_order_no,
                "channel_order_no": repair.channel_order_no,
            },
        )
        self._session.add(recharge_record)
        self._session.flush()
        recharge_order = WalletRechargeOrder(
            account_id=repair.account_id,
            wallet_account_id=wallet.id,
            user_id=repair.user_id,
            amount=repair.amount,
            currency=repair.currency,
            status="paid",
            credited_at=now,
        )
        self._session.add(recharge_order)
        self._session.flush()
        ledger = self._wallet_ledger_service.credit_system_balance(
            wallet=wallet,
            account_id=repair.account_id,
            user_id=repair.user_id,
            amount=Decimal(repair.amount),
            currency=repair.currency,
            transaction_type="recharge_repair",
            source_type="callback_repair",
            note="Recharge repair credited",
            reference_type="recharge_repair_order",
            reference_id=repair.id,
            fund_type="cash",
            is_real_recharge=True,
        )
        self._session.flush()
        repair.status = "credited"
        repair.approved_by = actor_id
        repair.approved_at = now
        repair.credited_at = now
        repair.recharge_record_id = recharge_record.id
        repair.ledger_id = ledger.id
        self._session.add(repair)
        self._session.commit()
        return repair

    def reject_repair(self, *, repair_id: str, actor_id: str, reason: str | None = None) -> RechargeRepairOrder:
        repair = self._require_repair_for_update(repair_id=repair_id)
        if repair.status == "rejected":
            return repair
        if repair.status != "pending":
            raise ValueError(f"Recharge repair '{repair.id}' cannot be rejected from '{repair.status}'.")
        repair.status = "rejected"
        repair.approved_by = actor_id
        repair.rejected_at = utc_now()
        if reason:
            repair.remark = reason
        self._session.add(repair)
        self._session.commit()
        return repair

    def list_repairs(self, *, account_id: str | None = None) -> list[RechargeRepairOrder]:
        query = select(RechargeRepairOrder).order_by(
            RechargeRepairOrder.created_at.desc(),
            RechargeRepairOrder.id.desc(),
        )
        if account_id is not None:
            query = query.where(RechargeRepairOrder.account_id == account_id)
        return self._session.scalars(query).all()

    def _require_user(self, *, user_id: str, account_id: str) -> AppUser:
        user = self._session.get(AppUser, user_id)
        if user is None:
            user = self._session.scalars(
                select(AppUser).where(
                    AppUser.account_id == account_id,
                    AppUser.public_user_id == user_id,
                )
            ).first()
        if user is None or user.account_id != account_id:
            raise LookupError(f"User '{user_id}' not found for account '{account_id}'.")
        return user

    def _require_wallet(self, *, account_id: str, user_id: str) -> WalletAccount:
        wallet = self._session.scalars(
            select(WalletAccount).where(
                WalletAccount.account_id == account_id,
                WalletAccount.user_id == user_id,
            )
        ).first()
        if wallet is None:
            wallet = WalletAccount(account_id=account_id, user_id=user_id)
            self._session.add(wallet)
            self._session.flush()
        return wallet

    def _require_repair_for_update(self, *, repair_id: str) -> RechargeRepairOrder:
        repair = self._session.scalars(
            select(RechargeRepairOrder)
            .where(RechargeRepairOrder.id == repair_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        ).first()
        if repair is None:
            raise LookupError(f"Recharge repair '{repair_id}' not found.")
        return repair
