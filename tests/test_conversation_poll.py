"""Tests for conversation polling and SSE streaming (RT-001, RT-003)."""

import json
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from tests.test_conversations import _create_manual_meta_account, _post_mock_inbound_message

_ADMIN_HEADERS = {
    "X-Actor-Id": "rt-test-admin",
    "X-Actor-Role": "super_admin",
}

_OPERATOR_HEADERS = {
    "X-Actor-Id": "rt-test-operator",
    "X-Actor-Role": "operator",
    "X-Actor-Account-Ids": "rt-account-001",
}

_ACCOUNT_ID = "rt-account-001"
_PORTFOLIO_ID = "portfolio-rt-001"
_WABA_ID = "waba-rt-001"
_CONVERSATION_ID = "rt-conv-001"
_PHONE_NUMBER = {"phone_number_id": "pn-rt-001", "display_phone_number": "+8613800000001"}


class TestPollEndpoint:
    """RT-001: GET /api/conversations/poll"""

    def _setup_account(self, client: TestClient) -> None:
        """Create a manual meta account for testing."""
        _create_manual_meta_account(
            client,
            account_id=_ACCOUNT_ID,
            portfolio_id=_PORTFOLIO_ID,
            waba_id=_WABA_ID,
            phone_numbers=[_PHONE_NUMBER],
        )

    def test_poll_empty_when_no_events(self, client: TestClient) -> None:
        """Test 1: No new events → returns empty events list."""
        self._setup_account(client)
        since = (datetime.now(UTC) + timedelta(hours=1)).isoformat().replace("+00:00", "Z")
        resp = client.get(
            f"/api/conversations/poll?since={since}",
            headers=_ADMIN_HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["events"] == []
        assert "server_time" in data

    def test_poll_returns_new_messages(self, client: TestClient) -> None:
        """Test 2: Messages after since → events contains new_message."""
        self._setup_account(client)
        since = (datetime.now(UTC) - timedelta(hours=1)).isoformat().replace("+00:00", "Z")

        _post_mock_inbound_message(
            client,
            account_id=_ACCOUNT_ID,
            conversation_id=_CONVERSATION_ID,
            user_id="user-poll-1",
            text="Hello, I need help with my order",
            phone_number_id=_PHONE_NUMBER["phone_number_id"],
        )

        resp = client.get(
            f"/api/conversations/poll?since={since}",
            headers=_ADMIN_HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        events = data["events"]
        assert len(events) >= 1
        new_msg_events = [e for e in events if e["event"] == "new_message"]
        assert len(new_msg_events) >= 1
        assert new_msg_events[0]["account_id"] == _ACCOUNT_ID
        assert isinstance(new_msg_events[0]["conversation_id"], str)
        assert new_msg_events[0]["direction"] == "inbound"
        assert "order" in new_msg_events[0]["preview"]

    def test_poll_returns_handover_events(self, client: TestClient) -> None:
        """Test 3: Handover events → events contains handover."""
        self._setup_account(client)
        since = (datetime.now(UTC) - timedelta(hours=1)).isoformat().replace("+00:00", "Z")

        # Create a conversation via mock message
        _post_mock_inbound_message(
            client,
            account_id=_ACCOUNT_ID,
            conversation_id=_CONVERSATION_ID,
            user_id="user-poll-2",
            text="Talk to human",
            phone_number_id=_PHONE_NUMBER["phone_number_id"],
        )

        # Register an agent for handover
        reg_resp = client.post(
            "/api/runtime/agents",
            json={
                "agent_id": "rt-test-operator",
                "display_name": "RT Test Operator",
                "status": "online",
                "is_active": True,
            },
        )
        assert reg_resp.status_code == 200

        # Use _CONVERSATION_ID directly — runtime state uses external_conversation_id
        handover_since = (datetime.now(UTC)).isoformat().replace("+00:00", "Z")

        # Trigger a handover
        resp = client.post(
            f"/api/runtime/conversations/{_CONVERSATION_ID}/handover?account_id={_ACCOUNT_ID}",
            json={
                "management_mode": "human_managed",
                "agent_id": "rt-test-operator",
                "reason": "test_handover",
            },
            headers=_OPERATOR_HEADERS,
        )
        assert resp.status_code == 200, f"Handover failed: {resp.text}"

        resp = client.get(
            f"/api/conversations/poll?since={handover_since}",
            headers=_ADMIN_HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        events = data["events"]
        handover_events = [e for e in events if e["event"] == "handover"]
        assert len(handover_events) >= 1
        assert isinstance(handover_events[0]["conversation_id"], str)
        assert handover_events[0]["to_mode"] == "human_managed"

    def test_poll_account_id_filter(self, client: TestClient) -> None:
        """Test 4: account_id filter correctly scopes results."""
        self._setup_account(client)
        since = (datetime.now(UTC) - timedelta(hours=1)).isoformat().replace("+00:00", "Z")

        _post_mock_inbound_message(
            client,
            account_id=_ACCOUNT_ID,
            conversation_id=_CONVERSATION_ID,
            user_id="user-filter-1",
            text="Filter test message",
            phone_number_id=_PHONE_NUMBER["phone_number_id"],
        )

        # Request with non-matching account_id
        resp = client.get(
            f"/api/conversations/poll?since={since}&account_id=nonexistent-account",
            headers=_ADMIN_HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        # Should have no events for this non-matching account
        if len(data["events"]) > 0:
            for e in data["events"]:
                assert e["account_id"] == "nonexistent-account", (
                    f"Expected nonexistent-account, got {e['account_id']}"
                )

    def test_poll_events_sorted_by_time(self, client: TestClient) -> None:
        """Test 5: Events are sorted by created_at."""
        self._setup_account(client)
        since = (datetime.now(UTC) - timedelta(hours=2)).isoformat().replace("+00:00", "Z")

        # Send a message
        _post_mock_inbound_message(
            client,
            account_id=_ACCOUNT_ID,
            conversation_id=_CONVERSATION_ID,
            user_id="user-sort-1",
            text="First message for sorting",
            phone_number_id=_PHONE_NUMBER["phone_number_id"],
        )

        resp = client.get(
            f"/api/conversations/poll?since={since}",
            headers=_ADMIN_HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        events = data["events"]
        timestamps = [e["created_at"] for e in events]
        assert timestamps == sorted(timestamps), "Events are not sorted by time"

    def test_poll_invalid_since_format_returns_422(self, client: TestClient) -> None:
        """Test 6: Invalid since format → 422."""
        self._setup_account(client)
        resp = client.get(
            "/api/conversations/poll?since=not-a-date",
            headers=_ADMIN_HEADERS,
        )
        assert resp.status_code == 422

    def test_poll_requires_auth(self, client: TestClient) -> None:
        """Test 7: Missing auth headers → 401 in non-test mode."""
        from app.core.settings import get_settings

        settings = get_settings()
        original_auth = settings.auth_required
        original_test = settings.test_mode
        settings.auth_required = True
        settings.test_mode = False
        try:
            since = (datetime.now(UTC)).isoformat().replace("+00:00", "Z")
            resp = client.get(f"/api/conversations/poll?since={since}")
            assert resp.status_code == 401
        finally:
            settings.auth_required = original_auth
            settings.test_mode = original_test


class TestStreamEndpoint:
    """RT-003: GET /api/conversations/stream

    Unit tests verify JWT auth and endpoint existence.
    Streaming content is validated by end-to-end tests (``_sse_test.py``).
    """

    def _get_admin_token(self, client: TestClient) -> str:
        """Login as default admin and return access token."""
        resp = client.post(
            "/api/admin/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        assert resp.status_code == 200, f"Login failed: {resp.text}"
        return resp.json()["access_token"]

    def _setup_account(self, client: TestClient) -> None:
        _create_manual_meta_account(
            client,
            account_id=_ACCOUNT_ID,
            portfolio_id=_PORTFOLIO_ID,
            waba_id=_WABA_ID,
            phone_numbers=[_PHONE_NUMBER],
        )

    def test_stream_missing_token_returns_422(self, client: TestClient) -> None:
        """Test 8: Missing token → 422 (endpoint exists, requires auth)."""
        resp = client.get("/api/conversations/stream")
        assert resp.status_code == 422

    def test_stream_invalid_token_returns_401(self, client: TestClient) -> None:
        """Test 9: Invalid token → 401 (JWT verification works)."""
        resp = client.get("/api/conversations/stream?token=bad-token")
        assert resp.status_code == 401

    def test_stream_admin_login_works(self, client: TestClient) -> None:
        """Test 10: Admin login returns valid token (prerequisite for SSE)."""
        token = self._get_admin_token(client)
        assert len(token) > 20  # JWT should be reasonable length
