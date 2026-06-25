from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import WalletAccount, WalletLedgerEntry, WithdrawalRequest

TWOPLACES = Decimal("0.01")


@dataclass(slots=True)
class BackfillStats:
    wallet_updates: int = 0
    ledger_updates: int = 0
    withdrawal_updates: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "wallet_updates": self.wallet_updates,
            "ledger_updates": self.ledger_updates,
            "withdrawal_updates": self.withdrawal_updates,
        }


def _amount(value: Decimal | None) -> Decimal:
    if value is None:
        return Decimal("0.00")
    return Decimal(value).quantize(TWOPLACES)


def _infer_ledger_split(entry: WalletLedgerEntry) -> tuple[Decimal, Decimal] | None:
    amount = _amount(entry.amount)
    if amount == Decimal("0.00"):
        return Decimal("0.00"), Decimal("0.00")
    if entry.ledger_type == "task":
        return None
    fund_type = (entry.fund_type or "").lower()
    if fund_type == "cash":
        return amount, Decimal("0.00")
    if fund_type == "bonus":
        return Decimal("0.00"), amount
    if fund_type == "mixed":
        return None
    if entry.is_bonus:
        return Decimal("0.00"), amount
    if entry.source_type in {"manual_real_recharge", "payment_callback", "callback_repair"}:
        return amount, Decimal("0.00")
    if entry.source_type in {"admin_bonus", "task_transfer_bonus"}:
        return Decimal("0.00"), amount
    return None


def backfill_wallet_cash_bonus(session: Session, *, apply: bool) -> dict[str, Any]:
    stats = BackfillStats()

    wallets = session.execute(select(WalletAccount)).scalars().all()
    for wallet in wallets:
        if (
            _amount(wallet.system_balance) > Decimal("0.00")
            and _amount(wallet.system_cash_balance) == Decimal("0.00")
            and _amount(wallet.system_bonus_balance) == Decimal("0.00")
        ):
            stats.wallet_updates += 1
            if apply:
                wallet.system_cash_balance = _amount(wallet.system_balance)
                wallet.system_bonus_balance = Decimal("0.00")
        if (
            _amount(wallet.frozen_balance) > Decimal("0.00")
            and _amount(wallet.system_cash_frozen) == Decimal("0.00")
            and _amount(wallet.system_bonus_frozen) == Decimal("0.00")
        ):
            stats.wallet_updates += 1
            if apply:
                wallet.system_cash_frozen = _amount(wallet.frozen_balance)
                wallet.system_bonus_frozen = Decimal("0.00")

    ledgers = session.execute(select(WalletLedgerEntry)).scalars().all()
    for entry in ledgers:
        if _amount(entry.cash_amount) != Decimal("0.00") or _amount(entry.bonus_amount) != Decimal("0.00"):
            continue
        inferred = _infer_ledger_split(entry)
        if inferred is None:
            continue
        cash_amount, bonus_amount = inferred
        stats.ledger_updates += 1
        if apply:
            entry.cash_amount = cash_amount
            entry.bonus_amount = bonus_amount

    withdrawals = session.execute(select(WithdrawalRequest)).scalars().all()
    for withdrawal in withdrawals:
        if _amount(withdrawal.amount) == Decimal("0.00"):
            continue
        if _amount(withdrawal.cash_amount) != Decimal("0.00") or _amount(withdrawal.bonus_amount) != Decimal("0.00"):
            continue
        ledger = session.execute(
            select(WalletLedgerEntry).where(
                WalletLedgerEntry.reference_type == "withdrawal_request",
                WalletLedgerEntry.reference_id == withdrawal.id,
                WalletLedgerEntry.transaction_type == "withdraw_request",
            )
        ).scalar_one_or_none()
        if ledger is None:
            continue
        stats.withdrawal_updates += 1
        if apply:
            withdrawal.cash_amount = _amount(ledger.cash_amount)
            withdrawal.bonus_amount = _amount(ledger.bonus_amount)

    if apply:
        session.commit()
    else:
        session.rollback()

    return {
        "apply": apply,
        **stats.as_dict(),
    }


def _load_session_factory():
    from app.db.session import get_sessionmaker

    return get_sessionmaker()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Backfill wallet cash/bonus split fields from legacy totals.")
    parser.add_argument("--apply", action="store_true", help="Write inferred changes to the database.")
    args = parser.parse_args(argv)

    try:
        session_factory = _load_session_factory()
        with session_factory() as session:
            report = backfill_wallet_cash_bonus(session, apply=args.apply)
    except Exception as exc:  # pragma: no cover - CLI fallback path
        error_report = {
            "ok": False,
            "apply": args.apply,
            "error": str(exc),
            "hint": (
                "Ensure DATABASE_URL points to a reachable database with a working driver, "
                "run alembic upgrade head before backfilling a fresh database, "
                "or run with TEST_MODE=true for a test-only sqlite context."
            ),
            "test_mode": os.environ.get("TEST_MODE"),
        }
        print(json.dumps(error_report, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
