"""Tests for Message Forward API (B-03)."""

from fastapi.testclient import TestClient

from tests.test_conversations import _create_manual_meta_account, _post_mock_inbound_message


def _setup_account(client: TestClient) -> str:
    account_id = "forward-test-account"
    _create_manual_meta_account(
        client,
        account_id=account_id,
        portfolio_id="portfolio-forward-1",
        waba_id="waba-forward-1",
        phone_numbers=[
            {
                "phone_number_id": "pn-forward-1",
                "display_phone_number": "+1 555 000 0200",
                "verified_name": "Forward Test",
                "quality_rating": "GREEN",
                "is_registered": True,
            }
        ],
    )
    return account_id


class TestConversationForward:
    def test_forward_message_to_another_conversation(self, client: TestClient) -> None:
        account_id = _setup_account(client)
        _post_mock_inbound_message(
            client,
            account_id=account_id,
            conversation_id="conv-forward-src",
            user_id="user-forward-src",
            text="Please forward this message.",
        )
        _post_mock_inbound_message(
            client,
            account_id=account_id,
            conversation_id="conv-forward-dst",
            user_id="user-forward-dst",
            text="Target conversation for forwarding.",
        )

        list_resp = client.get(
            f"/api/conversations/{account_id}/conv-forward-src/messages",
            params={"limit": 5},
        )
        assert list_resp.status_code == 200
        messages = list_resp.json()
        assert len(messages) >= 1
        msg_id = messages[0]["id"]

        resp = client.post(
            f"/api/conversations/{account_id}/conv-forward-src/messages/{msg_id}/forward",
            json={
                "target_conversation_id": "conv-forward-dst",
                "include_context": True,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "message_id" in data
        assert data["target_conversation_id"] == "conv-forward-dst"

    def test_forward_nonexistent_message_404(self, client: TestClient) -> None:
        account_id = _setup_account(client)
        _post_mock_inbound_message(
            client,
            account_id=account_id,
            conversation_id="conv-fwd-3",
            user_id="user-fwd-3",
            text="Test target.",
        )
        resp = client.post(
            f"/api/conversations/{account_id}/conv-fwd-3/messages/nonexistent-msg/forward",
            json={"target_conversation_id": "conv-fwd-3"},
        )
        assert resp.status_code == 404

    def test_forward_to_nonexistent_target_404(self, client: TestClient) -> None:
        account_id = _setup_account(client)
        _post_mock_inbound_message(
            client,
            account_id=account_id,
            conversation_id="conv-fwd-4",
            user_id="user-fwd-4",
            text="Source message.",
        )
        list_resp = client.get(
            f"/api/conversations/{account_id}/conv-fwd-4/messages",
            params={"limit": 5},
        )
        assert list_resp.status_code == 200
        messages = list_resp.json()
        assert len(messages) >= 1
        msg_id = messages[0]["id"]

        resp = client.post(
            f"/api/conversations/{account_id}/conv-fwd-4/messages/{msg_id}/forward",
            json={"target_conversation_id": "conv-does-not-exist"},
        )
        assert resp.status_code == 404
