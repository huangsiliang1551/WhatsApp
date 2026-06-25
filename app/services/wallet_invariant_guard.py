from __future__ import annotations

from decimal import Decimal

from app.db.models import WalletAccount


class WalletInvariantGuard:
    @staticmethod
    def validate(wallet: WalletAccount) -> None:
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
            raise ValueError(f"WALLET_INVARIANT_ERROR: {errors}")

    @staticmethod
    def _amount(value: Decimal | None) -> Decimal:
        if value is None:
            return Decimal("0.00")
        return Decimal(value).quantize(Decimal("0.01"))
