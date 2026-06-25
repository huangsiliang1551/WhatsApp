from decimal import Decimal

from sqlalchemy.orm import Session, sessionmaker

from app.db.models import WalletAccount, WalletLedgerEntry, WithdrawalRequest
from scripts.backfill_wallet_cash_bonus import backfill_wallet_cash_bonus
from scripts.check_wallet_balance_invariants import build_invariant_report


def test_wallet_invariant_report_detects_split_balance_mismatch(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        wallet = WalletAccount(
            account_id="acct-wallet-script",
            user_id="user-wallet-script",
            system_balance=Decimal("100"),
            system_cash_balance=Decimal("40"),
            system_bonus_balance=Decimal("30"),
            frozen_balance=Decimal("0"),
        )
        session.add(wallet)
        session.commit()

        report = build_invariant_report(session)

    assert report["ok"] is False
    assert report["violation_count"] >= 1
    assert any(item["kind"] == "wallet_balance_mismatch" for item in report["violations"])


def test_wallet_backfill_script_populates_legacy_wallet_and_ledger_splits(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        wallet = WalletAccount(
            id="wallet-legacy-script",
            account_id="acct-wallet-script",
            user_id="user-wallet-script",
            system_balance=Decimal("80"),
            system_cash_balance=Decimal("0"),
            system_bonus_balance=Decimal("0"),
            frozen_balance=Decimal("20"),
            system_cash_frozen=Decimal("0"),
            system_bonus_frozen=Decimal("0"),
        )
        session.add(wallet)
        session.flush()
        ledger = WalletLedgerEntry(
            account_id="acct-wallet-script",
            wallet_account_id=wallet.id,
            user_id="user-wallet-script",
            ledger_type="system",
            transaction_type="manual_recharge",
            direction="credit",
            amount=Decimal("80"),
            currency="USD",
            status="paid",
            source_type="manual_real_recharge",
            fund_type="cash",
            cash_amount=Decimal("0"),
            bonus_amount=Decimal("0"),
        )
        withdrawal = WithdrawalRequest(
            id="withdraw-legacy-script",
            account_id="acct-wallet-script",
            wallet_account_id=wallet.id,
            user_id="user-wallet-script",
            request_no="WDR-LEGACY-SCRIPT",
            amount=Decimal("20"),
            cash_amount=Decimal("0"),
            bonus_amount=Decimal("0"),
            currency="USD",
            status="submitted",
        )
        session.add_all([ledger, withdrawal])
        session.flush()
        withdraw_ledger = WalletLedgerEntry(
            account_id="acct-wallet-script",
            wallet_account_id=wallet.id,
            user_id="user-wallet-script",
            ledger_type="system",
            transaction_type="withdraw_request",
            direction="debit",
            amount=Decimal("20"),
            currency="USD",
            status="submitted",
            source_type="withdrawal",
            fund_type="cash",
            cash_amount=Decimal("20"),
            bonus_amount=Decimal("0"),
            reference_type="withdrawal_request",
            reference_id=withdrawal.id,
        )
        session.add(withdraw_ledger)
        session.commit()

    with db_session_factory() as session:
        dry_run = backfill_wallet_cash_bonus(session, apply=False)
    assert dry_run["wallet_updates"] >= 2
    assert dry_run["ledger_updates"] >= 1
    assert dry_run["withdrawal_updates"] >= 1

    with db_session_factory() as session:
        applied = backfill_wallet_cash_bonus(session, apply=True)
        assert applied["wallet_updates"] >= 2
        assert applied["ledger_updates"] >= 1
        assert applied["withdrawal_updates"] >= 1

    with db_session_factory() as session:
        wallet = session.get(WalletAccount, "wallet-legacy-script")
        withdrawal = session.get(WithdrawalRequest, "withdraw-legacy-script")
        ledger = session.query(WalletLedgerEntry).filter(WalletLedgerEntry.transaction_type == "manual_recharge").one()

        assert wallet is not None
        assert wallet.system_cash_balance == Decimal("80")
        assert wallet.system_bonus_balance == Decimal("0")
        assert wallet.system_cash_frozen == Decimal("20")
        assert wallet.system_bonus_frozen == Decimal("0")
        assert withdrawal is not None
        assert withdrawal.cash_amount == Decimal("20")
        assert withdrawal.bonus_amount == Decimal("0")
        assert ledger.cash_amount == Decimal("80")
        assert ledger.bonus_amount == Decimal("0")
