from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import TaskPackageInstanceItem
from tests.test_h5_member_auth import (
    _create_site,
    _mark_h5_member_whatsapp_bound,
    _register_member,
    _seed_member_wallet,
)
from tests.test_h5_task_packages_wallet import _seed_task_package_scope


def test_h5_task_package_spec_alias_routes_match_legacy_routes(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-h5-task-alias", site_key="h5-task-alias")
    auth_payload = _register_member(
        client,
        site_key="h5-task-alias",
        phone="+86139000999991",
        display_name="Alias Member",
    )
    public_user_id = auth_payload["member"]["publicUserId"]
    _mark_h5_member_whatsapp_bound(db_session_factory, public_user_id=public_user_id)
    seeded = _seed_task_package_scope(
        db_session_factory,
        account_id="acct-h5-task-alias",
        site_id=site["id"],
        public_user_id=public_user_id,
        system_balance=Decimal("500.00"),
        task_balance=Decimal("50.00"),
    )

    legacy_list = client.get("/api/h5/task-packages")
    alias_list = client.get("/api/h5/tasks/packages")
    assert legacy_list.status_code == 200, legacy_list.text
    assert alias_list.status_code == 200, alias_list.text
    assert alias_list.json() == legacy_list.json()

    legacy_detail = client.get(f"/api/h5/task-packages/{seeded['package_id']}")
    alias_detail = client.get(f"/api/h5/tasks/packages/{seeded['package_id']}")
    assert legacy_detail.status_code == 200, legacy_detail.text
    assert alias_detail.status_code == 200, alias_detail.text
    assert alias_detail.json() == legacy_detail.json()

    alias_claim = client.post(f"/api/h5/tasks/packages/{seeded['package_id']}/claim")
    assert alias_claim.status_code == 200, alias_claim.text
    alias_claim_payload = alias_claim.json()
    assert alias_claim_payload["id"] == seeded["package_id"]
    assert alias_claim_payload["status"] == "active"
    assert alias_claim_payload["claimedAt"] is not None
    assert alias_claim_payload["currentItem"]["id"] == seeded["item_a_id"]

    start_response = client.post(
        f"/api/h5/tasks/packages/{seeded['package_id']}/current-product/start"
    )
    assert start_response.status_code == 200, start_response.text
    assert start_response.json()["id"] == seeded["package_id"]
    assert start_response.json()["currentItem"]["id"] == seeded["item_a_id"]
    with db_session_factory() as session:
        started_item = session.query(TaskPackageInstanceItem).filter(
            TaskPackageInstanceItem.id == seeded["item_a_id"]
        ).one()
        assert started_item.started_at is not None

    complete_response = client.post(
        f"/api/h5/tasks/packages/{seeded['package_id']}/current-product/complete"
    )
    assert complete_response.status_code == 200, complete_response.text
    assert complete_response.json()["taskPackage"]["id"] == seeded["package_id"]
    assert complete_response.json()["taskPackage"]["currentItem"]["id"] == seeded["item_b_id"]
    assert complete_response.json()["taskPackage"]["currentItemIndex"] == 2


def test_h5_task_package_list_routes_support_status_filter(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-h5-task-alias-filter", site_key="h5-task-alias-filter")
    auth_payload = _register_member(
        client,
        site_key="h5-task-alias-filter",
        phone="+86139000999994",
        display_name="Alias Filter Member",
    )
    public_user_id = auth_payload["member"]["publicUserId"]
    _mark_h5_member_whatsapp_bound(db_session_factory, public_user_id=public_user_id)
    seeded = _seed_task_package_scope(
        db_session_factory,
        account_id="acct-h5-task-alias-filter",
        site_id=site["id"],
        public_user_id=public_user_id,
        system_balance=Decimal("500.00"),
        task_balance=Decimal("50.00"),
    )

    pending_alias = client.get("/api/h5/tasks/packages", params={"status": "pending_claim"})
    pending_legacy = client.get("/api/h5/task-packages", params={"status": "pending_claim"})
    assert pending_alias.status_code == 200, pending_alias.text
    assert pending_legacy.status_code == 200, pending_legacy.text
    assert len(pending_alias.json()) == 1
    assert pending_alias.json() == pending_legacy.json()

    active_before_claim = client.get("/api/h5/tasks/packages", params={"status": "active"})
    assert active_before_claim.status_code == 200, active_before_claim.text
    assert active_before_claim.json() == []

    claim_response = client.post(f"/api/h5/tasks/packages/{seeded['package_id']}/claim")
    assert claim_response.status_code == 200, claim_response.text

    active_alias = client.get("/api/h5/tasks/packages", params={"status": "active"})
    active_legacy = client.get("/api/h5/task-packages", params={"status": "active"})
    assert active_alias.status_code == 200, active_alias.text
    assert active_legacy.status_code == 200, active_legacy.text
    assert len(active_alias.json()) == 1
    assert active_alias.json() == active_legacy.json()


def test_h5_task_package_purchase_rejects_non_current_item(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-h5-task-order-guard", site_key="h5-task-order-guard")
    auth_payload = _register_member(
        client,
        site_key="h5-task-order-guard",
        phone="+86139000999995",
        display_name="Alias Order Guard Member",
    )
    public_user_id = auth_payload["member"]["publicUserId"]
    _mark_h5_member_whatsapp_bound(db_session_factory, public_user_id=public_user_id)
    seeded = _seed_task_package_scope(
        db_session_factory,
        account_id="acct-h5-task-order-guard",
        site_id=site["id"],
        public_user_id=public_user_id,
        system_balance=Decimal("500.00"),
        task_balance=Decimal("50.00"),
    )

    claim_response = client.post(f"/api/h5/tasks/packages/{seeded['package_id']}/claim")
    assert claim_response.status_code == 200, claim_response.text

    out_of_order_purchase = client.post(
        f"/api/h5/task-packages/{seeded['package_id']}/items/{seeded['item_b_id']}/purchase"
    )
    assert out_of_order_purchase.status_code == 200, out_of_order_purchase.text
    payload = out_of_order_purchase.json()
    assert payload["success"] is False
    assert payload["reason"] == "Only the current product can be completed."
    assert payload["taskPackage"]["currentItem"]["id"] == seeded["item_a_id"]


def test_h5_task_package_complete_alias_returns_explicit_no_current_product_payload_when_package_is_finished(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-h5-task-alias-finished", site_key="h5-task-alias-finished")
    auth_payload = _register_member(
        client,
        site_key="h5-task-alias-finished",
        phone="+86139000999993",
        display_name="Alias Finished Member",
    )
    public_user_id = auth_payload["member"]["publicUserId"]
    _mark_h5_member_whatsapp_bound(db_session_factory, public_user_id=public_user_id)
    seeded = _seed_task_package_scope(
        db_session_factory,
        account_id="acct-h5-task-alias-finished",
        site_id=site["id"],
        public_user_id=public_user_id,
        system_balance=Decimal("500.00"),
        task_balance=Decimal("50.00"),
    )

    claim_response = client.post(f"/api/h5/tasks/packages/{seeded['package_id']}/claim")
    assert claim_response.status_code == 200, claim_response.text

    first_complete = client.post(
        f"/api/h5/tasks/packages/{seeded['package_id']}/current-product/complete"
    )
    assert first_complete.status_code == 200, first_complete.text
    second_complete = client.post(
        f"/api/h5/tasks/packages/{seeded['package_id']}/current-product/complete"
    )
    assert second_complete.status_code == 200, second_complete.text

    finished_complete = client.post(
        f"/api/h5/tasks/packages/{seeded['package_id']}/current-product/complete"
    )
    assert finished_complete.status_code == 200, finished_complete.text
    payload = finished_complete.json()
    assert payload["success"] is False
    assert payload["reason"] == "No current product is available for completion."
    assert payload["taskPackage"]["id"] == seeded["package_id"]
    assert payload["taskPackage"]["status"] == "completed"
    assert payload["taskPackage"]["currentItem"] is None
    assert payload["wallet"]["systemBalance"] == 450.0
    assert payload["wallet"]["taskBalance"] == 60.0


def test_h5_task_balance_transfer_spec_alias_matches_existing_wallet_transfer(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _create_site(client, account_id="acct-h5-transfer-alias", site_key="h5-transfer-alias")
    auth_payload = _register_member(
        client,
        site_key="h5-transfer-alias",
        phone="+86139000999992",
        display_name="Transfer Alias Member",
    )
    public_user_id = auth_payload["member"]["publicUserId"]
    _mark_h5_member_whatsapp_bound(db_session_factory, public_user_id=public_user_id)
    _seed_member_wallet(
        db_session_factory,
        account_id="acct-h5-transfer-alias",
        public_user_id=public_user_id,
        system_balance=Decimal("0.00"),
        task_balance=Decimal("60.00"),
    )

    response = client.post(
        "/api/h5/wallet/task-balance/transfer",
        json={"amount": "25.00"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["taskBalance"] == 35.0
    assert payload["systemBalance"] == 25.0
