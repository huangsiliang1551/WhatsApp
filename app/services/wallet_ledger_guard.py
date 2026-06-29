from __future__ import annotations

from decimal import Decimal
from typing import Any


class WalletLedgerGuard:
    @staticmethod
    def enforce_credit(entry: Any) -> None:
        amount = WalletLedgerGuard._amount(getattr(entry, "amount", None))
        cash_amount = WalletLedgerGuard._amount(getattr(entry, "cash_amount", None))
        bonus_amount = WalletLedgerGuard._amount(getattr(entry, "bonus_amount", None))
        task_amount = WalletLedgerGuard._amount(getattr(entry, "task_amount", None))
        ledger_type = getattr(entry, "ledger_type", None)
        fund_type = getattr(entry, "fund_type", None)

        if ledger_type == "task" or fund_type == "task":
            if task_amount != amount or cash_amount != Decimal("0.00") or bonus_amount != Decimal("0.00"):
                raise ValueError("LEDGER_TASK_SPLIT_INVALID")
        elif cash_amount + bonus_amount != amount:
            raise ValueError("LEDGER_SPLIT_INVALID")

        if not getattr(entry, "source_type", None):
            raise ValueError("MISSING_SOURCE_TYPE")

        if not getattr(entry, "idempotency_key", None):
            raise ValueError("MISSING_IDEMPOTENCY_KEY")

    @staticmethod
    def enforce_debit(entry: Any) -> None:
        if not hasattr(entry, "cash_amount"):
            raise ValueError("MISSING_CASH_SPLIT")
        if not hasattr(entry, "bonus_amount"):
            raise ValueError("MISSING_BONUS_SPLIT")
        if not getattr(entry, "source_type", None):
            raise ValueError("MISSING_SOURCE_TYPE")
        if not getattr(entry, "idempotency_key", None):
            raise ValueError("MISSING_IDEMPOTENCY_KEY")

    @staticmethod
    def _amount(value: Decimal | None) -> Decimal:
        if value is None:
            return Decimal("0.00")
        return Decimal(value).quantize(Decimal("0.01"))
