from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from hashlib import sha256

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import WalletAccount, WalletLedgerEntry, WithdrawalRequest
from app.services.wallet_invariant_guard import WalletInvariantError, WalletInvariantGuard
from app.services.wallet_ledger_guard import WalletLedgerGuard


TWOPLACES = Decimal("0.01")


@dataclass(slots=True)
class WalletSplit:
    cash_amount: Decimal
    bonus_amount: Decimal

    @property
    def total(self) -> Decimal:
        return self.cash_amount + self.bonus_amount

    @property
    def fund_type(self) -> str:
        if self.cash_amount > Decimal("0") and self.bonus_amount > Decimal("0"):
            return "mixed"
        if self.bonus_amount > Decimal("0"):
            return "bonus"
        return "cash"


class WalletLedgerService:
    def __init__(self, *, session: Session) -> None:
        self._session = session

    def ensure_split_balance(self, *, wallet: WalletAccount) -> None:
        cash_balance = self._value(wallet.system_cash_balance)
        bonus_balance = self._value(wallet.system_bonus_balance)
        cash_frozen = self._value(wallet.system_cash_frozen)
        bonus_frozen = self._value(wallet.system_bonus_frozen)
        system_balance = self._quantize(self._value(wallet.system_balance))
        frozen_balance = self._quantize(self._value(wallet.frozen_balance))

        if cash_balance == Decimal("0") and bonus_balance == Decimal("0") and system_balance > Decimal("0"):
            cash_balance = system_balance
        if cash_frozen == Decimal("0") and bonus_frozen == Decimal("0") and frozen_balance > Decimal("0"):
            cash_frozen = frozen_balance

        wallet.system_cash_balance = self._quantize(cash_balance)
        wallet.system_bonus_balance = self._quantize(bonus_balance)
        wallet.system_cash_frozen = self._quantize(cash_frozen)
        wallet.system_bonus_frozen = self._quantize(bonus_frozen)
        self._sync_totals(wallet=wallet)

    def credit_system_balance(
        self,
        *,
        wallet: WalletAccount,
        account_id: str,
        user_id: str,
        amount: Decimal,
        currency: str,
        transaction_type: str,
        source_type: str,
        note: str | None,
        reference_type: str | None,
        reference_id: str | None,
        fund_type: str,
        status: str = "paid",
        ledger_type: str = "system",
        is_bonus: bool = False,
        is_real_recharge: bool = False,
        idempotency_key: str | None = None,
    ) -> WalletLedgerEntry:
        self.ensure_split_balance(wallet=wallet)
        resolved_idempotency_key = idempotency_key or self._build_idempotency_key(
            account_id=account_id,
            wallet_account_id=wallet.id,
            user_id=user_id,
            ledger_type=ledger_type,
            transaction_type=transaction_type,
            direction="credit",
            source_type=source_type,
            reference_type=reference_type,
            reference_id=reference_id,
        )
        existing = self._find_existing_ledger(account_id=account_id, idempotency_key=resolved_idempotency_key)
        if existing is not None:
            return existing
        sanitized_amount = self._quantize(amount)
        cash_amount = sanitized_amount if fund_type == "cash" else Decimal("0")
        bonus_amount = sanitized_amount if fund_type == "bonus" else Decimal("0")
        balance_before = self._quantize(self._value(wallet.system_balance))
        cash_before = self._quantize(self._value(wallet.system_cash_balance))
        bonus_before = self._quantize(self._value(wallet.system_bonus_balance))

        wallet.system_cash_balance = self._quantize(cash_before + cash_amount)
        wallet.system_bonus_balance = self._quantize(bonus_before + bonus_amount)
        self._sync_totals(wallet=wallet)
        self._session.add(wallet)

        ledger_entry = WalletLedgerEntry(
            account_id=account_id,
            wallet_account_id=wallet.id,
            user_id=user_id,
            ledger_type=ledger_type,
            transaction_type=transaction_type,
            direction="credit",
            amount=sanitized_amount,
            currency=currency,
            status=status,
            note=note,
            reference_type=reference_type,
            reference_id=reference_id,
            source_type=source_type,
            fund_type=fund_type,
            cash_amount=cash_amount,
            bonus_amount=bonus_amount,
            balance_before=balance_before,
            balance_after=self._quantize(self._value(wallet.system_balance)),
            cash_balance_before=cash_before,
            cash_balance_after=self._quantize(self._value(wallet.system_cash_balance)),
            bonus_balance_before=bonus_before,
            bonus_balance_after=self._quantize(self._value(wallet.system_bonus_balance)),
            display_category="wallet_credit",
            display_title=note,
            is_bonus=is_bonus,
            is_real_recharge=is_real_recharge,
            idempotency_key=resolved_idempotency_key,
        )
        WalletLedgerGuard.enforce_credit(ledger_entry)
        WalletInvariantGuard.validate_ledger_entry(ledger_entry)
        WalletInvariantGuard.validate_wallet(wallet)
        self._session.add(ledger_entry)
        return ledger_entry

    def credit_task_balance(
        self,
        *,
        wallet: WalletAccount,
        account_id: str,
        user_id: str,
        amount: Decimal,
        currency: str,
        transaction_type: str,
        source_type: str,
        note: str | None,
        reference_type: str | None,
        reference_id: str | None,
        status: str = "paid",
    ) -> WalletLedgerEntry:
        self.ensure_split_balance(wallet=wallet)
        sanitized_amount = self._quantize(amount)
        task_before = self._quantize(self._value(wallet.task_balance))

        wallet.task_balance = self._quantize(task_before + sanitized_amount)
        self._session.add(wallet)

        ledger_entry = WalletLedgerEntry(
            account_id=account_id,
            wallet_account_id=wallet.id,
            user_id=user_id,
            ledger_type="task",
            transaction_type=transaction_type,
            direction="credit",
            amount=sanitized_amount,
            currency=currency,
            status=status,
            note=note,
            reference_type=reference_type,
            reference_id=reference_id,
            source_type=source_type,
            fund_type="task",
            cash_amount=Decimal("0.00"),
            bonus_amount=Decimal("0.00"),
            task_amount=sanitized_amount,
            task_balance_before=task_before,
            task_balance_after=self._quantize(self._value(wallet.task_balance)),
            display_category="task_reward",
            display_title=note,
            idempotency_key=self._build_idempotency_key(
                account_id=account_id,
                wallet_account_id=wallet.id,
                user_id=user_id,
                ledger_type="task",
                transaction_type=transaction_type,
                direction="credit",
                source_type=source_type,
                reference_type=reference_type,
                reference_id=reference_id,
            ),
        )
        WalletLedgerGuard.enforce_credit(ledger_entry)
        WalletInvariantGuard.validate(wallet)
        self._session.add(ledger_entry)
        return ledger_entry

    def transfer_task_to_system_bonus(
        self,
        *,
        wallet: WalletAccount,
        account_id: str,
        user_id: str,
        amount: Decimal,
        currency: str,
        note_out: str,
        note_in: str,
        reference_type: str,
        reference_id: str,
        idempotency_key: str | None = None,
    ) -> tuple[WalletLedgerEntry, WalletLedgerEntry]:
        self.ensure_split_balance(wallet=wallet)
        base_idempotency_key = idempotency_key or self._build_idempotency_key(
            account_id=account_id,
            wallet_account_id=wallet.id,
            user_id=user_id,
            ledger_type="transfer",
            transaction_type="task_to_system_transfer",
            direction="mixed",
            source_type="task_transfer_bonus",
            reference_type=reference_type,
            reference_id=reference_id,
        )
        task_idempotency_key = f"{base_idempotency_key}:task_debit"
        system_idempotency_key = f"{base_idempotency_key}:system_credit"
        existing_task = self._find_existing_ledger(account_id=account_id, idempotency_key=task_idempotency_key)
        existing_system = self._find_existing_ledger(account_id=account_id, idempotency_key=system_idempotency_key)
        if existing_task is not None and existing_system is not None:
            return existing_task, existing_system
        if existing_task is not None or existing_system is not None:
            raise WalletInvariantError("PARTIAL_TASK_TRANSFER_LEDGER_FOUND")
        sanitized_amount = self._quantize(amount)
        task_before = self._quantize(self._value(wallet.task_balance))
        system_before = self._quantize(self._value(wallet.system_balance))
        bonus_before = self._quantize(self._value(wallet.system_bonus_balance))

        wallet.task_balance = self._quantize(task_before - sanitized_amount)
        wallet.system_bonus_balance = self._quantize(bonus_before + sanitized_amount)
        self._sync_totals(wallet=wallet)
        self._session.add(wallet)

        task_ledger = WalletLedgerEntry(
            account_id=account_id,
            wallet_account_id=wallet.id,
            user_id=user_id,
            ledger_type="task",
            transaction_type="task_to_system_transfer",
            direction="debit",
            amount=sanitized_amount,
            currency=currency,
            status="paid",
            note=note_out,
            reference_type=reference_type,
            reference_id=reference_id,
            source_type="task_transfer_bonus",
            fund_type="task",
            task_amount=sanitized_amount,
            task_balance_before=task_before,
            task_balance_after=self._quantize(self._value(wallet.task_balance)),
            display_category="task_transfer",
            display_title=note_out,
            idempotency_key=task_idempotency_key,
        )
        system_ledger = WalletLedgerEntry(
            account_id=account_id,
            wallet_account_id=wallet.id,
            user_id=user_id,
            ledger_type="system",
            transaction_type="task_to_system_transfer",
            direction="credit",
            amount=sanitized_amount,
            currency=currency,
            status="paid",
            note=note_in,
            reference_type=reference_type,
            reference_id=reference_id,
            source_type="task_transfer_bonus",
            fund_type="bonus",
            cash_amount=Decimal("0"),
            bonus_amount=sanitized_amount,
            balance_before=system_before,
            balance_after=self._quantize(self._value(wallet.system_balance)),
            cash_balance_before=self._quantize(self._value(wallet.system_cash_balance)),
            cash_balance_after=self._quantize(self._value(wallet.system_cash_balance)),
            bonus_balance_before=bonus_before,
            bonus_balance_after=self._quantize(self._value(wallet.system_bonus_balance)),
            display_category="wallet_credit",
            display_title=note_in,
            is_bonus=True,
            idempotency_key=system_idempotency_key,
        )
        WalletLedgerGuard.enforce_debit(task_ledger)
        WalletLedgerGuard.enforce_credit(system_ledger)
        WalletInvariantGuard.validate_ledger_entry(task_ledger)
        WalletInvariantGuard.validate_ledger_entry(system_ledger)
        WalletInvariantGuard.validate_wallet(wallet)
        self._session.add(task_ledger)
        self._session.add(system_ledger)
        return task_ledger, system_ledger

    def debit_system_balance(
        self,
        *,
        wallet: WalletAccount,
        account_id: str,
        user_id: str,
        amount: Decimal,
        currency: str,
        transaction_type: str,
        source_type: str,
        note: str | None,
        reference_type: str | None,
        reference_id: str | None,
        status: str = "paid",
        idempotency_key: str | None = None,
    ) -> tuple[WalletSplit, WalletLedgerEntry]:
        self.ensure_split_balance(wallet=wallet)
        resolved_idempotency_key = idempotency_key or self._build_idempotency_key(
            account_id=account_id,
            wallet_account_id=wallet.id,
            user_id=user_id,
            ledger_type="system",
            transaction_type=transaction_type,
            direction="debit",
            source_type=source_type,
            reference_type=reference_type,
            reference_id=reference_id,
        )
        existing = self._find_existing_ledger(account_id=account_id, idempotency_key=resolved_idempotency_key)
        if existing is not None:
            return (
                WalletSplit(
                    cash_amount=self._quantize(self._value(existing.cash_amount)),
                    bonus_amount=self._quantize(self._value(existing.bonus_amount)),
                ),
                existing,
            )
        split = self.calculate_cash_bonus_split(wallet=wallet, amount=amount)
        balance_before = self._quantize(self._value(wallet.system_balance))
        cash_before = self._quantize(self._value(wallet.system_cash_balance))
        bonus_before = self._quantize(self._value(wallet.system_bonus_balance))

        wallet.system_cash_balance = self._quantize(cash_before - split.cash_amount)
        wallet.system_bonus_balance = self._quantize(bonus_before - split.bonus_amount)
        self._sync_totals(wallet=wallet)
        self._session.add(wallet)

        ledger_entry = WalletLedgerEntry(
            account_id=account_id,
            wallet_account_id=wallet.id,
            user_id=user_id,
            ledger_type="system",
            transaction_type=transaction_type,
            direction="debit",
            amount=self._quantize(amount),
            currency=currency,
            status=status,
            note=note,
            reference_type=reference_type,
            reference_id=reference_id,
            source_type=source_type,
            fund_type=split.fund_type,
            cash_amount=split.cash_amount,
            bonus_amount=split.bonus_amount,
            balance_before=balance_before,
            balance_after=self._quantize(self._value(wallet.system_balance)),
            cash_balance_before=cash_before,
            cash_balance_after=self._quantize(self._value(wallet.system_cash_balance)),
            bonus_balance_before=bonus_before,
            bonus_balance_after=self._quantize(self._value(wallet.system_bonus_balance)),
            display_category="wallet_debit",
            display_title=note,
            is_bonus=split.bonus_amount > Decimal("0"),
            idempotency_key=resolved_idempotency_key,
        )
        WalletLedgerGuard.enforce_debit(ledger_entry)
        WalletInvariantGuard.validate_ledger_entry(ledger_entry)
        WalletInvariantGuard.validate_wallet(wallet)
        self._session.add(ledger_entry)
        return split, ledger_entry

    def submit_withdrawal(
        self,
        *,
        wallet: WalletAccount,
        withdrawal: WithdrawalRequest,
        note: str,
    ) -> WalletLedgerEntry:
        self.ensure_split_balance(wallet=wallet)
        split = self.calculate_cash_bonus_split(wallet=wallet, amount=Decimal(withdrawal.amount))
        balance_before = self._quantize(self._value(wallet.system_balance))
        cash_before = self._quantize(self._value(wallet.system_cash_balance))
        bonus_before = self._quantize(self._value(wallet.system_bonus_balance))
        cash_frozen_before = self._quantize(self._value(wallet.system_cash_frozen))
        bonus_frozen_before = self._quantize(self._value(wallet.system_bonus_frozen))

        wallet.system_cash_balance = self._quantize(cash_before - split.cash_amount)
        wallet.system_bonus_balance = self._quantize(bonus_before - split.bonus_amount)
        wallet.system_cash_frozen = self._quantize(cash_frozen_before + split.cash_amount)
        wallet.system_bonus_frozen = self._quantize(bonus_frozen_before + split.bonus_amount)
        self._sync_totals(wallet=wallet)

        withdrawal.cash_amount = split.cash_amount
        withdrawal.bonus_amount = split.bonus_amount
        self._session.add(wallet)
        self._session.add(withdrawal)

        ledger_entry = WalletLedgerEntry(
            account_id=withdrawal.account_id,
            wallet_account_id=wallet.id,
            user_id=withdrawal.user_id,
            ledger_type="system",
            transaction_type="withdraw_request",
            direction="debit",
            amount=self._quantize(Decimal(withdrawal.amount)),
            currency=withdrawal.currency,
            status="submitted",
            note=note,
            reference_type="withdrawal_request",
            reference_id=withdrawal.id,
            source_type="withdrawal",
            fund_type=split.fund_type,
            cash_amount=split.cash_amount,
            bonus_amount=split.bonus_amount,
            balance_before=balance_before,
            balance_after=self._quantize(self._value(wallet.system_balance)),
            cash_balance_before=cash_before,
            cash_balance_after=self._quantize(self._value(wallet.system_cash_balance)),
            bonus_balance_before=bonus_before,
            bonus_balance_after=self._quantize(self._value(wallet.system_bonus_balance)),
            display_category="withdrawal",
            display_title=note,
            is_bonus=split.bonus_amount > Decimal("0"),
            idempotency_key=f"withdraw_submit:{withdrawal.id}",
        )
        WalletLedgerGuard.enforce_debit(ledger_entry)
        WalletInvariantGuard.validate_ledger_entry(ledger_entry)
        WalletInvariantGuard.validate_wallet(wallet)
        self._session.add(ledger_entry)
        return ledger_entry

    def reject_withdrawal(
        self,
        *,
        wallet: WalletAccount,
        withdrawal: WithdrawalRequest,
        note: str,
    ) -> WalletLedgerEntry:
        self.ensure_split_balance(wallet=wallet)
        cash_amount = self._quantize(self._value(withdrawal.cash_amount))
        bonus_amount = self._quantize(self._value(withdrawal.bonus_amount))
        balance_before = self._quantize(self._value(wallet.system_balance))
        cash_before = self._quantize(self._value(wallet.system_cash_balance))
        bonus_before = self._quantize(self._value(wallet.system_bonus_balance))

        wallet.system_cash_frozen = self._quantize(self._value(wallet.system_cash_frozen) - cash_amount)
        wallet.system_bonus_frozen = self._quantize(self._value(wallet.system_bonus_frozen) - bonus_amount)
        wallet.system_cash_balance = self._quantize(cash_before + cash_amount)
        wallet.system_bonus_balance = self._quantize(bonus_before + bonus_amount)
        self._sync_totals(wallet=wallet)
        self._session.add(wallet)

        ledger_entry = WalletLedgerEntry(
            account_id=withdrawal.account_id,
            wallet_account_id=wallet.id,
            user_id=withdrawal.user_id,
            ledger_type="system",
            transaction_type="withdraw_reject_refund",
            direction="credit",
            amount=self._quantize(Decimal(withdrawal.amount)),
            currency=withdrawal.currency,
            status="paid",
            note=note,
            reference_type="withdrawal_request",
            reference_id=withdrawal.id,
            source_type="withdrawal_reject_refund",
            fund_type=WalletSplit(cash_amount=cash_amount, bonus_amount=bonus_amount).fund_type,
            cash_amount=cash_amount,
            bonus_amount=bonus_amount,
            balance_before=balance_before,
            balance_after=self._quantize(self._value(wallet.system_balance)),
            cash_balance_before=cash_before,
            cash_balance_after=self._quantize(self._value(wallet.system_cash_balance)),
            bonus_balance_before=bonus_before,
            bonus_balance_after=self._quantize(self._value(wallet.system_bonus_balance)),
            display_category="withdrawal",
            display_title=note,
            is_bonus=bonus_amount > Decimal("0"),
            idempotency_key=f"withdraw_reject:{withdrawal.id}",
        )
        WalletLedgerGuard.enforce_credit(ledger_entry)
        WalletInvariantGuard.validate_ledger_entry(ledger_entry)
        WalletInvariantGuard.validate_wallet(wallet)
        self._session.add(ledger_entry)
        return ledger_entry

    def settle_paid_withdrawal(self, *, wallet: WalletAccount, withdrawal: WithdrawalRequest) -> WalletLedgerEntry:
        self.ensure_split_balance(wallet=wallet)
        idempotency_key = f"withdraw_paid:{withdrawal.id}"
        existing = self._find_existing_ledger(account_id=withdrawal.account_id, idempotency_key=idempotency_key)
        if existing is not None:
            return existing
        cash_amount = self._quantize(self._value(withdrawal.cash_amount))
        bonus_amount = self._quantize(self._value(withdrawal.bonus_amount))
        balance_before = self._quantize(self._value(wallet.system_balance))
        cash_before = self._quantize(self._value(wallet.system_cash_balance))
        bonus_before = self._quantize(self._value(wallet.system_bonus_balance))
        cash_frozen_before = self._quantize(self._value(wallet.system_cash_frozen))
        bonus_frozen_before = self._quantize(self._value(wallet.system_bonus_frozen))
        wallet.system_cash_frozen = self._quantize(self._value(wallet.system_cash_frozen) - self._value(withdrawal.cash_amount))
        wallet.system_bonus_frozen = self._quantize(
            self._value(wallet.system_bonus_frozen) - self._value(withdrawal.bonus_amount)
        )
        self._sync_totals(wallet=wallet)
        ledger_entry = WalletLedgerEntry(
            account_id=withdrawal.account_id,
            wallet_account_id=wallet.id,
            user_id=withdrawal.user_id,
            ledger_type="system",
            transaction_type="withdraw_paid_settlement",
            direction="debit",
            amount=self._quantize(Decimal(withdrawal.amount)),
            currency=withdrawal.currency,
            status="paid",
            note="Withdrawal payout settled",
            reference_type="withdrawal_request",
            reference_id=withdrawal.id,
            source_type="withdrawal_paid",
            fund_type=WalletSplit(cash_amount=cash_amount, bonus_amount=bonus_amount).fund_type,
            cash_amount=cash_amount,
            bonus_amount=bonus_amount,
            balance_before=balance_before,
            balance_after=self._quantize(self._value(wallet.system_balance)),
            cash_balance_before=cash_before,
            cash_balance_after=self._quantize(self._value(wallet.system_cash_balance)),
            bonus_balance_before=bonus_before,
            bonus_balance_after=self._quantize(self._value(wallet.system_bonus_balance)),
            idempotency_key=idempotency_key,
            metadata_json={
                "cash_frozen_before": f"{cash_frozen_before:.2f}",
                "cash_frozen_after": f"{self._quantize(self._value(wallet.system_cash_frozen)):.2f}",
                "bonus_frozen_before": f"{bonus_frozen_before:.2f}",
                "bonus_frozen_after": f"{self._quantize(self._value(wallet.system_bonus_frozen)):.2f}",
            },
        )
        WalletLedgerGuard.enforce_debit(ledger_entry)
        WalletInvariantGuard.validate_ledger_entry(ledger_entry)
        WalletInvariantGuard.validate_wallet(wallet)
        self._session.add(wallet)
        self._session.add(ledger_entry)
        return ledger_entry

    def calculate_cash_bonus_split(self, *, wallet: WalletAccount, amount: Decimal) -> WalletSplit:
        self.ensure_split_balance(wallet=wallet)
        sanitized_amount = self._quantize(amount)
        cash_balance = self._quantize(self._value(wallet.system_cash_balance))
        bonus_balance = self._quantize(self._value(wallet.system_bonus_balance))
        cash_amount = min(cash_balance, sanitized_amount)
        bonus_amount = sanitized_amount - cash_amount
        if bonus_amount > bonus_balance:
            raise ValueError("System balance is insufficient.")
        return WalletSplit(
            cash_amount=self._quantize(cash_amount),
            bonus_amount=self._quantize(bonus_amount),
        )

    def _find_existing_ledger(self, *, account_id: str, idempotency_key: str) -> WalletLedgerEntry | None:
        for pending in self._session.new:
            if not isinstance(pending, WalletLedgerEntry):
                continue
            if pending.account_id == account_id and pending.idempotency_key == idempotency_key:
                return pending
        return self._session.scalars(
            select(WalletLedgerEntry).where(
                WalletLedgerEntry.account_id == account_id,
                WalletLedgerEntry.idempotency_key == idempotency_key,
            )
        ).first()

    @staticmethod
    def _sync_totals(*, wallet: WalletAccount) -> None:
        wallet.system_balance = WalletLedgerService._quantize(
            WalletLedgerService._value(wallet.system_cash_balance)
            + WalletLedgerService._value(wallet.system_bonus_balance)
        )
        wallet.frozen_balance = WalletLedgerService._quantize(
            WalletLedgerService._value(wallet.system_cash_frozen)
            + WalletLedgerService._value(wallet.system_bonus_frozen)
        )

    @staticmethod
    def _build_idempotency_key(
        *,
        account_id: str,
        wallet_account_id: str | None,
        user_id: str,
        ledger_type: str,
        transaction_type: str,
        direction: str,
        source_type: str | None,
        reference_type: str | None,
        reference_id: str | None,
    ) -> str:
        raw = "|".join(
            [
                account_id,
                wallet_account_id or "",
                user_id,
                ledger_type,
                transaction_type,
                direction,
                source_type or "",
                reference_type or "",
                reference_id or "",
            ]
        )
        return f"wallet:{sha256(raw.encode('utf-8')).hexdigest()}"

    @staticmethod
    def _quantize(amount: Decimal) -> Decimal:
        return amount.quantize(TWOPLACES, rounding=ROUND_HALF_UP)

    @staticmethod
    def _value(amount: Decimal | None) -> Decimal:
        if amount is None:
            return Decimal("0")
        return Decimal(amount)
