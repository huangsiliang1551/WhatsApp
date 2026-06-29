from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Account, AppUser, PaymentChannel, RechargeRepairOrder


def _super_admin_headers(*account_ids: str) -> dict[str, str]:
    return {
        "X-Actor-Id": "super-admin-payment-reconciliation",
        "X-Actor-Role": "super_admin",
        "X-Actor-Account-Ids": ",".join(account_ids),
    }


def test_finance_reconciliation_item_can_create_repair(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        account = Account(
            account_id="acct-reconcile-repair",
            display_name="acct-reconcile-repair",
            provider_type="mock",
        )
        user = AppUser(
            id="user-reconcile-repair",
            account_id=account.account_id,
            public_user_id="pub-user-reconcile-repair",
            registration_site_id=None,
            display_name="Reconcile Repair",
            has_phone=True,
            is_anonymous=False,
            lifecycle_status="active",
        )
        channel = PaymentChannel(
            id="channel-reconcile-repair",
            name="Channel Reconcile Repair",
            channel_type="generic_hmac",
            callback_secret="secret",
            status="active",
            config_json={
                "reconciliation_bill": [
                    {
                        "date": "2026-06-29",
                        "order_id": "CH-ORDER-REPAIR-1",
                        "user_id": user.id,
                        "amount": "99.00",
                        "currency": "USD",
                        "status": "success",
                    }
                ]
            },
        )
        session.add_all([account, user, channel])
        session.commit()

    run_response = client.post(
        "/api/finance/reconcile",
        json={"channel_id": "channel-reconcile-repair", "date": "2026-06-29"},
        headers=_super_admin_headers("acct-reconcile-repair"),
    )
    assert run_response.status_code == 200, run_response.text
    rec_id = run_response.json()["id"]

    items_response = client.get(
        f"/api/finance/reconciliations/{rec_id}/items",
        headers=_super_admin_headers("acct-reconcile-repair"),
    )
    assert items_response.status_code == 200, items_response.text
    items = items_response.json()
    assert len(items) == 1
    assert items[0]["item_type"] == "missing_platform"

    repair_response = client.post(
        f"/api/finance/reconciliation-items/{items[0]['id']}/create-repair",
        headers=_super_admin_headers("acct-reconcile-repair"),
    )
    assert repair_response.status_code == 200, repair_response.text
    payload = repair_response.json()
    assert payload["status"] == "repair_created"
    assert payload["repair_order_id"] is not None

    with db_session_factory() as session:
        repair = session.get(RechargeRepairOrder, payload["repair_order_id"])
        assert repair is not None
        assert repair.account_id == "acct-reconcile-repair"
        assert repair.channel_order_no == "CH-ORDER-REPAIR-1"


def test_finance_reconciliation_item_can_be_ignored(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        account = Account(
            account_id="acct-reconcile-ignore",
            display_name="acct-reconcile-ignore",
            provider_type="mock",
        )
        user = AppUser(
            id="user-reconcile-ignore",
            account_id=account.account_id,
            public_user_id="pub-user-reconcile-ignore",
            registration_site_id=None,
            display_name="Reconcile Ignore",
            has_phone=True,
            is_anonymous=False,
            lifecycle_status="active",
        )
        channel = PaymentChannel(
            id="channel-reconcile-ignore",
            name="Channel Reconcile Ignore",
            channel_type="generic_hmac",
            callback_secret="secret",
            status="active",
            config_json={
                "reconciliation_bill": [
                    {
                        "date": "2026-06-29",
                        "order_id": "CH-ORDER-IGNORE-1",
                        "user_id": user.id,
                        "amount": "21.00",
                        "currency": "USD",
                        "status": "success",
                    }
                ]
            },
        )
        session.add_all([account, user, channel])
        session.commit()

    run_response = client.post(
        "/api/finance/reconcile",
        json={"channel_id": "channel-reconcile-ignore", "date": "2026-06-29"},
        headers=_super_admin_headers("acct-reconcile-ignore"),
    )
    rec_id = run_response.json()["id"]
    items_response = client.get(
        f"/api/finance/reconciliations/{rec_id}/items",
        headers=_super_admin_headers("acct-reconcile-ignore"),
    )
    item_id = items_response.json()[0]["id"]

    ignore_response = client.post(
        f"/api/finance/reconciliation-items/{item_id}/ignore",
        json={"reason": "accepted mismatch"},
        headers=_super_admin_headers("acct-reconcile-ignore"),
    )
    assert ignore_response.status_code == 200, ignore_response.text
    payload = ignore_response.json()
    assert payload["status"] == "ignored"


def test_finance_reconciliation_item_can_be_resolved(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        account = Account(
            account_id="acct-reconcile-resolve",
            display_name="acct-reconcile-resolve",
            provider_type="mock",
        )
        user = AppUser(
            id="user-reconcile-resolve",
            account_id=account.account_id,
            public_user_id="pub-user-reconcile-resolve",
            registration_site_id=None,
            display_name="Reconcile Resolve",
            has_phone=True,
            is_anonymous=False,
            lifecycle_status="active",
        )
        channel = PaymentChannel(
            id="channel-reconcile-resolve",
            name="Channel Reconcile Resolve",
            channel_type="generic_hmac",
            callback_secret="secret",
            status="active",
            config_json={
                "reconciliation_bill": [
                    {
                        "date": "2026-06-29",
                        "order_id": "CH-ORDER-RESOLVE-1",
                        "user_id": user.id,
                        "amount": "55.00",
                        "currency": "USD",
                        "status": "success",
                    }
                ]
            },
        )
        session.add_all([account, user, channel])
        session.commit()

    run_response = client.post(
        "/api/finance/reconcile",
        json={"channel_id": "channel-reconcile-resolve", "date": "2026-06-29"},
        headers=_super_admin_headers("acct-reconcile-resolve"),
    )
    rec_id = run_response.json()["id"]
    items_response = client.get(
        f"/api/finance/reconciliations/{rec_id}/items",
        headers=_super_admin_headers("acct-reconcile-resolve"),
    )
    item_id = items_response.json()[0]["id"]

    resolve_response = client.post(
        f"/api/finance/reconciliation-items/{item_id}/resolve",
        json={"reason": "checked with provider"},
        headers=_super_admin_headers("acct-reconcile-resolve"),
    )
    assert resolve_response.status_code == 200, resolve_response.text
    payload = resolve_response.json()
    assert payload["status"] == "resolved"
