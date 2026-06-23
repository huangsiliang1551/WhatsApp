"""Tests for Conversation Sentiment Analysis API (B-04)."""

from fastapi.testclient import TestClient

from tests.test_conversations import _create_manual_meta_account, _post_mock_inbound_message


def _setup_account(client: TestClient) -> str:
    account_id = "sentiment-test-account"
    _create_manual_meta_account(
        client,
        account_id=account_id,
        portfolio_id="portfolio-sentiment-1",
        waba_id="waba-sentiment-1",
        phone_numbers=[
            {
                "phone_number_id": "pn-sentiment-1",
                "display_phone_number": "+1 555 000 0400",
                "verified_name": "Sentiment Test",
                "quality_rating": "GREEN",
                "is_registered": True,
            }
        ],
    )
    return account_id


class TestConversationSentiment:
    def test_sentiment_returns_expected_structure(self, client: TestClient) -> None:
        """Sentiment may return mock fallback in test environment, but structure must be valid."""
        account_id = _setup_account(client)
        _post_mock_inbound_message(
            client,
            account_id=account_id,
            conversation_id="conv-sent-1",
            user_id="user-sent-1",
            text="I am very frustrated with your service!",
        )
        resp = client.get(
            f"/api/conversations/{account_id}/conv-sent-1/sentiment",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "sentiment" in data
        assert "confidence" in data
        assert "summary" in data
        assert data["sentiment"] in ("angry", "anxious", "satisfied", "neutral")
        assert isinstance(data["confidence"], (int, float))
        assert 0.0 <= data["confidence"] <= 1.0

    def test_sentiment_no_messages_returns_neutral(self, client: TestClient) -> None:
        account_id = _setup_account(client)
        resp = client.get(
            f"/api/conversations/{account_id}/conv-sent-empty/sentiment",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["sentiment"] == "neutral"

    def test_sentiment_nonexistent_conversation_404(self, client: TestClient) -> None:
        account_id = _setup_account(client)
        resp = client.get(
            f"/api/conversations/{account_id}/conv-does-not-exist/sentiment",
        )
        assert resp.status_code == 404
