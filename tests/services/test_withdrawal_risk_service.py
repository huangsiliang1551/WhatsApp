from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Account, AppUser, WithdrawalRequest


def _seed_user(session: Session, *, account_id: str, user_id: str) -> AppUser:
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
    session.add_all([account, user])
    session.flush()
    return user


def _make_withdrawal(
    *,
    withdrawal_id: str,
    account_id: str,
    user_id: str,
    status: str,
    amount: str = "100.00",
    duplicate_account_count: int = 0,
    risk_level: str | None = None,
    risk_flags: list[str] | None = None,
) -> WithdrawalRequest:
    return WithdrawalRequest(
        id=withdrawal_id,
        account_id=account_id,
        wallet_account_id=f"wallet-{user_id}",
        user_id=user_id,
        request_no=f"WD-{withdrawal_id}",
        amount=Decimal(amount),
        cash_amount=Decimal(amount),
        bonus_amount=Decimal("0.00"),
        currency="USD",
        status=status,
        duplicate_account_count=duplicate_account_count,
        risk_level=risk_level,
        risk_flags=risk_flags,
    )


def test_withdrawal_risk_blocks_duplicate_active_withdrawal(
    db_session_factory: sessionmaker[Session],
) -> None:
    from app.services.withdrawal_risk_service import WithdrawalRiskService

    with db_session_factory() as session:
        user = _seed_user(session, account_id="acct-risk-duplicate-active", user_id="user-risk-duplicate-active")
        current = _make_withdrawal(
            withdrawal_id="wd-current",
            account_id=user.account_id,
            user_id=user.id,
            status="submitted",
        )
        other_active = _make_withdrawal(
            withdrawal_id="wd-other",
            account_id=user.account_id,
            user_id=user.id,
            status="reviewing",
        )
        session.add_all([current, other_active])
        session.commit()

        decision = WithdrawalRiskService(session=session).evaluate_for_transition(
            withdrawal=current,
            next_status="approved",
        )

        assert decision.allowed is False
        assert decision.reason_code == "duplicate_active_withdrawal"


def test_withdrawal_risk_requires_second_review_for_duplicate_account(
    db_session_factory: sessionmaker[Session],
) -> None:
    from app.services.withdrawal_risk_service import WithdrawalRiskService

    with db_session_factory() as session:
        user = _seed_user(session, account_id="acct-risk-duplicate-account", user_id="user-risk-duplicate-account")
        withdrawal = _make_withdrawal(
            withdrawal_id="wd-risk-review",
            account_id=user.account_id,
            user_id=user.id,
            status="submitted",
            duplicate_account_count=1,
            risk_level="low",
            risk_flags=["duplicate_withdraw_account"],
        )
        session.add(withdrawal)
        session.commit()

        decision = WithdrawalRiskService(session=session).evaluate_for_transition(
            withdrawal=withdrawal,
            next_status="approved",
        )

        assert decision.allowed is False
        assert decision.reason_code == "second_review_required"


def test_withdrawal_risk_allows_approve_after_reviewing_for_duplicate_account(
    db_session_factory: sessionmaker[Session],
) -> None:
    from app.services.withdrawal_risk_service import WithdrawalRiskService

    with db_session_factory() as session:
        user = _seed_user(session, account_id="acct-risk-reviewed", user_id="user-risk-reviewed")
        withdrawal = _make_withdrawal(
            withdrawal_id="wd-reviewed",
            account_id=user.account_id,
            user_id=user.id,
            status="reviewing",
            duplicate_account_count=1,
            risk_level="low",
            risk_flags=["duplicate_withdraw_account"],
        )
        session.add(withdrawal)
        session.commit()

        decision = WithdrawalRiskService(session=session).evaluate_for_transition(
            withdrawal=withdrawal,
            next_status="approved",
        )

        assert decision.allowed is True
