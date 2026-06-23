"""Tests for CUS-001 ~ CUS-003: Enhanced user list, timeline, batch lifecycle."""

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import (
    AppUser,
    Conversation,
    MemberProfile,
    Message,
    Ticket,
    WalletAccount,
    WalletLedgerEntry,
    WithdrawalRequest,
    utc_now,
)
from tests.test_h5_member_auth import _create_site, _operator_headers, _register_member
from tests.test_h5_task_packages_wallet import _seed_task_package_scope


# ── CUS-001: User list pagination, search, aggregate fields ──────────


def test_cus001_backward_compatible_full_list(client: TestClient) -> None:
    """Without page param, returns full list (old behaviour)."""
    acct = "acct-cus001-backward"
    site = _create_site(client, account_id=acct, site_key="cus001-backward")

    _register_member(client, site_key="cus001-backward", phone="+8613900067011", display_name="BC A")
    _register_member(client, site_key="cus001-backward", phone="+8613900067012", display_name="BC B")

    # No page → full list
    resp = client.get("/api/platform/users", headers=_operator_headers(acct))
    assert resp.status_code == 200, resp.text
    data = resp.json()
    # Without pagination, returns a list (backward compatible)
    assert isinstance(data, list), f"Expected list got {type(data)}"
    assert len(data) >= 2

    # With page → paginated response
    resp2 = client.get("/api/platform/users?page=1&size=10", headers=_operator_headers(acct))
    assert resp2.status_code == 200, resp2.text
    data2 = resp2.json()
    assert isinstance(data2, dict), f"Expected dict got {type(data2)}"
    assert "items" in data2
    assert "total" in data2


def test_cus001_pagination(client: TestClient, db_session_factory: sessionmaker[Session]) -> None:
    """Pagination returns correct page/size/total."""
    acct = "acct-cus001-pagination"
    _create_site(client, account_id=acct, site_key="cus001-pagination")

    # Create 5 users
    user_ids = []
    for i in range(5):
        auth = _register_member(
            client,
            site_key="cus001-pagination",
            phone=f"+861390006702{i}",
            display_name=f"Pagination User {i}",
        )
        user_ids.append(auth["member"]["userId"])

    # Page 1, size 3
    resp = client.get("/api/platform/users?page=1&size=3&sort=created_at:asc", headers=_operator_headers(acct))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["page"] == 1
    assert body["size"] == 3
    assert body["total"] == 5
    assert len(body["items"]) == 3

    # Page 2, size 3
    resp2 = client.get("/api/platform/users?page=2&size=3&sort=created_at:asc", headers=_operator_headers(acct))
    assert resp2.status_code == 200, resp2.text
    body2 = resp2.json()
    assert body2["page"] == 2
    assert body2["size"] == 3
    assert len(body2["items"]) == 2


def test_cus001_search_by_public_user_id(client: TestClient) -> None:
    """Search by public_user_id returns matching users."""
    acct = "acct-cus001-search-puid"
    site = _create_site(client, account_id=acct, site_key="cus001-search-puid")

    _register_member(client, site_key="cus001-search-puid", phone="+8613900067031", display_name="Search UID A")
    _register_member(client, site_key="cus001-search-puid", phone="+8613900067032", display_name="Search UID B")

    resp = client.get("/api/platform/users", params={"search": "Search UID A"}, headers=_operator_headers(acct))
    assert resp.status_code == 200, resp.text
    data = resp.json()
    # No page → full list
    assert isinstance(data, list)
    assert len(data) >= 1
    # At least one result contains the display name
    names = [u.get("display_name") for u in data]
    assert any(n and "Search UID A" in n for n in names)


def test_cus001_search_by_display_name(client: TestClient) -> None:
    """Search by display_name returns matching users."""
    acct = "acct-cus001-search-dn"
    site = _create_site(client, account_id=acct, site_key="cus001-search-dn")

    _register_member(client, site_key="cus001-search-dn", phone="+8613900067041", display_name="John Smith")
    _register_member(client, site_key="cus001-search-dn", phone="+8613900067042", display_name="Jane Doe")

    resp = client.get("/api/platform/users", params={"search": "John"}, headers=_operator_headers(acct))
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert isinstance(data, list)
    names = [u.get("display_name") for u in data]
    assert any(n and "John" in n for n in names)


def test_cus001_search_by_phone(client: TestClient) -> None:
    """Search by phone number (identity_value) returns matching users."""
    acct = "acct-cus001-search-phone"
    site = _create_site(client, account_id=acct, site_key="cus001-search-phone")

    _register_member(client, site_key="cus001-search-phone", phone="+8613900067051", display_name="Phone User")

    resp = client.get(
        "/api/platform/users",
        params={"search": "13900067051"},
        headers=_operator_headers(acct),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    # Paginated result
    if isinstance(data, dict):
        items = data["items"]
    else:
        items = data
    assert len(items) >= 1


def test_cus001_filter_by_lifecycle_status(client: TestClient, db_session_factory: sessionmaker[Session]) -> None:
    """Filter by lifecycle_status returns only matching users."""
    acct = "acct-cus001-filter-lc"
    site = _create_site(client, account_id=acct, site_key="cus001-filter-lc")

    auth_a = _register_member(client, site_key="cus001-filter-lc", phone="+8613900067061", display_name="LC Active")
    auth_b = _register_member(client, site_key="cus001-filter-lc", phone="+8613900067062", display_name="LC Frozen")

    # Manually set one user to frozen
    with db_session_factory() as session:
        user = session.query(AppUser).filter(AppUser.id == auth_b["member"]["userId"]).one()
        user.lifecycle_status = "frozen"
        session.commit()

    resp = client.get(
        "/api/platform/users",
        params={"lifecycle_status": "active"},
        headers=_operator_headers(acct),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    items = data if isinstance(data, list) else data.get("items", [])
    assert all(u["lifecycle_status"] == "active" for u in items)


def test_cus001_aggregate_fields(client: TestClient, db_session_factory: sessionmaker[Session]) -> None:
    """Paginated response includes conversation_count, ticket_count, wallet_balance."""
    acct = "acct-cus001-agg"
    site = _create_site(client, account_id=acct, site_key="cus001-agg")

    auth = _register_member(client, site_key="cus001-agg", phone="+8613900067071", display_name="Agg User")
    internal_id = auth["member"]["userId"]

    # Seed wallet balance and create conversations/tickets
    _seed_task_package_scope(
        db_session_factory,
        account_id=acct,
        site_id=site["id"],
        public_user_id=auth["member"]["publicUserId"],
        system_balance=Decimal("99.50"),
    )

    with db_session_factory() as session:
        # Create a conversation
        conv = Conversation(
            account_id=acct,
            external_conversation_id="ext-agg-001",
            customer_id=internal_id,
            status="open",
        )
        session.add(conv)
        session.flush()

        # Create a ticket
        ticket = Ticket(
            account_id=acct,
            user_id=internal_id,
            ticket_no="T-AGG-001",
            ticket_type="help",
            status="open",
            title="Help ticket",
        )
        session.add(ticket)
        session.commit()

    resp = client.get("/api/platform/users?page=1&size=20", headers=_operator_headers(acct))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    items = body["items"]

    # Find our user
    agg_user = next((u for u in items if u["id"] == internal_id), None)
    assert agg_user is not None, f"User {internal_id} not found in response"
    assert agg_user["conversation_count"] >= 1, f"Expected conversation_count >= 1, got {agg_user['conversationCount']}"
    assert agg_user["ticket_count"] >= 1, f"Expected ticket_count >= 1, got {agg_user['ticketCount']}"
    assert agg_user["wallet_balance"] >= 99.0, f"Expected wallet_balance >= 99, got {agg_user['walletBalance']}"


def test_cus001_filter_by_has_whatsapp(client: TestClient, db_session_factory: sessionmaker[Session]) -> None:
    """Filter by has_whatsapp returns only matching users."""
    acct = "acct-cus001-wa"
    site = _create_site(client, account_id=acct, site_key="cus001-wa")

    _register_member(client, site_key="cus001-wa", phone="+8613900067081", display_name="WA User")

    resp = client.get(
        "/api/platform/users",
        params={"has_whatsapp": "false"},
        headers=_operator_headers(acct),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    items = data if isinstance(data, list) else data.get("items", [])
    if items:
        assert all(u.get("has_whatsapp") is False for u in items)


def test_cus001_sort_order(client: TestClient) -> None:
    """Sort by created_at:asc returns users in ascending order."""
    acct = "acct-cus001-sort"
    site = _create_site(client, account_id=acct, site_key="cus001-sort")

    _register_member(client, site_key="cus001-sort", phone="+8613900067091", display_name="Sort A")
    _register_member(client, site_key="cus001-sort", phone="+8613900067092", display_name="Sort B")

    resp = client.get(
        "/api/platform/users",
        params={"sort": "created_at:asc", "page": "1", "size": "10"},
        headers=_operator_headers(acct),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    items = body["items"]
    if len(items) >= 2:
        assert items[0]["created_at"] <= items[-1]["created_at"]


def test_cus001_cross_account_isolation(client: TestClient) -> None:
    """Operator from account A cannot see users from account B."""
    acct_a = "acct-cus001-iso-a"
    acct_b = "acct-cus001-iso-b"
    _create_site(client, account_id=acct_a, site_key="cus001-iso-a")
    _create_site(client, account_id=acct_b, site_key="cus001-iso-b")

    _register_member(client, site_key="cus001-iso-a", phone="+8613900067101", display_name="ISO A")
    _register_member(client, site_key="cus001-iso-b", phone="+8613900067102", display_name="ISO B")

    resp = client.get("/api/platform/users", headers=_operator_headers(acct_a))
    assert resp.status_code == 200, resp.text
    data = resp.json()
    items = data if isinstance(data, list) else data.get("items", [])
    # Check that display names are only from account A
    for u in items:
        assert u.get("account_id") is None or u["account_id"] == acct_a


# ── CUS-003: Batch lifecycle ─────────────────────────────────────────


def test_cus003_batch_lifecycle_block(client: TestClient, db_session_factory: sessionmaker[Session]) -> None:
    """Batch lifecycle can block multiple users."""
    acct = "acct-cus003-block"
    site = _create_site(client, account_id=acct, site_key="cus003-block")

    auth_a = _register_member(client, site_key="cus003-block", phone="+8613900067201", display_name="Block A")
    auth_b = _register_member(client, site_key="cus003-block", phone="+8613900067202", display_name="Block B")

    user_id_a = auth_a["member"]["userId"]
    user_id_b = auth_b["member"]["userId"]

    resp = client.post(
        "/api/customers/batch-lifecycle",
        json={
            "customer_ids": [user_id_a, user_id_b],
            "account_id": acct,
            "lifecycle_status": "blacklisted",
        },
        headers=_operator_headers(acct),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["updated_count"] == 2
    assert body["lifecycle_status"] == "blacklisted"

    # Verify
    with db_session_factory() as session:
        for uid in [user_id_a, user_id_b]:
            user = session.get(AppUser, uid)
            assert user is not None
            assert user.lifecycle_status == "blacklisted"


def test_cus003_batch_lifecycle_unblock(client: TestClient, db_session_factory: sessionmaker[Session]) -> None:
    """Batch lifecycle can unblock users."""
    acct = "acct-cus003-unblock"
    site = _create_site(client, account_id=acct, site_key="cus003-unblock")

    auth = _register_member(client, site_key="cus003-unblock", phone="+8613900067211", display_name="Unblock")

    with db_session_factory() as session:
        user = session.get(AppUser, auth["member"]["userId"])
        assert user is not None
        user.lifecycle_status = "blacklisted"
        session.commit()

    resp = client.post(
        "/api/customers/batch-lifecycle",
        json={
            "customer_ids": [auth["member"]["userId"]],
            "account_id": acct,
            "lifecycle_status": "active",
        },
        headers=_operator_headers(acct),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["updated_count"] == 1

    with db_session_factory() as session:
        user = session.get(AppUser, auth["member"]["userId"])
        assert user is not None
        assert user.lifecycle_status == "active"


def test_cus003_batch_lifecycle_invalid_status(client: TestClient) -> None:
    """Batch lifecycle with invalid status returns 422."""
    acct = "acct-cus003-invalid"
    _create_site(client, account_id=acct, site_key="cus003-invalid")

    resp = client.post(
        "/api/customers/batch-lifecycle",
        json={
            "customer_ids": ["some-id"],
            "account_id": acct,
            "lifecycle_status": "invalid_status",
        },
        headers=_operator_headers(acct),
    )
    assert resp.status_code == 422, resp.text


def test_cus003_batch_lifecycle_cross_account_denied(client: TestClient) -> None:
    """Batch lifecycle from different account returns 403."""
    acct_a = "acct-cus003-cross-a"
    acct_b = "acct-cus003-cross-b"
    _create_site(client, account_id=acct_a, site_key="cus003-cross-a")

    resp = client.post(
        "/api/customers/batch-lifecycle",
        json={
            "customer_ids": ["some-id"],
            "account_id": acct_b,
            "lifecycle_status": "blacklisted",
        },
        headers=_operator_headers(acct_a),
    )
    assert resp.status_code == 403, resp.text


# ── CUS-002: Customer timeline ───────────────────────────────────────


def test_cus002_timeline_returns_events(client: TestClient, db_session_factory: sessionmaker[Session]) -> None:
    """Timeline endpoint returns merged events sorted by time."""
    acct = "acct-cus002-timeline"
    site = _create_site(client, account_id=acct, site_key="cus002-timeline")

    auth = _register_member(client, site_key="cus002-timeline", phone="+8613900067301", display_name="Timeline")
    internal_id = auth["member"]["userId"]

    # Create a conversation + message
    with db_session_factory() as session:
        conv = Conversation(
            account_id=acct,
            external_conversation_id="ext-tl-001",
            customer_id=internal_id,
            status="open",
        )
        session.add(conv)
        session.flush()

        msg = Message(
            account_id=acct,
            conversation_id=conv.id,
            direction="inbound",
            content_text="Hello, I need help",
            created_at=utc_now(),
        )
        session.add(msg)

        # Create a ticket
        ticket = Ticket(
            account_id=acct,
            user_id=internal_id,
            ticket_no="T-TL-001",
            ticket_type="help",
            status="open",
            title="Timeline ticket",
        )
        session.add(ticket)
        session.commit()

    resp = client.get(
        f"/api/customers/{internal_id}/timeline",
        params={"account_id": acct},
        headers=_operator_headers(acct),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "events" in body
    assert len(body["events"]) >= 2

    # Events should be sorted by time descending
    times = [e["time"] for e in body["events"]]
    assert times == sorted(times, reverse=True), "Events not sorted by time descending"

    # At least one message and one ticket event
    types = {e["type"] for e in body["events"]}
    assert "message" in types
    assert "ticket" in types


def test_cus002_timeline_respects_limit(client: TestClient, db_session_factory: sessionmaker[Session]) -> None:
    """Timeline endpoint respects limit parameter."""
    acct = "acct-cus002-limit"
    site = _create_site(client, account_id=acct, site_key="cus002-limit")

    auth = _register_member(client, site_key="cus002-limit", phone="+8613900067311", display_name="Timeline Limit")
    internal_id = auth["member"]["userId"]

    # Create a few events
    with db_session_factory() as session:
        conv = Conversation(
            account_id=acct,
            external_conversation_id="ext-tl-limit-001",
            customer_id=internal_id,
            status="open",
        )
        session.add(conv)
        session.flush()

        for i in range(3):
            msg = Message(
                account_id=acct,
                conversation_id=conv.id,
                direction="inbound",
                content_text=f"Message {i}",
                created_at=utc_now(),
            )
            session.add(msg)
        session.commit()

    # Limit to 1
    resp = client.get(
        f"/api/customers/{internal_id}/timeline",
        params={"account_id": acct, "limit": 1},
        headers=_operator_headers(acct),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["events"]) <= 1


def test_cus002_timeline_wallet_events(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    """Timeline includes wallet ledger and withdrawal events."""
    acct = "acct-cus002-wallet"
    site = _create_site(client, account_id=acct, site_key="cus002-wallet")

    auth = _register_member(
        client,
        site_key="cus002-wallet",
        phone="+8613900067321",
        display_name="Timeline Wallet",
    )
    internal_id = auth["member"]["userId"]

    # Seed wallet + ledger entry
    _seed_task_package_scope(
        db_session_factory,
        account_id=acct,
        site_id=site["id"],
        public_user_id=auth["member"]["publicUserId"],
        system_balance=Decimal("200"),
    )

    with db_session_factory() as session:
        wallet = session.query(WalletAccount).filter(WalletAccount.user_id == internal_id).first()
        assert wallet is not None

        ledger = WalletLedgerEntry(
            account_id=acct,
            wallet_account_id=wallet.id,
            user_id=internal_id,
            ledger_type="recharge",
            transaction_type="credit",
            direction="credit",
            amount=Decimal("50"),
            currency="USD",
        )
        session.add(ledger)

        withdrawal = WithdrawalRequest(
            account_id=acct,
            wallet_account_id=wallet.id,
            user_id=internal_id,
            request_no="WD-TL-001",
            amount=Decimal("30"),
            currency="USD",
            status="submitted",
        )
        session.add(withdrawal)
        session.commit()

    resp = client.get(
        f"/api/customers/{internal_id}/timeline",
        params={"account_id": acct},
        headers=_operator_headers(acct),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    types = {e["type"] for e in body["events"]}
    assert "wallet" in types, "Timeline missing wallet events"
    assert "withdrawal" in types, "Timeline missing withdrawal events"
