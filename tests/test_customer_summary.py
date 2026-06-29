"""Tests for Customer 360 Summary API (BFX-002)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

pytestmark = pytest.mark.postgres

from app.db.models import AppUser
from tests.test_conversations import _create_manual_meta_account, _post_mock_inbound_message
from tests.test_h5_member_auth import _create_site, _register_member


def _setup_test_account(client: TestClient) -> str:
    """Create a meta account with a phone number and return account_id."""
    account_id = "customer-summary-account"
    phone_numbers = [
        {
            "phone_number_id": "pn-cs-1",
            "display_phone_number": "+1 555 000 0001",
            "verified_name": "CS Test",
            "quality_rating": "GREEN",
            "is_registered": True,
        }
    ]
    _create_manual_meta_account(
        client,
        account_id=account_id,
        portfolio_id="portfolio-cs-1",
        waba_id="waba-cs-1",
        phone_numbers=phone_numbers,
    )
    return account_id


def _seed_customer(
    db_session_factory: sessionmaker[Session],
    *,
    account_id: str,
    customer_id: str,
    display_name: str | None = None,
) -> None:
    with db_session_factory() as session:
        session.add(
            AppUser(
                id=customer_id,
                account_id=account_id,
                public_user_id=customer_id,
                display_name=display_name or customer_id,
            )
        )
        session.commit()


class TestCustomerSummary:
    def test_summary_returns_customer_data(
        self,
        client: TestClient,
        db_session_factory: sessionmaker[Session],
    ) -> None:
        account_id = _setup_test_account(client)
        _seed_customer(db_session_factory, account_id=account_id, customer_id="user-cs-1")
        _post_mock_inbound_message(
            client,
            account_id=account_id,
            conversation_id="conv-cs-1",
            user_id="user-cs-1",
            text="Hello, I need help",
        )
        resp = client.get(f"/api/customers/user-cs-1/summary?account_id={account_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert "customer" in data

    def test_summary_includes_conversations(
        self,
        client: TestClient,
        db_session_factory: sessionmaker[Session],
    ) -> None:
        account_id = _setup_test_account(client)
        _seed_customer(db_session_factory, account_id=account_id, customer_id="user-cs-2")
        _post_mock_inbound_message(
            client,
            account_id=account_id,
            conversation_id="conv-cs-2",
            user_id="user-cs-2",
            text="Test conversation",
        )
        resp = client.get(f"/api/customers/user-cs-2/summary?account_id={account_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert "conversations" in data
        assert data["conversations"]["total"] >= 0
        assert isinstance(data["conversations"]["items"], list)

    def test_summary_includes_tickets(
        self,
        client: TestClient,
        db_session_factory: sessionmaker[Session],
    ) -> None:
        account_id = _setup_test_account(client)
        _seed_customer(db_session_factory, account_id=account_id, customer_id="user-cs-3")
        resp = client.get(f"/api/customers/user-cs-3/summary?account_id={account_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert "tickets" in data
        assert "total" in data["tickets"]
        assert isinstance(data["tickets"]["items"], list)

    def test_summary_includes_wallet(
        self,
        client: TestClient,
        db_session_factory: sessionmaker[Session],
    ) -> None:
        account_id = _setup_test_account(client)
        _seed_customer(db_session_factory, account_id=account_id, customer_id="user-cs-4")
        resp = client.get(f"/api/customers/user-cs-4/summary?account_id={account_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert "wallet" in data
        assert "balance" in data["wallet"]
        assert "system_balance" in data["wallet"]
        assert "task_balance" in data["wallet"]

    def test_summary_includes_member_status(
        self,
        client: TestClient,
        db_session_factory: sessionmaker[Session],
    ) -> None:
        account_id = _setup_test_account(client)
        _seed_customer(db_session_factory, account_id=account_id, customer_id="user-cs-5")
        resp = client.get(f"/api/customers/user-cs-5/summary?account_id={account_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert "member_status" in data

    def test_summary_includes_tags(
        self,
        client: TestClient,
        db_session_factory: sessionmaker[Session],
    ) -> None:
        account_id = _setup_test_account(client)
        _seed_customer(db_session_factory, account_id=account_id, customer_id="user-cs-6")
        resp = client.get(f"/api/customers/user-cs-6/summary?account_id={account_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert "tags" in data
        assert isinstance(data["tags"], list)

    def test_summary_no_data_returns_empty_modules(
        self,
        client: TestClient,
        db_session_factory: sessionmaker[Session],
    ) -> None:
        account_id = _setup_test_account(client)
        _seed_customer(db_session_factory, account_id=account_id, customer_id="user-cs-empty")
        resp = client.get(f"/api/customers/user-cs-empty/summary?account_id={account_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["customer"]["id"] == "user-cs-empty"
        assert data["conversations"]["total"] == 0
        assert data["tickets"]["total"] == 0
        assert data["wallet"]["balance"] == 0

    def test_summary_account_id_filter(
        self,
        client: TestClient,
        db_session_factory: sessionmaker[Session],
    ) -> None:
        account_id = _setup_test_account(client)
        _seed_customer(db_session_factory, account_id=account_id, customer_id="user-cs-8")
        resp = client.get(f"/api/customers/user-cs-8/summary?account_id={account_id}")
        assert resp.status_code == 200

    def test_summary_missing_account_id(
        self,
        client: TestClient,
        db_session_factory: sessionmaker[Session],
    ) -> None:
        account_id = _setup_test_account(client)
        _seed_customer(db_session_factory, account_id=account_id, customer_id="user-cs-9")
        resp = client.get("/api/customers/user-cs-9/summary")
        assert resp.status_code in (200, 422)

    def test_summary_response_time(
        self,
        client: TestClient,
        db_session_factory: sessionmaker[Session],
    ) -> None:
        import time
        account_id = _setup_test_account(client)
        _seed_customer(db_session_factory, account_id=account_id, customer_id="user-cs-10")
        t0 = time.monotonic()
        client.get(f"/api/customers/user-cs-10/summary?account_id={account_id}")
        elapsed = (time.monotonic() - t0) * 1000
        assert elapsed < 5000, f"Customer summary took {elapsed:.0f}ms, expected <5000ms"

    def test_summary_includes_same_ip_user_count(
        self,
        client: TestClient,
        db_session_factory: sessionmaker[Session],
    ) -> None:
        account_id = "customer-summary-ip-account"
        _create_site(client, account_id=account_id, site_key="customer-summary-ip")
        auth_a = _register_member(
            client,
            site_key="customer-summary-ip",
            phone="+8613900067991",
            display_name="IP Count A",
        )
        _register_member(
            client,
            site_key="customer-summary-ip",
            phone="+8613900067992",
            display_name="IP Count B",
        )

        with db_session_factory() as session:
            user_a = session.get(AppUser, auth_a["member"]["userId"])
            assert user_a is not None
            user_a.registration_ip = "172.18.0.1"
            sibling = (
                session.query(AppUser)
                .filter(
                    AppUser.account_id == account_id,
                    AppUser.id != auth_a["member"]["userId"],
                )
                .first()
            )
            assert sibling is not None
            sibling.registration_ip = "172.18.0.1"
            session.commit()

        resp = client.get(f"/api/customers/{auth_a['member']['userId']}/summary?account_id={account_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["customer"]["same_ip_user_count"] == 2
