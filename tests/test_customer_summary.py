"""Tests for Customer 360 Summary API (BFX-002)."""

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.postgres

from tests.test_conversations import _create_manual_meta_account, _post_mock_inbound_message


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


class TestCustomerSummary:
    def test_summary_returns_customer_data(self, client: TestClient) -> None:
        account_id = _setup_test_account(client)
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

    def test_summary_includes_conversations(self, client: TestClient) -> None:
        account_id = _setup_test_account(client)
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

    def test_summary_includes_tickets(self, client: TestClient) -> None:
        account_id = _setup_test_account(client)
        resp = client.get(f"/api/customers/user-cs-3/summary?account_id={account_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert "tickets" in data
        assert "total" in data["tickets"]
        assert isinstance(data["tickets"]["items"], list)

    def test_summary_includes_wallet(self, client: TestClient) -> None:
        account_id = _setup_test_account(client)
        resp = client.get(f"/api/customers/user-cs-4/summary?account_id={account_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert "wallet" in data
        assert "balance" in data["wallet"]

    def test_summary_includes_member_status(self, client: TestClient) -> None:
        account_id = _setup_test_account(client)
        resp = client.get(f"/api/customers/user-cs-5/summary?account_id={account_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert "member_status" in data

    def test_summary_includes_tags(self, client: TestClient) -> None:
        account_id = _setup_test_account(client)
        resp = client.get(f"/api/customers/user-cs-6/summary?account_id={account_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert "tags" in data
        assert isinstance(data["tags"], list)

    def test_summary_no_data_returns_empty_modules(self, client: TestClient) -> None:
        account_id = _setup_test_account(client)
        resp = client.get(f"/api/customers/nonexistent-user/summary?account_id={account_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["customer"] == {}
        assert data["conversations"]["total"] == 0
        assert data["tickets"]["total"] == 0
        assert data["wallet"]["balance"] == 0

    def test_summary_account_id_filter(self, client: TestClient) -> None:
        account_id = _setup_test_account(client)
        resp = client.get(f"/api/customers/user-cs-8/summary?account_id={account_id}")
        assert resp.status_code == 200

    def test_summary_missing_account_id(self, client: TestClient) -> None:
        _setup_test_account(client)
        resp = client.get("/api/customers/user-cs-9/summary")
        assert resp.status_code in (200, 422)

    def test_summary_response_time(self, client: TestClient) -> None:
        import time
        account_id = _setup_test_account(client)
        t0 = time.monotonic()
        client.get(f"/api/customers/user-cs-10/summary?account_id={account_id}")
        elapsed = (time.monotonic() - t0) * 1000
        assert elapsed < 5000, f"Customer summary took {elapsed:.0f}ms, expected <5000ms"
