from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import WithdrawalRequest
from tests.test_h5_member_auth import _create_site, _register_member
from tests.test_h5_task_packages_wallet import _seed_task_package_scope


def _finance_headers(*account_ids: str) -> dict[str, str]:
    return {
        "X-Actor-Id": "finance-withdrawal-risk",
        "X-Actor-Role": "finance",
        "X-Actor-Account-Ids": ",".join(account_ids),
    }


def _seed_member_withdrawal(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
    *,
    account_id: str,
    site_key: str,
    phone: str,
    amount: int = 120,
) -> str:
    site = _create_site(client, account_id=account_id, site_key=site_key)
    auth_payload = _register_member(
        client,
        site_key=site_key,
        phone=phone,
        display_name=f"Risk {site_key}",
    )
    _seed_task_package_scope(
        db_session_factory,
        account_id=account_id,
        site_id=site["id"],
        public_user_id=auth_payload["member"]["publicUserId"],
        system_balance=Decimal("300"),
        task_balance=Decimal("0"),
    )
    response = client.post("/api/h5/withdrawals", json={"amount": amount})
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_platform_withdrawal_policy_blocks_approve_when_another_active_request_exists(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    withdrawal_id = _seed_member_withdrawal(
        client,
        db_session_factory,
        account_id="acct-platform-risk-active",
        site_key="platform-risk-active",
        phone="+86139000879911",
    )

    with db_session_factory() as session:
        withdrawal = session.get(WithdrawalRequest, withdrawal_id)
        assert withdrawal is not None
        extra = WithdrawalRequest(
            account_id=withdrawal.account_id,
            wallet_account_id=withdrawal.wallet_account_id,
            user_id=withdrawal.user_id,
            request_no="WD-RISK-ACTIVE-EXTRA",
            amount=Decimal("50.00"),
            cash_amount=Decimal("50.00"),
            bonus_amount=Decimal("0.00"),
            currency="USD",
            status="reviewing",
        )
        session.add(extra)
        session.commit()

    response = client.post(
        f"/api/platform/withdrawals/{withdrawal_id}/status",
        json={"status": "approved", "note": "Approve blocked by risk."},
        headers=_finance_headers("acct-platform-risk-active"),
    )
    assert response.status_code == 409, response.text
    assert "duplicate active withdrawal" in response.json()["detail"].lower()


def test_platform_withdrawal_policy_requires_review_before_approve_for_duplicate_account(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    first_id = _seed_member_withdrawal(
        client,
        db_session_factory,
        account_id="acct-platform-risk-review",
        site_key="platform-risk-review",
        phone="+86139000879912",
    )
    with db_session_factory() as session:
        first = session.get(WithdrawalRequest, first_id)
        assert first is not None
        first.status = "rejected"
        session.add(first)
        session.commit()

    second_id = _seed_member_withdrawal(
        client,
        db_session_factory,
        account_id="acct-platform-risk-review",
        site_key="platform-risk-review-2",
        phone="+86139000879913",
    )

    with db_session_factory() as session:
        second = session.get(WithdrawalRequest, second_id)
        assert second is not None
        second.account_fingerprint = "same-fingerprint"
        second.duplicate_account_count = 1
        second.risk_level = "low"
        second.risk_flags = ["duplicate_withdraw_account"]
        session.add(second)
        session.commit()

    blocked = client.post(
        f"/api/platform/withdrawals/{second_id}/status",
        json={"status": "approved", "note": "Direct approve should fail."},
        headers=_finance_headers("acct-platform-risk-review"),
    )
    assert blocked.status_code == 409, blocked.text
    assert "second review" in blocked.json()["detail"].lower()

    reviewing = client.post(
        f"/api/platform/withdrawals/{second_id}/status",
        json={"status": "reviewing", "note": "Second review started."},
        headers=_finance_headers("acct-platform-risk-review"),
    )
    assert reviewing.status_code == 200, reviewing.text

    approved = client.post(
        f"/api/platform/withdrawals/{second_id}/status",
        json={"status": "approved", "note": "Approved after second review."},
        headers=_finance_headers("acct-platform-risk-review"),
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"
