"""Tests for AI Reply Preview API (B-06)."""

from fastapi.testclient import TestClient

from tests.test_conversations import _create_manual_meta_account, _post_mock_inbound_message


def _setup_account(client: TestClient) -> str:
    account_id = "ai-preview-test-account"
    _create_manual_meta_account(
        client,
        account_id=account_id,
        portfolio_id="portfolio-ai-preview-1",
        waba_id="waba-ai-preview-1",
        phone_numbers=[
            {
                "phone_number_id": "pn-ai-preview-1",
                "display_phone_number": "+1 555 000 0500",
                "verified_name": "AI Preview Test",
                "quality_rating": "GREEN",
                "is_registered": True,
            }
        ],
    )
    return account_id


class TestAiReplyPreview:
    def test_ai_preview_returns_structure(self, client: TestClient) -> None:
        """In test environment, AI provider may be mock; verify structure regardless."""
        account_id = _setup_account(client)
        _post_mock_inbound_message(
            client,
            account_id=account_id,
            conversation_id="conv-ai-preview-1",
            user_id="user-ai-1",
            text="What are your business hours?",
        )
        resp = client.post(
            f"/api/conversations/{account_id}/conv-ai-preview-1/ai-preview",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "preview_text" in data
        assert isinstance(data["preview_text"], str)

    def test_ai_preview_empty_conversation(self, client: TestClient) -> None:
        account_id = _setup_account(client)
        resp = client.post(
            f"/api/conversations/{account_id}/conv-ai-preview-empty/ai-preview",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "preview_text" in data

    def test_ai_preview_nonexistent_conversation_404(self, client: TestClient) -> None:
        account_id = _setup_account(client)
        resp = client.post(
            f"/api/conversations/{account_id}/conv-does-not-exist/ai-preview",
        )
        assert resp.status_code == 404
