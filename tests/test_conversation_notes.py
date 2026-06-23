"""Tests for Conversation Notes API (BFX-003)."""

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.postgres

from tests.test_conversations import _create_manual_meta_account, _post_mock_inbound_message


def _setup_account(client: TestClient) -> str:
    account_id = "notes-test-account"
    _create_manual_meta_account(
        client,
        account_id=account_id,
        portfolio_id="portfolio-notes-1",
        waba_id="waba-notes-1",
        phone_numbers=[
            {
                "phone_number_id": "pn-notes-1",
                "display_phone_number": "+1 555 000 0001",
                "verified_name": "Notes Test",
                "quality_rating": "GREEN",
                "is_registered": True,
            }
        ],
    )
    return account_id


class TestConversationNotes:
    def test_create_note(self, client: TestClient) -> None:
        account_id = _setup_account(client)
        _post_mock_inbound_message(
            client,
            account_id=account_id,
            conversation_id="conv-notes-1",
            user_id="user-notes-1",
            text="Test conversation for notes",
        )
        resp = client.post(
            f"/api/conversations/{account_id}:conv-notes-1/notes",
            json={"content": "Customer needs urgent help", "agent_id": "agent-001"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["content"] == "Customer needs urgent help"
        assert data["agent_id"] == "agent-001"
        assert "id" in data
        assert "created_at" in data

    def test_list_notes(self, client: TestClient) -> None:
        account_id = _setup_account(client)
        _post_mock_inbound_message(
            client,
            account_id=account_id,
            conversation_id="conv-notes-2",
            user_id="user-notes-2",
            text="Test for listing notes",
        )
        client.post(
            f"/api/conversations/{account_id}:conv-notes-2/notes",
            json={"content": "First note", "agent_id": "agent-001"},
        )
        client.post(
            f"/api/conversations/{account_id}:conv-notes-2/notes",
            json={"content": "Second note", "agent_id": "agent-002"},
        )
        resp = client.get(f"/api/conversations/{account_id}:conv-notes-2/notes")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 2

    def test_note_has_required_fields(self, client: TestClient) -> None:
        account_id = _setup_account(client)
        _post_mock_inbound_message(
            client,
            account_id=account_id,
            conversation_id="conv-notes-3",
            user_id="user-notes-3",
            text="Test fields",
        )
        resp = client.post(
            f"/api/conversations/{account_id}:conv-notes-3/notes",
            json={"content": "Test note", "agent_id": "agent-003"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for field in ("id", "conversation_id", "content", "agent_id", "created_at"):
            assert field in data

    def test_account_id_isolation(self, client: TestClient) -> None:
        account_id = _setup_account(client)
        _post_mock_inbound_message(
            client,
            account_id=account_id,
            conversation_id="conv-notes-4",
            user_id="user-notes-4",
            text="Test isolation",
        )
        client.post(
            f"/api/conversations/{account_id}:conv-notes-4/notes",
            json={"content": "Note for account A", "agent_id": "agent-001"},
        )
        # Query with wrong account prefix should not find notes
        resp = client.get("/api/conversations/wrong-account:conv-notes-4/notes")
        assert resp.status_code in (200, 404)
        if resp.status_code == 200:
            assert len(resp.json()) == 0

    def test_create_note_empty_content_rejected(self, client: TestClient) -> None:
        account_id = _setup_account(client)
        _post_mock_inbound_message(
            client,
            account_id=account_id,
            conversation_id="conv-notes-5",
            user_id="user-notes-5",
            text="Test empty",
        )
        resp = client.post(
            f"/api/conversations/{account_id}:conv-notes-5/notes",
            json={"content": "", "agent_id": "agent-001"},
        )
        assert resp.status_code == 422

    def test_list_notes_no_notes(self, client: TestClient) -> None:
        account_id = _setup_account(client)
        _post_mock_inbound_message(
            client,
            account_id=account_id,
            conversation_id="conv-notes-6",
            user_id="user-notes-6",
            text="Test no notes",
        )
        resp = client.get(f"/api/conversations/{account_id}:conv-notes-6/notes")
        assert resp.status_code == 200
        assert resp.json() == []
