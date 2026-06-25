from __future__ import annotations

import os
import json
import sys
from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import WalletAccount, WalletLedgerEntry, WithdrawalRequest

TWOPLACES = Decimal("0.01")


@dataclass(slots=True)
class InvariantViolation:
    kind: str
    record_id: str
    account_id: str | None
    detail: str


def _amount(value: Decimal | None) -> Decimal:
    if value is None:
        return Decimal("0.00")
    return Decimal(value).quantize(TWOPLACES)


def collect_wallet_invariant_violations(session: Session) -> list[InvariantViolation]:
    violations: list[InvariantViolation] = []

    wallets = session.execute(select(WalletAccount)).scalars().all()
    for wallet in wallets:
        cash_total = _amount(wallet.system_cash_balance) + _amount(wallet.system_bonus_balance)
        frozen_total = _amount(wallet.system_cash_frozen) + _amount(wallet.system_bonus_frozen)
        if _amount(wallet.system_balance) != cash_total:
            violations.append(
                InvariantViolation(
                    kind="wallet_balance_mismatch",
                    record_id=wallet.id,
                    account_id=wallet.account_id,
                    detail=(
                        f"system_balance={_amount(wallet.system_balance)} "
                        f"!= cash+bonus={cash_total}"
                    ),
                )
            )
        if _amount(wallet.frozen_balance) != frozen_total:
            violations.append(
                InvariantViolation(
                    kind="wallet_frozen_mismatch",
                    record_id=wallet.id,
                    account_id=wallet.account_id,
                    detail=(
                        f"frozen_balance={_amount(wallet.frozen_balance)} "
                        f"!= cash_frozen+bonus_frozen={frozen_total}"
                    ),
                )
            )
        for field_name, value in (
            ("system_cash_balance", wallet.system_cash_balance),
            ("system_bonus_balance", wallet.system_bonus_balance),
            ("system_cash_frozen", wallet.system_cash_frozen),
            ("system_bonus_frozen", wallet.system_bonus_frozen),
        ):
            if _amount(value) < Decimal("0.00"):
                violations.append(
                    InvariantViolation(
                        kind="wallet_negative_split",
                        record_id=wallet.id,
                        account_id=wallet.account_id,
                        detail=f"{field_name}={_amount(value)} is negative",
                    )
                )

    ledgers = session.execute(select(WalletLedgerEntry)).scalars().all()
    wallet_ids_with_ledger = {ledger.wallet_account_id for ledger in ledgers}
    for wallet in wallets:
        if wallet.id not in wallet_ids_with_ledger:
            violations.append(
                InvariantViolation(
                    kind="wallet_missing_ledger",
                    record_id=wallet.id,
                    account_id=wallet.account_id,
                    detail="wallet account has no ledger entries",
                )
            )

    duplicate_idempotency_counts: dict[str, int] = {}
    for ledger in ledgers:
        if ledger.idempotency_key:
            duplicate_idempotency_counts[ledger.idempotency_key] = (
                duplicate_idempotency_counts.get(ledger.idempotency_key, 0) + 1
            )
        if ledger.ledger_type == "system":
            split_total = _amount(ledger.cash_amount) + _amount(ledger.bonus_amount)
            if _amount(ledger.amount) != split_total:
                violations.append(
                    InvariantViolation(
                        kind="system_ledger_split_mismatch",
                        record_id=ledger.id,
                        account_id=ledger.account_id,
                        detail=f"amount={_amount(ledger.amount)} != cash+bonus={split_total}",
                    )
                )
        if (
            ledger.source_type in {"admin_bonus", "invite_bonus", "activity_bonus"}
            and ledger.is_bonus is False
        ):
            violations.append(
                InvariantViolation(
                    kind="wallet_bonus_flag_mismatch",
                    record_id=ledger.id,
                    account_id=ledger.account_id,
                    detail=(
                        f"source_type={ledger.source_type} requires is_bonus=true, "
                        f"but is_bonus={ledger.is_bonus}"
                    ),
                )
            )
        if ledger.ledger_type == "task":
            if _amount(ledger.amount) != _amount(ledger.task_amount):
                violations.append(
                    InvariantViolation(
                        kind="task_ledger_amount_mismatch",
                        record_id=ledger.id,
                        account_id=ledger.account_id,
                        detail=(
                            f"amount={_amount(ledger.amount)} != task_amount={_amount(ledger.task_amount)}"
                        ),
                    )
                )

    for idempotency_key, count in duplicate_idempotency_counts.items():
        if count > 1:
            violations.append(
                InvariantViolation(
                    kind="wallet_duplicate_idempotency_key",
                    record_id=idempotency_key,
                    account_id=None,
                    detail=f"idempotency_key={idempotency_key} duplicated {count} times",
                )
            )

    withdrawals = session.execute(select(WithdrawalRequest)).scalars().all()
    for withdrawal in withdrawals:
        split_total = _amount(withdrawal.cash_amount) + _amount(withdrawal.bonus_amount)
        if split_total not in {Decimal("0.00"), _amount(withdrawal.amount)}:
            violations.append(
                InvariantViolation(
                    kind="withdrawal_split_mismatch",
                    record_id=withdrawal.id,
                    account_id=withdrawal.account_id,
                    detail=f"amount={_amount(withdrawal.amount)} != cash+bonus={split_total}",
                )
            )

    return violations


def build_invariant_report(session: Session) -> dict[str, Any]:
    violations = collect_wallet_invariant_violations(session)
    return {
        "ok": len(violations) == 0,
        "violation_count": len(violations),
        "violations": [asdict(item) for item in violations],
    }


def _load_session_factory():
    from app.db.session import get_sessionmaker

    return get_sessionmaker()


def main() -> int:
    try:
        session_factory = _load_session_factory()
        with session_factory() as session:
            report = build_invariant_report(session)
    except Exception as exc:  # pragma: no cover - CLI fallback path
        error_report = {
            "ok": False,
            "error": str(exc),
            "hint": (
                "Ensure DATABASE_URL points to a reachable database with a working driver, "
                "run alembic upgrade head before checking a fresh database, "
                "or run with TEST_MODE=true for a test-only sqlite context."
            ),
            "test_mode": os.environ.get("TEST_MODE"),
        }
        print(json.dumps(error_report, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
