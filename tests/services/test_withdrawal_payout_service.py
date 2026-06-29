from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import WalletAccount, WalletLedgerEntry, WithdrawalRequest
from tests.test_h5_member_auth import _create_site, _register_member
from tests.test_h5_task_packages_wallet import _seed_task_package_scope


def _finance_headers(*account_ids: str) -> dict[str, str]:
    return {
        "X-Actor-Id": "finance-withdrawal-paid",
        "X-Actor-Role": "finance",
        "X-Actor-Account-Ids": ",".join(account_ids),
    }


def test_paid_transition_releases_frozen_once_and_persists_settlement_ledger(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-withdrawal-paid", site_key="withdrawal-paid")
    auth_payload = _register_member(
        client,
        site_key="withdrawal-paid",
        phone="+86139000879902",
        display_name="Withdrawal Paid",
    )
    _seed_task_package_scope(
        db_session_factory,
        account_id="acct-withdrawal-paid",
        site_id=site["id"],
        public_user_id=auth_payload["member"]["publicUserId"],
        system_balance=Decimal("200"),
        task_balance=Decimal("0"),
    )

    created = client.post("/api/h5/withdrawals", json={"amount": 120})
    assert created.status_code == 200, created.text
    withdrawal_id = created.json()["id"]

    approved = client.post(
        f"/api/platform/withdrawals/{withdrawal_id}/status",
        json={"status": "approved", "note": "Approved for payout."},
        headers=_finance_headers("acct-withdrawal-paid"),
    )
    assert approved.status_code == 200, approved.text

    first_paid = client.post(
        f"/api/platform/withdrawals/{withdrawal_id}/status",
        json={"status": "paid", "note": "Payout done."},
        headers=_finance_headers("acct-withdrawal-paid"),
    )
    second_paid = client.post(
        f"/api/platform/withdrawals/{withdrawal_id}/status",
        json={"status": "paid", "note": "Payout done."},
        headers=_finance_headers("acct-withdrawal-paid"),
    )
    assert first_paid.status_code == 200, first_paid.text
    assert second_paid.status_code == 200, second_paid.text

    with db_session_factory() as session:
        withdrawal = session.get(WithdrawalRequest, withdrawal_id)
        assert withdrawal is not None
        wallet = session.get(WalletAccount, withdrawal.wallet_account_id)
        assert wallet is not None
        settlement_ledgers = session.query(WalletLedgerEntry).filter(
            WalletLedgerEntry.reference_type == "withdrawal_request",
            WalletLedgerEntry.reference_id == withdrawal_id,
            WalletLedgerEntry.transaction_type == "withdraw_paid_settlement",
        ).all()

        assert wallet.system_cash_frozen == Decimal("0")
        assert wallet.system_bonus_frozen == Decimal("0")
        assert wallet.frozen_balance == Decimal("0")
        assert len(settlement_ledgers) == 1
