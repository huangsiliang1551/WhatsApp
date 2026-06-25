from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import AppUser, WalletAccount, WalletBonusGrantRecord, WalletLedgerEntry
from tests.test_h5_member_auth import _create_site, _register_member
from tests.test_h5_task_packages_wallet import _seed_task_package_scope


def _super_admin_headers(*account_ids: str) -> dict[str, str]:
    return {
        "X-Actor-Id": "super-admin-bonus-grants",
        "X-Actor-Role": "super_admin",
        "X-Actor-Account-Ids": ",".join(account_ids),
    }


def test_bonus_grant_create_approve_and_reject_flow(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-bonus-grants", site_key="bonus-grants")
    auth_payload = _register_member(
        client,
        site_key="bonus-grants",
        phone="+8613900087101",
        display_name="Bonus Grant Member",
    )
    _seed_task_package_scope(
        db_session_factory,
        account_id="acct-bonus-grants",
        site_id=site["id"],
        public_user_id=auth_payload["member"]["publicUserId"],
        system_balance=Decimal("0"),
        task_balance=Decimal("0"),
    )

    with db_session_factory() as session:
        user = session.query(AppUser).filter(AppUser.public_user_id == auth_payload["member"]["publicUserId"]).one()
        user_id = user.id

    create_response = client.post(
        "/api/finance/bonus-grants",
        headers=_super_admin_headers("acct-bonus-grants"),
        json={
            "account_id": "acct-bonus-grants",
            "user_id": auth_payload["member"]["publicUserId"],
            "amount": 200,
            "currency": "USD",
            "source_type": "admin_bonus",
            "reason": "Promo compensation",
        },
    )
    assert create_response.status_code == 200, create_response.text
    created = create_response.json()
    assert created["status"] == "pending"
    assert created["public_user_id"] == auth_payload["member"]["publicUserId"]

    with db_session_factory() as session:
        wallet = session.query(WalletAccount).filter(WalletAccount.user_id == user_id).one()
        assert wallet.system_balance == Decimal("0")
        assert wallet.system_bonus_balance == Decimal("0")

    approve_response = client.post(
        f"/api/finance/bonus-grants/{created['id']}/approve",
        headers=_super_admin_headers("acct-bonus-grants"),
    )
    assert approve_response.status_code == 200, approve_response.text
    approved = approve_response.json()
    assert approved["status"] == "credited"
    assert approved["ledger_id"] is not None

    duplicate_approve = client.post(
        f"/api/finance/bonus-grants/{created['id']}/approve",
        headers=_super_admin_headers("acct-bonus-grants"),
    )
    assert duplicate_approve.status_code == 200, duplicate_approve.text
    assert duplicate_approve.json()["status"] == "credited"

    reject_create = client.post(
        "/api/finance/bonus-grants",
        headers=_super_admin_headers("acct-bonus-grants"),
        json={
            "account_id": "acct-bonus-grants",
            "user_id": auth_payload["member"]["publicUserId"],
            "amount": 50,
            "currency": "USD",
            "source_type": "admin_bonus",
            "reason": "Rejected bonus",
        },
    )
    reject_id = reject_create.json()["id"]
    reject_response = client.post(
        f"/api/finance/bonus-grants/{reject_id}/reject",
        headers=_super_admin_headers("acct-bonus-grants"),
        json={"reason": "invalid request"},
    )
    assert reject_response.status_code == 200, reject_response.text
    assert reject_response.json()["status"] == "rejected"

    with db_session_factory() as session:
        wallet = session.query(WalletAccount).filter(WalletAccount.user_id == user_id).one()
        assert wallet.system_balance == Decimal("200")
        assert wallet.system_bonus_balance == Decimal("200")

        grant_rows = session.query(WalletBonusGrantRecord).filter(WalletBonusGrantRecord.user_id == user_id).all()
        bonus_ledgers = session.query(WalletLedgerEntry).filter(
            WalletLedgerEntry.user_id == user_id,
            WalletLedgerEntry.transaction_type == "bonus_grant",
        ).all()

        assert len(grant_rows) == 2
        assert len(bonus_ledgers) == 1
        assert bonus_ledgers[0].bonus_amount == Decimal("200")
        assert bonus_ledgers[0].cash_amount == Decimal("0")
