"""Tests for Conversation Message Search API (B-01)."""

from fastapi.testclient import TestClient

from tests.test_conversations import _create_manual_meta_account, _post_mock_inbound_message


def _setup_account(client: TestClient) -> str:
    account_id = "search-test-account"
    _create_manual_meta_account(
        client,
        account_id=account_id,
        portfolio_id="portfolio-search-1",
        waba_id="waba-search-1",
        phone_numbers=[
            {
                "phone_number_id": "pn-search-1",
                "display_phone_number": "+1 555 000 0100",
                "verified_name": "Search Test",
                "quality_rating": "GREEN",
                "is_registered": True,
            }
        ],
    )
    return account_id


class TestConversationSearch:
    def test_search_messages_finds_match(self, client: TestClient) -> None:
        account_id = _setup_account(client)
        _post_mock_inbound_message(
            client,
            account_id=account_id,
            conversation_id="conv-search-1",
            user_id="user-search-1",
            text="我需要退换货，订单号 ORDER-12345",
        )
        resp = client.get(
            f"/api/conversations/{account_id}/conv-search-1/messages/search",
            params={"q": "退换货"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_search_no_match_returns_empty(self, client: TestClient) -> None:
        account_id = _setup_account(client)
        _post_mock_inbound_message(
            client,
            account_id=account_id,
            conversation_id="conv-search-2",
            user_id="user-search-2",
            text="Hello, how are you?",
        )
        resp = client.get(
            f"/api/conversations/{account_id}/conv-search-2/messages/search",
            params={"q": "XYZZY_NOT_FOUND_999"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data == []

    def test_search_requires_query(self, client: TestClient) -> None:
        account_id = _setup_account(client)
        resp = client.get(
            f"/api/conversations/{account_id}/conv-nonexistent/messages/search",
        )
        assert resp.status_code == 422

    def test_search_nonexistent_conversation_404(self, client: TestClient) -> None:
        account_id = _setup_account(client)
        resp = client.get(
            f"/api/conversations/{account_id}/conv-does-not-exist/messages/search",
            params={"q": "anything"},
        )
        assert resp.status_code == 404
