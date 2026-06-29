from __future__ import annotations

from decimal import Decimal

from app.db.models import WalletAccount
from app.db.models import WalletLedgerEntry


class WalletInvariantError(ValueError):
    """Raised when wallet balances or ledger entries become inconsistent."""


class WalletInvariantGuard:
    @staticmethod
    def validate(wallet: WalletAccount) -> None:
        WalletInvariantGuard.validate_wallet(wallet)

    @staticmethod
    def validate_wallet(wallet: WalletAccount) -> None:
        errors: list[str] = []

        system_balance = WalletInvariantGuard._amount(wallet.system_balance)
        system_cash_balance = WalletInvariantGuard._amount(wallet.system_cash_balance)
        system_bonus_balance = WalletInvariantGuard._amount(wallet.system_bonus_balance)
        frozen_balance = WalletInvariantGuard._amount(wallet.frozen_balance)
        system_cash_frozen = WalletInvariantGuard._amount(wallet.system_cash_frozen)
        system_bonus_frozen = WalletInvariantGuard._amount(wallet.system_bonus_frozen)

        if system_balance != (system_cash_balance + system_bonus_balance):
            errors.append("BALANCE_MISMATCH")

        if frozen_balance != (system_cash_frozen + system_bonus_frozen):
            errors.append("FROZEN_MISMATCH")

        if system_cash_balance < Decimal("0.00") or system_bonus_balance < Decimal("0.00"):
            errors.append("NEGATIVE_BALANCE")

        if system_cash_frozen < Decimal("0.00") or system_bonus_frozen < Decimal("0.00"):
            errors.append("NEGATIVE_FROZEN")

        if errors:
            raise WalletInvariantError(f"WALLET_INVARIANT_ERROR: {errors}")

    @staticmethod
    def validate_ledger_entry(entry: WalletLedgerEntry) -> None:
        amount = WalletInvariantGuard._amount(entry.amount)
        cash_amount = WalletInvariantGuard._amount(entry.cash_amount)
        bonus_amount = WalletInvariantGuard._amount(entry.bonus_amount)
        task_amount = WalletInvariantGuard._amount(entry.task_amount)

        if amount < Decimal("0.00"):
            raise WalletInvariantError("NEGATIVE_LEDGER_AMOUNT")
        if cash_amount < Decimal("0.00") or bonus_amount < Decimal("0.00") or task_amount < Decimal("0.00"):
            raise WalletInvariantError("NEGATIVE_LEDGER_SPLIT")
        if not getattr(entry, "idempotency_key", None):
            raise WalletInvariantError("MISSING_IDEMPOTENCY_KEY")
        if not getattr(entry, "source_type", None):
            raise WalletInvariantError("LEDGER_SOURCE_TYPE_REQUIRED")
        if not getattr(entry, "reference_type", None) or not getattr(entry, "reference_id", None):
            raise WalletInvariantError("LEDGER_REFERENCE_REQUIRED")
        if entry.ledger_type == "system" and amount != cash_amount + bonus_amount:
            raise WalletInvariantError("SYSTEM_LEDGER_AMOUNT_MISMATCH")
        if entry.ledger_type == "task" and task_amount not in {Decimal("0.00"), amount}:
            raise WalletInvariantError("TASK_LEDGER_AMOUNT_MISMATCH")

    @staticmethod
    def _amount(value: Decimal | None) -> Decimal:
        if value is None:
            return Decimal("0.00")
        return Decimal(value).quantize(Decimal("0.01"))
