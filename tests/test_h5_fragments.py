from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import (
    AppUser,
    FragmentDefinition,
    FragmentInventory,
    MailingRequest,
    MemberProfile,
)
from tests.test_h5_member_auth import _create_site, _register_member
from tests.test_h5_task_packages_wallet import _seed_task_package_scope


def _seed_fragment_balance(
    db_session_factory: sessionmaker[Session],
    *,
    account_id: str,
    public_user_id: str,
    fragment_key: str,
    fragment_name: str,
    rarity: str,
    color: str,
    owned_count: int,
    required_count: int = 1,
) -> None:
    with db_session_factory() as session:
        user = session.query(AppUser).filter(AppUser.public_user_id == public_user_id).one()
        member_profile = session.query(MemberProfile).filter(MemberProfile.user_id == user.id).one()
        definition = session.query(FragmentDefinition).filter(
            FragmentDefinition.account_id == account_id,
            FragmentDefinition.fragment_key == fragment_key,
        ).first()
        if definition is None:
            definition = FragmentDefinition(
                account_id=account_id,
                fragment_key=fragment_key,
                name=fragment_name,
                rarity=rarity,
                color=color,
                required_count=required_count,
                reward_name="Star Ring Gift Box",
                status="active",
            )
            session.add(definition)
            session.flush()

        inventory = session.query(FragmentInventory).filter(
            FragmentInventory.account_id == account_id,
            FragmentInventory.user_id == user.id,
            FragmentInventory.fragment_definition_id == definition.id,
        ).first()
        if inventory is None:
            inventory = FragmentInventory(
                account_id=account_id,
                user_id=user.id,
                member_profile_id=member_profile.id,
                fragment_definition_id=definition.id,
                owned_count=owned_count,
            )
            session.add(inventory)
        else:
            inventory.owned_count = owned_count
            session.add(inventory)
        session.commit()


def test_h5_fragments_overview_and_checkin_flow(
    client: TestClient,
) -> None:
    _create_site(client, account_id="acct-h5-fragments", site_key="h5-fragments")
    _register_member(
        client,
        site_key="h5-fragments",
        phone="+8613900050505",
        display_name="Fragment Member",
    )

    overview_response = client.get("/api/h5/fragments")
    assert overview_response.status_code == 200, overview_response.text
    overview = overview_response.json()
    assert overview["rewardName"] == "Star Ring Gift Box"
    assert len(overview["inventory"]) == 3
    assert overview["dropLogs"] == []
    assert overview["shippingOrders"] == []

    checkin_response = client.post("/api/h5/fragments/check-in")
    assert checkin_response.status_code == 200, checkin_response.text
    checked_in = checkin_response.json()
    assert len(checked_in["dropLogs"]) == 1
    assert checked_in["dropLogs"][0]["source"] == "checkin"
    assert sum(item["owned"] for item in checked_in["inventory"]) == 1

    repeated_response = client.post("/api/h5/fragments/check-in")
    assert repeated_response.status_code == 409, repeated_response.text
    assert "already checked in" in str(repeated_response.json()["detail"]).lower()


def test_h5_completed_task_package_awards_fragment_drop(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-h5-fragment-task", site_key="h5-fragment-task")
    auth_payload = _register_member(
        client,
        site_key="h5-fragment-task",
        phone="+8613900050506",
        display_name="Fragment Task Member",
    )
    seeded = _seed_task_package_scope(
        db_session_factory,
        account_id="acct-h5-fragment-task",
        site_id=site["id"],
        public_user_id=auth_payload["member"]["publicUserId"],
        system_balance=Decimal("120"),
        task_balance=Decimal("0"),
    )

    claim_response = client.post(f"/api/h5/task-packages/{seeded['package_id']}/claim")
    assert claim_response.status_code == 200, claim_response.text

    first_purchase = client.post(
        f"/api/h5/task-packages/{seeded['package_id']}/items/{seeded['item_a_id']}/purchase"
    )
    assert first_purchase.status_code == 200, first_purchase.text
    assert first_purchase.json()["success"] is True
    assert first_purchase.json().get("fragmentDrop") is None

    second_purchase = client.post(
        f"/api/h5/task-packages/{seeded['package_id']}/items/{seeded['item_b_id']}/purchase"
    )
    assert second_purchase.status_code == 200, second_purchase.text
    assert second_purchase.json()["success"] is True
    assert second_purchase.json()["fragmentDrop"] is not None
    assert second_purchase.json()["fragmentDrop"]["source"] == "task"

    overview_response = client.get("/api/h5/fragments")
    assert overview_response.status_code == 200, overview_response.text
    overview = overview_response.json()
    assert len(overview["dropLogs"]) == 1
    assert overview["dropLogs"][0]["source"] == "task"
    assert sum(item["owned"] for item in overview["inventory"]) == 1


def test_h5_fragment_exchange_creates_shipping_request_and_debits_inventory(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _create_site(client, account_id="acct-h5-fragment-exchange", site_key="h5-fragment-exchange")
    auth_payload = _register_member(
        client,
        site_key="h5-fragment-exchange",
        phone="+8613900050507",
        display_name="Fragment Exchange Member",
    )
    public_user_id = auth_payload["member"]["publicUserId"]

    _seed_fragment_balance(
        db_session_factory,
        account_id="acct-h5-fragment-exchange",
        public_user_id=public_user_id,
        fragment_key="fragment-sun",
        fragment_name="Star Core Fragment",
        rarity="common",
        color="#f59e0b",
        owned_count=1,
    )
    _seed_fragment_balance(
        db_session_factory,
        account_id="acct-h5-fragment-exchange",
        public_user_id=public_user_id,
        fragment_key="fragment-moon",
        fragment_name="Moon Glow Fragment",
        rarity="rare",
        color="#6366f1",
        owned_count=1,
    )
    _seed_fragment_balance(
        db_session_factory,
        account_id="acct-h5-fragment-exchange",
        public_user_id=public_user_id,
        fragment_key="fragment-star",
        fragment_name="Star Ray Fragment",
        rarity="epic",
        color="#ef4444",
        owned_count=1,
    )

    exchange_response = client.post(
        "/api/h5/fragments/exchanges",
        json={
            "receiver": "Demo User",
            "phone": "13800000000",
            "country": "China",
            "province": "Guangdong",
            "city": "Shenzhen",
            "addressLine": "Nanshan Science Park",
        },
    )
    assert exchange_response.status_code == 200, exchange_response.text
    overview = exchange_response.json()
    assert overview["shippingOrders"][0]["status"] == "submitted"
    assert overview["shippingOrders"][0]["address"]["receiver"] == "Demo User"
    assert all(item["owned"] == 0 for item in overview["inventory"])

    list_shipping_response = client.get("/api/h5/rewards/shipping")
    assert list_shipping_response.status_code == 200, list_shipping_response.text
    shipping_orders = list_shipping_response.json()
    assert len(shipping_orders) == 1
    assert shipping_orders[0]["status"] == "submitted"

    with db_session_factory() as session:
        shipping_request = session.query(MailingRequest).filter(
            MailingRequest.account_id == "acct-h5-fragment-exchange"
        ).one()
        assert shipping_request.receiver == "Demo User"
        assert shipping_request.city == "Shenzhen"


def test_h5_member_home_includes_fragment_shipping_summary(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _create_site(
        client,
        account_id="acct-h5-fragment-home",
        site_key="h5-fragment-home",
    )
    auth_payload = _register_member(
        client,
        site_key="h5-fragment-home",
        phone="+8613900050508",
        display_name="Fragment Home Member",
    )
    public_user_id = auth_payload["member"]["publicUserId"]

    _seed_fragment_balance(
        db_session_factory,
        account_id="acct-h5-fragment-home",
        public_user_id=public_user_id,
        fragment_key="fragment-sun",
        fragment_name="Star Core Fragment",
        rarity="common",
        color="#f59e0b",
        owned_count=1,
    )
    _seed_fragment_balance(
        db_session_factory,
        account_id="acct-h5-fragment-home",
        public_user_id=public_user_id,
        fragment_key="fragment-moon",
        fragment_name="Moon Glow Fragment",
        rarity="rare",
        color="#6366f1",
        owned_count=1,
    )
    _seed_fragment_balance(
        db_session_factory,
        account_id="acct-h5-fragment-home",
        public_user_id=public_user_id,
        fragment_key="fragment-star",
        fragment_name="Star Ray Fragment",
        rarity="epic",
        color="#ef4444",
        owned_count=1,
    )

    ready_home_response = client.get("/api/h5/member/home")
    assert ready_home_response.status_code == 200, ready_home_response.text
    ready_home = ready_home_response.json()
    assert ready_home["fragments"]["rewardName"] == "Star Ring Gift Box"
    assert ready_home["fragments"]["completedCount"] == 3
    assert ready_home["fragments"]["totalCount"] == 3
    assert ready_home["fragments"]["missingCount"] == 0
    assert ready_home["fragments"]["canExchange"] is True
    assert ready_home["fragments"]["shippingOrderCount"] == 0
    assert ready_home["fragments"]["latestShippingStatus"] is None

    exchange_response = client.post(
        "/api/h5/fragments/exchanges",
        json={
            "receiver": "Demo User",
            "phone": "13800000000",
            "country": "China",
            "province": "Guangdong",
            "city": "Shenzhen",
            "addressLine": "Nanshan Science Park",
        },
    )
    assert exchange_response.status_code == 200, exchange_response.text

    exchanged_home_response = client.get("/api/h5/member/home")
    assert exchanged_home_response.status_code == 200, exchanged_home_response.text
    exchanged_home = exchanged_home_response.json()
    assert exchanged_home["fragments"]["rewardName"] == "Star Ring Gift Box"
    assert exchanged_home["fragments"]["completedCount"] == 0
    assert exchanged_home["fragments"]["totalCount"] == 3
    assert exchanged_home["fragments"]["missingCount"] == 3
    assert exchanged_home["fragments"]["canExchange"] is False
    assert exchanged_home["fragments"]["shippingOrderCount"] == 1
    assert exchanged_home["fragments"]["latestShippingStatus"] == "submitted"
