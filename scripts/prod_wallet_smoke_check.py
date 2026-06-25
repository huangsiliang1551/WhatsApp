from __future__ import annotations

import json
import sys
from typing import Any

from app.db.session import get_sessionmaker
from scripts.check_wallet_balance_invariants import build_invariant_report


def run_checks() -> dict[str, Any]:
    session_factory = get_sessionmaker()
    with session_factory() as session:
        report = build_invariant_report(session)

    grouped = {
        "balance_check": [item for item in report["violations"] if item["kind"] == "wallet_balance_mismatch"],
        "frozen_check": [item for item in report["violations"] if item["kind"] == "wallet_frozen_mismatch"],
        "duplicate_check": [item for item in report["violations"] if item["kind"] == "wallet_duplicate_idempotency_key"],
        "withdrawal_check": [item for item in report["violations"] if item["kind"] == "withdrawal_split_mismatch"],
        "other_checks": [
            item
            for item in report["violations"]
            if item["kind"]
            not in {
                "wallet_balance_mismatch",
                "wallet_frozen_mismatch",
                "wallet_duplicate_idempotency_key",
                "withdrawal_split_mismatch",
            }
        ],
    }
    return {
        "ok": report["ok"],
        "violation_count": report["violation_count"],
        "checks": grouped,
    }


def main() -> int:
    report = run_checks()
    print("1. balance invariant check...")
    print(f"violations={len(report['checks']['balance_check'])}")
    print("2. frozen invariant check...")
    print(f"violations={len(report['checks']['frozen_check'])}")
    print("3. duplicate ledger check...")
    print(f"violations={len(report['checks']['duplicate_check'])}")
    print("4. withdrawal split check...")
    print(f"violations={len(report['checks']['withdrawal_check'])}")
    if report["checks"]["other_checks"]:
        print("5. other wallet checks...")
        print(f"violations={len(report['checks']['other_checks'])}")
    print("ALL CHECKS DONE")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
