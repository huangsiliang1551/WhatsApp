from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Account, AppUser, WalletAccount
from app.services.wallet_invariant_guard import WalletInvariantGuard
from app.services.wallet_ledger_guard import WalletLedgerGuard
from app.services.wallet_ledger_service import WalletLedgerService


def test_wallet_invariant_guard_raises_for_balance_mismatch() -> None:
    wallet = WalletAccount(
        account_id="acct-guard",
        user_id="user-guard",
        system_balance=Decimal("100.00"),
        system_cash_balance=Decimal("60.00"),
        system_bonus_balance=Decimal("30.00"),
        frozen_balance=Decimal("0.00"),
        system_cash_frozen=Decimal("0.00"),
        system_bonus_frozen=Decimal("0.00"),
    )

    with pytest.raises(ValueError, match="BALANCE_MISMATCH"):
        WalletInvariantGuard.validate(wallet)


def test_wallet_ledger_guard_rejects_credit_without_idempotency_key() -> None:
    class Entry:
        amount = Decimal("10.00")
        cash_amount = Decimal("10.00")
        bonus_amount = Decimal("0.00")
        source_type = "manual_real_recharge"
        idempotency_key = None

    with pytest.raises(ValueError, match="MISSING_IDEMPOTENCY_KEY"):
        WalletLedgerGuard.enforce_credit(Entry())


def test_wallet_ledger_service_assigns_idempotency_key_for_credit(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        account = Account(account_id="acct-wallet-guard", display_name="Wallet Guard", provider_type="mock")
        user = AppUser(
            id="user-wallet-guard",
            account_id=account.account_id,
            public_user_id="pub-wallet-guard",
            registration_site_id=None,
            display_name="Wallet Guard User",
            has_phone=True,
            is_anonymous=False,
            lifecycle_status="active",
        )
        wallet = WalletAccount(
            id="wallet-wallet-guard",
            account_id=account.account_id,
            user_id=user.id,
            currency="USD",
        )
        session.add_all([account, user, wallet])
        session.flush()

        ledger = WalletLedgerService(session=session).credit_system_balance(
            wallet=wallet,
            account_id=account.account_id,
            user_id=user.id,
            amount=Decimal("25.00"),
            currency="USD",
            transaction_type="manual_recharge",
            source_type="manual_real_recharge",
            note="Manual recharge credited",
            reference_type="wallet_recharge_order",
            reference_id="recharge-order-1",
            fund_type="cash",
            is_real_recharge=True,
        )
        session.flush()

        assert ledger.idempotency_key is not None
        assert ledger.cash_amount == Decimal("25.00")
        assert wallet.system_balance == Decimal("25.00")
        assert wallet.system_cash_balance == Decimal("25.00")


def test_wallet_ledger_service_assigns_idempotency_key_for_task_credit(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        account = Account(account_id="acct-wallet-task-guard", display_name="Wallet Task Guard", provider_type="mock")
        user = AppUser(
            id="user-wallet-task-guard",
            account_id=account.account_id,
            public_user_id="pub-wallet-task-guard",
            registration_site_id=None,
            display_name="Wallet Task Guard User",
            has_phone=True,
            is_anonymous=False,
            lifecycle_status="active",
        )
        wallet = WalletAccount(
            id="wallet-wallet-task-guard",
            account_id=account.account_id,
            user_id=user.id,
            currency="USD",
        )
        session.add_all([account, user, wallet])
        session.flush()

        ledger = WalletLedgerService(session=session).credit_task_balance(
            wallet=wallet,
            account_id=account.account_id,
            user_id=user.id,
            amount=Decimal("12.50"),
            currency="USD",
            transaction_type="task_reward",
            source_type="task_reward",
            note="Task reward credited",
            reference_type="task_package_instance",
            reference_id="pkg-1",
        )
        session.flush()

        assert ledger.idempotency_key is not None
        assert ledger.task_amount == Decimal("12.50")
        assert ledger.cash_amount == Decimal("0.00")
        assert ledger.bonus_amount == Decimal("0.00")
        assert wallet.task_balance == Decimal("12.50")
