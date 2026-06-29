from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import (
    AppUser,
    MemberProfile,
    MemberVerificationRequest,
    RechargeRecord,
    RechargeRepairOrder,
    WalletAccount,
    WalletLedgerEntry,
)
from tests.test_h5_member_auth import _create_site, _register_member, _seed_task_system_config
from tests.test_h5_task_packages_wallet import _seed_task_package_scope


def _super_admin_headers(*account_ids: str) -> dict[str, str]:
    return {
        "X-Actor-Id": "super-admin-recharge-repairs",
        "X-Actor-Role": "super_admin",
        "X-Actor-Account-Ids": ",".join(account_ids),
    }


def test_recharge_repair_create_approve_and_reject_flow(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-recharge-repairs", site_key="recharge-repairs")
    auth_payload = _register_member(
        client,
        site_key="recharge-repairs",
        phone="+8613900087201",
        display_name="Recharge Repair Member",
    )
    _seed_task_package_scope(
        db_session_factory,
        account_id="acct-recharge-repairs",
        site_id=site["id"],
        public_user_id=auth_payload["member"]["publicUserId"],
        system_balance=Decimal("0"),
        task_balance=Decimal("0"),
    )

    with db_session_factory() as session:
        user = session.query(AppUser).filter(AppUser.public_user_id == auth_payload["member"]["publicUserId"]).one()
        user_id = user.id

    create_response = client.post(
        "/api/finance/recharge-repairs",
        headers=_super_admin_headers("acct-recharge-repairs"),
        json={
            "account_id": "acct-recharge-repairs",
            "user_id": auth_payload["member"]["publicUserId"],
            "amount": 120,
            "currency": "USD",
            "repair_type": "callback_missing",
            "reason": "Missing callback",
            "channel_id": "ch-1",
            "channel_order_no": "order-123",
        },
    )
    assert create_response.status_code == 200, create_response.text
    created = create_response.json()
    assert created["status"] == "pending"
    assert created["public_user_id"] == auth_payload["member"]["publicUserId"]

    approve_response = client.post(
        f"/api/finance/recharge-repairs/{created['id']}/approve",
        headers=_super_admin_headers("acct-recharge-repairs"),
    )
    assert approve_response.status_code == 200, approve_response.text
    approved = approve_response.json()
    assert approved["status"] == "credited"
    assert approved["recharge_record_id"] is not None
    assert approved["ledger_id"] is not None

    duplicate_approve = client.post(
        f"/api/finance/recharge-repairs/{created['id']}/approve",
        headers=_super_admin_headers("acct-recharge-repairs"),
    )
    assert duplicate_approve.status_code == 200, duplicate_approve.text
    assert duplicate_approve.json()["status"] == "credited"

    reject_create = client.post(
        "/api/finance/recharge-repairs",
        headers=_super_admin_headers("acct-recharge-repairs"),
        json={
            "account_id": "acct-recharge-repairs",
            "user_id": auth_payload["member"]["publicUserId"],
            "amount": 50,
            "currency": "USD",
            "repair_type": "callback_failed",
            "reason": "Verification failed",
            "channel_order_no": "order-456",
        },
    )
    reject_id = reject_create.json()["id"]
    reject_response = client.post(
        f"/api/finance/recharge-repairs/{reject_id}/reject",
        headers=_super_admin_headers("acct-recharge-repairs"),
        json={"reason": "not enough evidence"},
    )
    assert reject_response.status_code == 200, reject_response.text
    assert reject_response.json()["status"] == "rejected"

    with db_session_factory() as session:
        wallet = session.query(WalletAccount).filter(WalletAccount.user_id == user_id).one()
        assert wallet.system_balance == Decimal("120")
        assert wallet.system_cash_balance == Decimal("120")
        assert wallet.system_bonus_balance == Decimal("0")

        repair_rows = session.query(RechargeRepairOrder).filter(RechargeRepairOrder.user_id == user_id).all()
        recharge_records = session.query(RechargeRecord).filter(RechargeRecord.user_id == user_id).all()
        ledgers = session.query(WalletLedgerEntry).filter(
            WalletLedgerEntry.user_id == user_id,
            WalletLedgerEntry.transaction_type == "recharge_repair",
        ).all()

        assert len(repair_rows) == 2
        assert len(recharge_records) == 1
        assert len(ledgers) == 1
        assert ledgers[0].cash_amount == Decimal("120")
        assert ledgers[0].is_real_recharge is True
        assert ledgers[0].idempotency_key is not None


def test_recharge_repair_auto_certifies_member_when_threshold_is_reached(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-recharge-repairs-certify", site_key="recharge-repairs-certify")
    auth_payload = _register_member(
        client,
        site_key="recharge-repairs-certify",
        phone="+8613900087202",
        display_name="Recharge Repair Certify Member",
    )
    _seed_task_system_config(
        db_session_factory,
        account_id="acct-recharge-repairs-certify",
        site_id=site["id"],
        certified_recharge_threshold=Decimal("100.00"),
        auto_certify_on_recharge=True,
    )

    create_response = client.post(
        "/api/finance/recharge-repairs",
        headers=_super_admin_headers("acct-recharge-repairs-certify"),
        json={
            "account_id": "acct-recharge-repairs-certify",
            "user_id": auth_payload["member"]["publicUserId"],
            "amount": 100,
            "currency": "USD",
            "repair_type": "callback_missing",
            "reason": "Missing callback",
            "channel_id": "ch-auto-certify",
            "channel_order_no": "order-auto-certify",
        },
    )
    assert create_response.status_code == 200, create_response.text
    created = create_response.json()

    approve_response = client.post(
        f"/api/finance/recharge-repairs/{created['id']}/approve",
        headers=_super_admin_headers("acct-recharge-repairs-certify"),
    )
    assert approve_response.status_code == 200, approve_response.text

    with db_session_factory() as session:
        user = session.query(AppUser).filter(AppUser.public_user_id == auth_payload["member"]["publicUserId"]).one()
        member_profile = session.query(MemberProfile).filter(MemberProfile.user_id == user.id).one()
        request = session.query(MemberVerificationRequest).filter(
            MemberVerificationRequest.account_id == "acct-recharge-repairs-certify",
            MemberVerificationRequest.member_profile_id == member_profile.id,
        ).one()
        assert request.status == "approved"
        assert request.review_note is not None
        assert "auto" in request.review_note.lower()
