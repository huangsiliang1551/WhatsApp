"""Tests for Conversation SLA API (B-05)."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Conversation

from tests.test_conversations import _create_manual_meta_account, _post_mock_inbound_message


def _setup_account(client: TestClient) -> str:
    account_id = "sla-test-account"
    _create_manual_meta_account(
        client,
        account_id=account_id,
        portfolio_id="portfolio-sla-1",
        waba_id="waba-sla-1",
        phone_numbers=[
            {
                "phone_number_id": "pn-sla-1",
                "display_phone_number": "+1 555 000 0300",
                "verified_name": "SLA Test",
                "quality_rating": "GREEN",
                "is_registered": True,
            }
        ],
    )
    return account_id


def _create_empty_conversation(
    db_session_factory: sessionmaker[Session],
    *,
    account_id: str,
    conversation_id: str,
    customer_id: str,
) -> None:
    with db_session_factory() as session:
        session.add(
            Conversation(
                id=conversation_id,
                account_id=account_id,
                external_conversation_id=conversation_id,
                customer_id=customer_id,
                status="open",
                is_sleeping=False,
            )
        )
        session.commit()


class TestConversationSla:
    def test_get_sla_returns_expected_structure(self, client: TestClient) -> None:
        account_id = _setup_account(client)
        _post_mock_inbound_message(
            client,
            account_id=account_id,
            conversation_id="conv-sla-1",
            user_id="user-sla-1",
            text="I need help urgently!",
        )
        resp = client.get(
            f"/api/conversations/{account_id}/conv-sla-1/sla",
        )
        assert resp.status_code == 200
        data = resp.json()
        for key in (
            "waiting_seconds",
            "threshold_warning",
            "threshold_critical",
            "is_overdue",
            "last_inbound_at",
        ):
            assert key in data
        assert isinstance(data["waiting_seconds"], int)
        assert isinstance(data["threshold_warning"], int)
        assert isinstance(data["threshold_critical"], int)
        assert isinstance(data["is_overdue"], bool)
        assert data["last_inbound_at"] is not None

    def test_sla_no_messages_returns_defaults(
        self,
        client: TestClient,
        db_session_factory: sessionmaker[Session],
    ) -> None:
        account_id = _setup_account(client)
        _create_empty_conversation(
            db_session_factory,
            account_id=account_id,
            conversation_id="conv-sla-empty",
            customer_id="user-sla-empty",
        )
        resp = client.get(
            f"/api/conversations/{account_id}/conv-sla-empty/sla",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["waiting_seconds"] == 0
        assert data["last_inbound_at"] is None
        assert data["is_overdue"] is False

    def test_sla_nonexistent_conversation_404(self, client: TestClient) -> None:
        account_id = _setup_account(client)
        resp = client.get(
            f"/api/conversations/{account_id}/conv-does-not-exist/sla",
        )
        assert resp.status_code == 404
