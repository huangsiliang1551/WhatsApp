from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.orm import Session

from app.db.models import WalletAccount, WalletLedgerEntry, WithdrawalRequest


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
    ) -> WalletLedgerEntry:
        self.ensure_split_balance(wallet=wallet)
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
        )
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
    ) -> tuple[WalletLedgerEntry, WalletLedgerEntry]:
        self.ensure_split_balance(wallet=wallet)
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
        )
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
    ) -> tuple[WalletSplit, WalletLedgerEntry]:
        self.ensure_split_balance(wallet=wallet)
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
        )
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
        )
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
        )
        self._session.add(ledger_entry)
        return ledger_entry

    def settle_paid_withdrawal(self, *, wallet: WalletAccount, withdrawal: WithdrawalRequest) -> None:
        self.ensure_split_balance(wallet=wallet)
        wallet.system_cash_frozen = self._quantize(self._value(wallet.system_cash_frozen) - self._value(withdrawal.cash_amount))
        wallet.system_bonus_frozen = self._quantize(
            self._value(wallet.system_bonus_frozen) - self._value(withdrawal.bonus_amount)
        )
        self._sync_totals(wallet=wallet)
        self._session.add(wallet)

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
    def _quantize(amount: Decimal) -> Decimal:
        return amount.quantize(TWOPLACES, rounding=ROUND_HALF_UP)

    @staticmethod
    def _value(amount: Decimal | None) -> Decimal:
        if amount is None:
            return Decimal("0")
        return Decimal(amount)
