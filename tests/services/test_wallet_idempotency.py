from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Account, AppUser, WalletAccount, WalletLedgerEntry, WithdrawalRequest
from app.services.wallet_ledger_service import WalletLedgerService


def _seed_wallet(session: Session, *, account_id: str, user_id: str, balance: Decimal) -> WalletAccount:
    account = Account(account_id=account_id, display_name=account_id, provider_type="mock")
    user = AppUser(
        id=user_id,
        account_id=account_id,
        public_user_id=f"pub-{user_id}",
        registration_site_id=None,
        display_name=user_id,
        has_phone=True,
        is_anonymous=False,
        lifecycle_status="active",
    )
    wallet = WalletAccount(
        id=f"wallet-{user_id}",
        account_id=account_id,
        user_id=user_id,
        currency="USD",
        system_balance=balance,
        system_cash_balance=balance,
        system_bonus_balance=Decimal("0.00"),
        frozen_balance=Decimal("0.00"),
        system_cash_frozen=Decimal("0.00"),
        system_bonus_frozen=Decimal("0.00"),
    )
    session.add_all([account, user, wallet])
    session.flush()
    return wallet


def test_credit_system_balance_is_idempotent_by_key(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        wallet = _seed_wallet(session, account_id="acct-wallet-idem", user_id="user-wallet-idem", balance=Decimal("0"))
        service = WalletLedgerService(session=session)

        first = service.credit_system_balance(
            wallet=wallet,
            account_id=wallet.account_id,
            user_id=wallet.user_id,
            amount=Decimal("25.00"),
            currency="USD",
            transaction_type="manual_recharge",
            source_type="manual_real_recharge",
            note="Manual recharge",
            reference_type="wallet_recharge_order",
            reference_id="recharge-1",
            fund_type="cash",
            is_real_recharge=True,
            idempotency_key="ledger-idem-1",
        )
        second = service.credit_system_balance(
            wallet=wallet,
            account_id=wallet.account_id,
            user_id=wallet.user_id,
            amount=Decimal("25.00"),
            currency="USD",
            transaction_type="manual_recharge",
            source_type="manual_real_recharge",
            note="Manual recharge",
            reference_type="wallet_recharge_order",
            reference_id="recharge-1",
            fund_type="cash",
            is_real_recharge=True,
            idempotency_key="ledger-idem-1",
        )
        session.flush()

        ledgers = session.scalars(
            select(WalletLedgerEntry).where(WalletLedgerEntry.account_id == wallet.account_id)
        ).all()

        assert first.id == second.id
        assert wallet.system_balance == Decimal("25.00")
        assert len(ledgers) == 1


def test_settle_paid_withdrawal_writes_single_settlement_ledger(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        wallet = _seed_wallet(session, account_id="acct-wallet-paid", user_id="user-wallet-paid", balance=Decimal("100"))
        wallet.system_balance = Decimal("20.00")
        wallet.system_cash_balance = Decimal("20.00")
        wallet.frozen_balance = Decimal("80.00")
        wallet.system_cash_frozen = Decimal("80.00")
        session.add(wallet)
        withdrawal = WithdrawalRequest(
            id="withdraw-paid-1",
            account_id=wallet.account_id,
            wallet_account_id=wallet.id,
            user_id=wallet.user_id,
            request_no="WD-1",
            amount=Decimal("80.00"),
            cash_amount=Decimal("80.00"),
            bonus_amount=Decimal("0.00"),
            currency="USD",
            status="approved",
        )
        session.add(withdrawal)
        session.flush()

        service = WalletLedgerService(session=session)
        first = service.settle_paid_withdrawal(wallet=wallet, withdrawal=withdrawal)
        second = service.settle_paid_withdrawal(wallet=wallet, withdrawal=withdrawal)
        session.flush()

        settlement_ledgers = session.scalars(
            select(WalletLedgerEntry).where(
                WalletLedgerEntry.reference_type == "withdrawal_request",
                WalletLedgerEntry.reference_id == withdrawal.id,
                WalletLedgerEntry.transaction_type == "withdraw_paid_settlement",
            )
        ).all()

        assert first is not None
        assert second is not None
        assert first.id == second.id
        assert wallet.system_cash_frozen == Decimal("0.00")
        assert wallet.frozen_balance == Decimal("0.00")
        assert len(settlement_ledgers) == 1
