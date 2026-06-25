from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import WithdrawalRequest, utc_now
from tests.test_h5_fragments import _seed_fragment_balance
from tests.test_h5_member_auth import _create_site, _register_member
from tests.test_h5_member_messages import _seed_member_notification
from tests.test_h5_task_packages_wallet import _seed_task_package_scope


def test_h5_member_auth_and_home_emit_camelcase_fields(client: TestClient) -> None:
    _create_site(client, account_id="acct-h5-camel-auth", site_key="h5-camel-auth")

    register_payload = _register_member(
        client,
        site_key="h5-camel-auth",
        phone="+8613900081001",
        display_name="Camel Auth Member",
    )
    member = register_payload["member"]
    assert "publicUserId" in member
    assert "memberNo" in member
    assert "siteKey" in member
    assert "displayName" in member
    assert "createdAt" in member

    me_response = client.get("/api/h5/auth/me")
    assert me_response.status_code == 200, me_response.text
    me_payload = me_response.json()
    assert "refreshExpiresAt" in me_payload["session"]
    assert "siteKey" in me_payload["site"]

    home_response = client.get("/api/h5/member/home")
    assert home_response.status_code == 200, home_response.text
    home_payload = home_response.json()
    assert "openTicketCount" in home_payload
    assert "unreadMessageCount" in home_payload
    assert "pendingClaimCount" in home_payload
    assert "taskSummary" in home_payload
    assert "pendingReview" in home_payload["taskSummary"]
    assert "systemBalance" in home_payload["wallet"]
    assert "accountIdMasked" in home_payload["member"]
    assert "inviteCode" in home_payload["member"]
    assert "verification" in home_payload
    assert "currentStatus" in home_payload["verification"]
    assert "hasActiveRequest" in home_payload["verification"]
    assert "fragments" in home_payload
    assert "rewardName" in home_payload["fragments"]
    assert "completedCount" in home_payload["fragments"]
    assert "totalCount" in home_payload["fragments"]
    assert "missingCount" in home_payload["fragments"]
    assert "canExchange" in home_payload["fragments"]
    assert "shippingOrderCount" in home_payload["fragments"]
    assert "latestShippingStatus" in home_payload["fragments"]
    assert "recentMessages" in home_payload
    assert "leaderboard" in home_payload


def test_h5_member_commerce_emit_camelcase_fields(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-h5-camel-commerce", site_key="h5-camel-commerce")
    auth_payload = _register_member(
        client,
        site_key="h5-camel-commerce",
        phone="+8613900081002",
        display_name="Camel Commerce Member",
    )
    seeded = _seed_task_package_scope(
        db_session_factory,
        account_id="acct-h5-camel-commerce",
        site_id=site["id"],
        public_user_id=auth_payload["member"]["publicUserId"],
        system_balance=Decimal("100"),
    )

    packages_response = client.get("/api/h5/task-packages")
    assert packages_response.status_code == 200, packages_response.text
    package_payload = packages_response.json()[0]
    assert "rewardRatio" in package_payload
    assert "dispatchedAt" in package_payload
    assert "completionWindowHours" in package_payload
    assert "countdownSeconds" in package_payload

    claim_response = client.post(f"/api/h5/task-packages/{seeded['package_id']}/claim")
    assert claim_response.status_code == 200, claim_response.text
    claimed = claim_response.json()
    assert "claimedAt" in claimed
    assert "expiresAt" in claimed

    purchase_response = client.post(
        f"/api/h5/task-packages/{seeded['package_id']}/items/{seeded['item_a_id']}/purchase"
    )
    assert purchase_response.status_code == 200, purchase_response.text
    purchase_payload = purchase_response.json()
    assert "taskPackage" in purchase_payload
    assert "fragmentDrop" in purchase_payload or purchase_payload["fragmentDrop"] is None
    assert "systemBalance" in purchase_payload["wallet"]
    assert "taskBalance" in purchase_payload["wallet"]

    orders_response = client.get("/api/h5/orders")
    assert orders_response.status_code == 200, orders_response.text
    order = orders_response.json()[0]
    assert "orderNo" in order
    assert "packageId" in order
    assert "packageTitle" in order
    assert "productName" in order
    assert "createdAt" in order

    transactions_response = client.get("/api/h5/wallet/transactions")
    assert transactions_response.status_code == 200, transactions_response.text
    transaction = transactions_response.json()[0]
    assert "ledgerType" in transaction
    assert "transactionType" in transaction
    assert "displayCategory" in transaction
    assert "displayTitle" in transaction
    assert "createdAt" in transaction


def test_h5_member_fragments_and_messages_emit_camelcase_fields_and_accept_addressline(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-h5-camel-fragments", site_key="h5-camel-fragments")
    auth_payload = _register_member(
        client,
        site_key="h5-camel-fragments",
        phone="+8613900081003",
        display_name="Camel Fragment Member",
    )
    public_user_id = auth_payload["member"]["publicUserId"]

    _seed_member_notification(
        db_session_factory,
        account_id="acct-h5-camel-fragments",
        public_user_id=public_user_id,
        site_id=site["id"],
        category="wallet",
        title="Wallet notice",
        body_text="Camel case body",
        is_read=False,
    )
    _seed_fragment_balance(
        db_session_factory,
        account_id="acct-h5-camel-fragments",
        public_user_id=public_user_id,
        fragment_key="fragment-sun",
        fragment_name="Star Core Fragment",
        rarity="common",
        color="#f59e0b",
        owned_count=1,
    )
    _seed_fragment_balance(
        db_session_factory,
        account_id="acct-h5-camel-fragments",
        public_user_id=public_user_id,
        fragment_key="fragment-moon",
        fragment_name="Moon Glow Fragment",
        rarity="rare",
        color="#6366f1",
        owned_count=1,
    )
    _seed_fragment_balance(
        db_session_factory,
        account_id="acct-h5-camel-fragments",
        public_user_id=public_user_id,
        fragment_key="fragment-star",
        fragment_name="Star Ray Fragment",
        rarity="epic",
        color="#ef4444",
        owned_count=1,
    )

    messages_response = client.get("/api/h5/messages")
    assert messages_response.status_code == 200, messages_response.text
    message = messages_response.json()[0]
    assert "bodyText" in message
    assert "isRead" in message
    assert "createdAt" in message

    overview_response = client.get("/api/h5/fragments")
    assert overview_response.status_code == 200, overview_response.text
    overview = overview_response.json()
    assert "dropLogs" in overview
    assert "rewardName" in overview
    assert "shippingOrders" in overview

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
    shipping_order = exchange_response.json()["shippingOrders"][0]
    assert "rewardName" in shipping_order
    assert "createdAt" in shipping_order
    assert "addressLine" in shipping_order["address"]


def test_h5_member_home_includes_recent_messages_and_leaderboard_payload(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-h5-camel-home", site_key="h5-camel-home")
    auth_payload = _register_member(
        client,
        site_key="h5-camel-home",
        phone="+8613900081004",
        display_name="Camel Home Member",
    )
    public_user_id = auth_payload["member"]["publicUserId"]

    _seed_task_package_scope(
        db_session_factory,
        account_id="acct-h5-camel-home",
        site_id=site["id"],
        public_user_id=public_user_id,
        system_balance=Decimal("220"),
        task_balance=Decimal("40"),
    )
    _seed_member_notification(
        db_session_factory,
        account_id="acct-h5-camel-home",
        public_user_id=public_user_id,
        site_id=site["id"],
        category="wallet",
        title="Home wallet notice",
        body_text="Shown in recent messages.",
        is_read=False,
    )

    create_response = client.post("/api/h5/withdrawals", json={"amount": 120})
    assert create_response.status_code == 200, create_response.text

    with db_session_factory() as session:
        withdrawal = session.get(WithdrawalRequest, create_response.json()["id"])
        assert withdrawal is not None
        withdrawal.status = "paid"
        withdrawal.paid_at = utc_now()
        session.add(withdrawal)
        session.commit()

    home_response = client.get("/api/h5/member/home")
    assert home_response.status_code == 200, home_response.text
    payload = home_response.json()

    assert payload["member"]["accountIdMasked"]
    assert payload["member"]["inviteCode"]
    assert len(payload["recentMessages"]) >= 1
    assert any(item["title"] == "Home wallet notice" for item in payload["recentMessages"])
    assert any(item["bodyText"] == "Shown in recent messages." for item in payload["recentMessages"])
    assert len(payload["leaderboard"]) == 1
    assert payload["leaderboard"][0]["rank"] == 1
    assert payload["leaderboard"][0]["accountIdMasked"] == payload["member"]["accountIdMasked"]
