from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import WalletAccount, WithdrawalRequest, utc_now
from tests.test_h5_member_auth import _create_site, _register_member
from tests.test_h5_task_packages_wallet import _seed_task_package_scope


def test_h5_withdrawal_create_and_list_flow(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-h5-withdraw", site_key="h5-withdraw")
    auth_payload = _register_member(
        client,
        site_key="h5-withdraw",
        phone="+8613900088888",
        display_name="Withdraw Member",
    )
    _seed_task_package_scope(
        db_session_factory,
        account_id="acct-h5-withdraw",
        site_id=site["id"],
        public_user_id=auth_payload["member"]["publicUserId"],
        system_balance=Decimal("150"),
        task_balance=Decimal("20"),
    )

    create_response = client.post("/api/h5/withdrawals", json={"amount": 120})
    assert create_response.status_code == 200, create_response.text
    created = create_response.json()
    assert created["amount"] == 120.0
    assert created["cashAmount"] == 120.0
    assert created["bonusAmount"] == 0.0
    assert created["status"] == "submitted"

    wallet_response = client.get("/api/h5/wallet")
    assert wallet_response.status_code == 200, wallet_response.text
    wallet_payload = wallet_response.json()
    assert wallet_payload["systemBalance"] == 30.0
    assert wallet_payload["taskBalance"] == 20.0

    list_response = client.get("/api/h5/withdrawals")
    assert list_response.status_code == 200, list_response.text
    items = list_response.json()
    assert len(items) == 1
    assert items[0]["id"] == created["id"]
    assert items[0]["status"] == "submitted"

    messages_response = client.get("/api/h5/messages")
    assert messages_response.status_code == 200, messages_response.text
    messages = messages_response.json()
    assert len(messages) == 1
    assert messages[0]["title"] == "Withdrawal submitted"
    assert messages[0]["category"] == "wallet"
    assert "120.00 USD" in messages[0]["bodyText"]

    home_response = client.get("/api/h5/member/home")
    assert home_response.status_code == 200, home_response.text
    assert home_response.json()["unreadMessageCount"] == 1
    assert home_response.json()["recentMessages"][0]["title"] == "Withdrawal submitted"

    with db_session_factory() as session:
        withdrawal = session.get(WithdrawalRequest, created["id"])
        assert withdrawal is not None
        wallet = session.get(WalletAccount, withdrawal.wallet_account_id)
        assert wallet is not None
        assert withdrawal.cash_amount == Decimal("120")
        assert withdrawal.bonus_amount == Decimal("0")
        assert wallet.system_balance == Decimal("30")
        assert wallet.system_cash_balance == Decimal("30")
        assert wallet.system_bonus_balance == Decimal("0")
        assert wallet.system_cash_frozen == Decimal("120")
        assert wallet.system_bonus_frozen == Decimal("0")


def test_h5_withdrawal_rejects_below_threshold_or_insufficient_system_balance(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-h5-withdraw-low", site_key="h5-withdraw-low")
    auth_payload = _register_member(
        client,
        site_key="h5-withdraw-low",
        phone="+8613900099999",
        display_name="Low Withdraw Member",
    )
    _seed_task_package_scope(
        db_session_factory,
        account_id="acct-h5-withdraw-low",
        site_id=site["id"],
        public_user_id=auth_payload["member"]["publicUserId"],
        system_balance=Decimal("80"),
        task_balance=Decimal("200"),
    )

    threshold_response = client.post("/api/h5/withdrawals", json={"amount": 50})
    assert threshold_response.status_code == 409, threshold_response.text
    assert "threshold" in str(threshold_response.json()["detail"]).lower()

    with db_session_factory() as session:
        session.execute(
            text("UPDATE wallet_accounts SET system_balance = 150 WHERE account_id = 'acct-h5-withdraw-low'")
        )
        session.commit()

    insufficient_response = client.post("/api/h5/withdrawals", json={"amount": 180})
    assert insufficient_response.status_code == 409, insufficient_response.text
    assert "insufficient" in str(insufficient_response.json()["detail"]).lower()


def test_h5_withdraw_leaderboard_returns_empty_until_paid_requests_exist(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-h5-withdraw-board", site_key="h5-withdraw-board")
    auth_payload = _register_member(
        client,
        site_key="h5-withdraw-board",
        phone="+8613900010101",
        display_name="Leaderboard Member",
    )
    _seed_task_package_scope(
        db_session_factory,
        account_id="acct-h5-withdraw-board",
        site_id=site["id"],
        public_user_id=auth_payload["member"]["publicUserId"],
        system_balance=Decimal("200"),
        task_balance=Decimal("0"),
    )

    create_response = client.post("/api/h5/withdrawals", json={"amount": 100})
    assert create_response.status_code == 200, create_response.text

    leaderboard_response = client.get("/api/h5/withdraw-leaderboard")
    assert leaderboard_response.status_code == 200, leaderboard_response.text
    assert leaderboard_response.json() == []


def test_h5_withdraw_leaderboard_aggregates_paid_requests_and_masks_member_no(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-h5-withdraw-board-paid", site_key="h5-withdraw-board-paid")
    auth_payload = _register_member(
        client,
        site_key="h5-withdraw-board-paid",
        phone="+8613900010202",
        display_name="Leaderboard Paid Member",
    )
    _seed_task_package_scope(
        db_session_factory,
        account_id="acct-h5-withdraw-board-paid",
        site_id=site["id"],
        public_user_id=auth_payload["member"]["publicUserId"],
        system_balance=Decimal("260"),
        task_balance=Decimal("0"),
    )

    create_response = client.post("/api/h5/withdrawals", json={"amount": 120})
    assert create_response.status_code == 200, create_response.text
    withdrawal_id = create_response.json()["id"]

    with db_session_factory() as session:
        request = session.get(WithdrawalRequest, withdrawal_id)
        assert request is not None
        request.status = "paid"
        request.paid_at = utc_now()
        session.add(request)
        session.commit()

    leaderboard_response = client.get("/api/h5/withdraw-leaderboard")
    assert leaderboard_response.status_code == 200, leaderboard_response.text
    leaderboard = leaderboard_response.json()
    assert len(leaderboard) == 1
    assert leaderboard[0]["rank"] == 1
    assert leaderboard[0]["amount"] == 120.0
    assert leaderboard[0]["accountIdMasked"] == (
        f"{auth_payload['member']['memberNo'][:3]}***{auth_payload['member']['memberNo'][-2:]}"
    )


def test_h5_withdrawal_uses_cash_first_then_bonus_split(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-h5-withdraw-mixed", site_key="h5-withdraw-mixed")
    auth_payload = _register_member(
        client,
        site_key="h5-withdraw-mixed",
        phone="+8613900010303",
        display_name="Mixed Withdraw Member",
    )
    _seed_task_package_scope(
        db_session_factory,
        account_id="acct-h5-withdraw-mixed",
        site_id=site["id"],
        public_user_id=auth_payload["member"]["publicUserId"],
        system_balance=Decimal("300"),
        task_balance=Decimal("0"),
    )

    with db_session_factory() as session:
        wallet = session.query(WalletAccount).filter(WalletAccount.account_id == "acct-h5-withdraw-mixed").one()
        wallet.system_cash_balance = Decimal("100")
        wallet.system_bonus_balance = Decimal("200")
        wallet.system_balance = Decimal("300")
        session.add(wallet)
        session.commit()

    create_response = client.post("/api/h5/withdrawals", json={"amount": 250})
    assert create_response.status_code == 200, create_response.text
    created = create_response.json()
    assert created["cashAmount"] == 100.0
    assert created["bonusAmount"] == 150.0

    with db_session_factory() as session:
        withdrawal = session.get(WithdrawalRequest, created["id"])
        assert withdrawal is not None
        wallet = session.get(WalletAccount, withdrawal.wallet_account_id)
        assert wallet is not None
        assert withdrawal.cash_amount == Decimal("100")
        assert withdrawal.bonus_amount == Decimal("150")
        assert wallet.system_balance == Decimal("50")
        assert wallet.system_cash_balance == Decimal("0")
        assert wallet.system_bonus_balance == Decimal("50")
        assert wallet.system_cash_frozen == Decimal("100")
        assert wallet.system_bonus_frozen == Decimal("150")


def test_h5_withdrawal_persists_account_snapshot_and_duplicate_flags(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-h5-withdraw-risk", site_key="h5-withdraw-risk")
    first_auth = _register_member(
        client,
        site_key="h5-withdraw-risk",
        phone="+8613900010401",
        display_name="Risk Withdraw A",
    )
    _seed_task_package_scope(
        db_session_factory,
        account_id="acct-h5-withdraw-risk",
        site_id=site["id"],
        public_user_id=first_auth["member"]["publicUserId"],
        system_balance=Decimal("300"),
        task_balance=Decimal("0"),
    )

    first_response = client.post(
        "/api/h5/withdrawals",
        json={
            "amount": 120,
            "withdraw_account_type": "bank",
            "bank_name": "ICBC",
            "account_no": "6222020000001234",
        },
    )
    assert first_response.status_code == 200, first_response.text
    first_payload = first_response.json()
    assert first_payload["accountNoMasked"] == "************1234"
    assert first_payload["duplicateAccountCount"] == 0
    assert first_payload["riskFlags"] == []

    second_auth = _register_member(
        client,
        site_key="h5-withdraw-risk",
        phone="+8613900010402",
        display_name="Risk Withdraw B",
    )
    _seed_task_package_scope(
        db_session_factory,
        account_id="acct-h5-withdraw-risk",
        site_id=site["id"],
        public_user_id=second_auth["member"]["publicUserId"],
        system_balance=Decimal("300"),
        task_balance=Decimal("0"),
    )

    second_response = client.post(
        "/api/h5/withdrawals",
        json={
            "amount": 150,
            "withdraw_account_type": "bank",
            "bank_name": "ICBC",
            "account_no": "6222020000001234",
        },
    )
    assert second_response.status_code == 200, second_response.text
    second_payload = second_response.json()
    assert second_payload["withdrawAccountType"] == "bank"
    assert second_payload["accountNoMasked"] == "************1234"
    assert second_payload["duplicateAccountCount"] == 1
    assert second_payload["duplicateMemberIds"] == [first_auth["member"]["publicUserId"]]
    assert second_payload["riskLevel"] == "low"
    assert second_payload["riskFlags"] == ["duplicate_withdraw_account"]
    assert second_payload["accountFingerprint"]

    list_response = client.get("/api/h5/withdrawals")
    assert list_response.status_code == 200, list_response.text
    items = list_response.json()
    assert items[0]["id"] == second_payload["id"]
    assert items[0]["duplicateAccountCount"] == 1

    with db_session_factory() as session:
        withdrawal = session.get(WithdrawalRequest, second_payload["id"])
        assert withdrawal is not None
        assert withdrawal.account_no_masked == "************1234"
        assert withdrawal.withdraw_account_type == "bank"
        assert withdrawal.account_fingerprint is not None
        assert withdrawal.duplicate_account_count == 1
        assert withdrawal.risk_level == "low"
        assert withdrawal.risk_flags == ["duplicate_withdraw_account"]
        assert withdrawal.account_snapshot_json == {
            "withdraw_account_type": "bank",
            "bank_name": "ICBC",
            "account_no_masked": "************1234",
        }
