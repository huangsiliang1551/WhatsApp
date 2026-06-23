from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import WalletAccount, WalletLedgerEntry, WithdrawalAuditLog, WithdrawalRequest
from tests.test_h5_member_auth import _create_site, _operator_headers, _register_member
from tests.test_h5_task_packages_wallet import _seed_task_package_scope


def _finance_headers(*account_ids: str) -> dict[str, str]:
    return {
        "X-Actor-Id": "finance-platform-withdrawals",
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
    system_balance: Decimal = Decimal("150"),
    amount: float = 120,
) -> tuple[dict[str, object], dict[str, object]]:
    site = _create_site(client, account_id=account_id, site_key=site_key)
    auth_payload = _register_member(
        client,
        site_key=site_key,
        phone=phone,
        display_name=f"Withdraw {site_key}",
    )
    _seed_task_package_scope(
        db_session_factory,
        account_id=account_id,
        site_id=site["id"],
        public_user_id=auth_payload["member"]["publicUserId"],
        system_balance=system_balance,
        task_balance=Decimal("0"),
    )
    create_response = client.post("/api/h5/withdrawals", json={"amount": amount})
    assert create_response.status_code == 200, create_response.text
    return site, create_response.json()


def test_platform_can_list_account_scoped_withdrawals(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _, first = _seed_member_withdrawal(
        client,
        db_session_factory,
        account_id="acct-platform-withdrawals-a",
        site_key="platform-withdrawals-a",
        phone="+86139000677901",
    )
    _, second = _seed_member_withdrawal(
        client,
        db_session_factory,
        account_id="acct-platform-withdrawals-b",
        site_key="platform-withdrawals-b",
        phone="+86139000677902",
    )

    response = client.get(
        "/api/platform/withdrawals",
        headers=_finance_headers("acct-platform-withdrawals-a"),
    )
    assert response.status_code == 200, response.text
    items = response.json()
    assert len(items) == 1
    assert items[0]["id"] == first["id"]
    assert items[0]["accountId"] == "acct-platform-withdrawals-a"
    assert items[0]["status"] == "submitted"
    assert items[0]["requestNo"] == first["requestNo"]
    assert items[0]["history"][0]["status"] == "submitted"

    denied = client.get(
        "/api/platform/withdrawals",
        params={"account_id": "acct-platform-withdrawals-b"},
        headers=_finance_headers("acct-platform-withdrawals-a"),
    )
    assert denied.status_code == 403, denied.text
    assert second["id"] != first["id"]


def test_platform_withdrawal_status_flow_updates_history_and_paid_timestamp(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _, created = _seed_member_withdrawal(
        client,
        db_session_factory,
        account_id="acct-platform-withdrawals-flow",
        site_key="platform-withdrawals-flow",
        phone="+86139000677903",
    )
    headers = _finance_headers("acct-platform-withdrawals-flow")

    reviewing = client.post(
        f"/api/platform/withdrawals/{created['id']}/status",
        json={"status": "reviewing", "note": "Finance is reviewing this request."},
        headers=headers,
    )
    assert reviewing.status_code == 200, reviewing.text
    assert reviewing.json()["status"] == "reviewing"
    assert reviewing.json()["reviewedAt"] is None

    approved = client.post(
        f"/api/platform/withdrawals/{created['id']}/status",
        json={"status": "approved", "note": "Approved for payout."},
        headers=headers,
    )
    assert approved.status_code == 200, approved.text
    approved_payload = approved.json()
    assert approved_payload["status"] == "approved"
    assert approved_payload["reviewedAt"] is not None
    assert approved_payload["paidAt"] is None
    assert [item["status"] for item in approved_payload["history"]] == [
        "submitted",
        "reviewing",
        "approved",
    ]

    paid = client.post(
        f"/api/platform/withdrawals/{created['id']}/status",
        json={"status": "paid", "note": "Payout completed."},
        headers=headers,
    )
    assert paid.status_code == 200, paid.text
    paid_payload = paid.json()
    assert paid_payload["status"] == "paid"
    assert paid_payload["reviewedAt"] is not None
    assert paid_payload["paidAt"] is not None
    assert [item["status"] for item in paid_payload["history"]] == [
        "submitted",
        "reviewing",
        "approved",
        "paid",
    ]

    with db_session_factory() as session:
        withdrawal = session.get(WithdrawalRequest, created["id"])
        assert withdrawal is not None
        assert withdrawal.status == "paid"
        assert withdrawal.reviewed_at is not None
        assert withdrawal.paid_at is not None


def test_platform_reject_withdrawal_restores_wallet_and_writes_refund_ledger(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _, created = _seed_member_withdrawal(
        client,
        db_session_factory,
        account_id="acct-platform-withdrawals-reject",
        site_key="platform-withdrawals-reject",
        phone="+86139000677904",
    )

    response = client.post(
        f"/api/platform/withdrawals/{created['id']}/status",
        json={
            "status": "rejected",
            "note": "Bank card verification failed.",
            "rejection_reason": "bank_card_verification_failed",
        },
        headers=_finance_headers("acct-platform-withdrawals-reject"),
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "rejected"
    assert payload["rejectionReason"] == "bank_card_verification_failed"
    assert payload["reviewedAt"] is not None
    assert payload["paidAt"] is None
    assert [item["status"] for item in payload["history"]] == ["submitted", "rejected"]

    with db_session_factory() as session:
        withdrawal = session.get(WithdrawalRequest, created["id"])
        assert withdrawal is not None
        wallet = session.query(WalletAccount).filter(WalletAccount.id == withdrawal.wallet_account_id).one()
        assert wallet.system_balance == Decimal("150")

        refund_ledgers = session.query(WalletLedgerEntry).filter(
            WalletLedgerEntry.reference_type == "withdrawal_request",
            WalletLedgerEntry.reference_id == created["id"],
            WalletLedgerEntry.transaction_type == "withdraw_reject_refund",
        ).all()
        audit_logs = session.query(WithdrawalAuditLog).filter(
            WithdrawalAuditLog.withdrawal_request_id == created["id"]
        ).all()

        assert len(refund_ledgers) == 1
        assert refund_ledgers[0].direction == "credit"
        assert refund_ledgers[0].amount == Decimal("120")
        assert [item.status for item in audit_logs] == ["submitted", "rejected"]


def test_platform_reject_requires_reason_and_paid_withdrawal_cannot_change(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _, created = _seed_member_withdrawal(
        client,
        db_session_factory,
        account_id="acct-platform-withdrawals-guard",
        site_key="platform-withdrawals-guard",
        phone="+86139000677905",
    )
    headers = _finance_headers("acct-platform-withdrawals-guard")

    missing_reason = client.post(
        f"/api/platform/withdrawals/{created['id']}/status",
        json={"status": "rejected", "note": "Rejected without reason."},
        headers=headers,
    )
    assert missing_reason.status_code == 409, missing_reason.text
    assert "rejection reason" in missing_reason.json()["detail"].lower()

    approved = client.post(
        f"/api/platform/withdrawals/{created['id']}/status",
        json={"status": "approved", "note": "Approved."},
        headers=headers,
    )
    assert approved.status_code == 200, approved.text
    paid = client.post(
        f"/api/platform/withdrawals/{created['id']}/status",
        json={"status": "paid", "note": "Paid."},
        headers=headers,
    )
    assert paid.status_code == 200, paid.text

    illegal = client.post(
        f"/api/platform/withdrawals/{created['id']}/status",
        json={
            "status": "rejected",
            "note": "Too late.",
            "rejection_reason": "too_late",
        },
        headers=headers,
    )
    assert illegal.status_code == 409, illegal.text
    assert "cannot transition" in illegal.json()["detail"].lower()


def test_platform_withdrawal_status_updates_emit_member_wallet_notifications(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _, created = _seed_member_withdrawal(
        client,
        db_session_factory,
        account_id="acct-platform-withdrawals-notify",
        site_key="platform-withdrawals-notify",
        phone="+86139000677906",
    )
    headers = _finance_headers("acct-platform-withdrawals-notify")

    approved = client.post(
        f"/api/platform/withdrawals/{created['id']}/status",
        json={"status": "approved", "note": "Approved and queued for payout."},
        headers=headers,
    )
    assert approved.status_code == 200, approved.text

    paid = client.post(
        f"/api/platform/withdrawals/{created['id']}/status",
        json={"status": "paid", "note": "Funds have been sent."},
        headers=headers,
    )
    assert paid.status_code == 200, paid.text

    messages_response = client.get("/api/h5/messages")
    assert messages_response.status_code == 200, messages_response.text
    messages = messages_response.json()
    assert [item["category"] for item in messages[:2]] == ["wallet", "wallet"]
    assert messages[0]["title"] == "Withdrawal paid"
    assert "Funds have been sent." in messages[0]["bodyText"]
    assert messages[0]["isRead"] is False
    assert messages[1]["title"] == "Withdrawal approved"
    assert "Approved and queued for payout." in messages[1]["bodyText"]
    message_id = messages[0]["id"]

    detail_response = client.get(f"/api/h5/messages/{message_id}")
    assert detail_response.status_code == 200, detail_response.text
    detail_payload = detail_response.json()
    assert detail_payload["id"] == message_id
    assert detail_payload["title"] == "Withdrawal paid"
    assert "Funds have been sent." in detail_payload["bodyText"]
    assert detail_payload["isRead"] is False

    home_response = client.get("/api/h5/member/home")
    assert home_response.status_code == 200, home_response.text
    home_payload = home_response.json()
    assert home_payload["unreadMessageCount"] == 2
    assert home_payload["recentMessages"][0]["title"] == "Withdrawal paid"
    assert home_payload["recentMessages"][1]["title"] == "Withdrawal approved"

    read_response = client.post(f"/api/h5/messages/{message_id}/read")
    assert read_response.status_code == 200, read_response.text
    assert read_response.json()["isRead"] is True
    assert read_response.json()["readAt"] is not None

    home_after_read = client.get("/api/h5/member/home")
    assert home_after_read.status_code == 200, home_after_read.text
    assert home_after_read.json()["unreadMessageCount"] == 1
