import os
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import get_messaging_service
from app.core.settings import get_settings
from app.db.models import Message, WhatsAppBusinessAccount
from app.providers.messaging.mock_provider import MockMessagingProvider
from app.schemas.messaging import OutboundDispatchRequest, OutboundDispatchResult
from app.services.conversation_service import ConversationService


class RuntimeErrorOutboundMessagingProvider(MockMessagingProvider):
    async def send_outbound(self, payload: OutboundDispatchRequest) -> OutboundDispatchResult:
        del payload
        raise RuntimeError("provider_send_unavailable")


def _create_manual_meta_account(
    client: TestClient,
    *,
    account_id: str,
    portfolio_id: str,
    waba_id: str,
    phone_numbers: list[dict[str, object]],
) -> None:
    response = client.post(
        "/api/meta/accounts/manual",
        json={
            "account_id": account_id,
            "display_name": account_id,
            "meta_business_portfolio_id": portfolio_id,
            "waba_id": waba_id,
            "access_token": f"token-{account_id}-{waba_id}",
            "verify_token": f"verify-{account_id}-{waba_id}",
            "app_secret": f"secret-{account_id}-{waba_id}",
            "token_source": "system_user",
            "phone_numbers": phone_numbers,
        },
    )
    assert response.status_code == 200


def _post_mock_inbound_message(
    client: TestClient,
    *,
    account_id: str,
    conversation_id: str,
    user_id: str,
    text: str,
    phone_number_id: str | None = None,
) -> None:
    payload: dict[str, object] = {
        "account_id": account_id,
        "conversation_id": conversation_id,
        "user_id": user_id,
        "text": text,
        "mode": "echo",
    }
    if phone_number_id is not None:
        payload["phone_number_id"] = phone_number_id

    response = client.post("/dev/mock/inbound-message", json=payload)
    assert response.status_code == 200


def test_list_conversations_and_messages_prefer_original_text_by_default(client: TestClient) -> None:
    inbound_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "mock-account-9",
            "conversation_id": "conv-9",
            "user_id": "user-9",
            "text": "bonjour, commande 123",
            "mode": "echo",
        },
    )
    assert inbound_response.status_code == 200

    conversations_response = client.get("/api/conversations?account_id=mock-account-9")
    assert conversations_response.status_code == 200
    conversations = conversations_response.json()["items"]

    assert conversations[0]["customer_language"] == "fr"
    assert conversations[0]["status"] == "open"
    assert conversations[0]["assigned_agent_name"] is None
    assert conversations[0]["last_message_preview"] == "Echo: bonjour, commande 123"

    messages_response = client.get("/api/conversations/mock-account-9/conv-9/messages")
    assert messages_response.status_code == 200
    messages = messages_response.json()

    assert messages[0]["original_text"] == "bonjour, commande 123"
    assert messages[0]["translated_text"] is None
    assert messages[0]["console_text"] == "bonjour, commande 123"


def test_list_messages_can_explicitly_request_conversation_view_translation(client: TestClient) -> None:
    inbound_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "mock-account-9b",
            "conversation_id": "conv-9b",
            "user_id": "user-9b",
            "text": "bonjour, commande 456",
            "mode": "echo",
        },
    )
    assert inbound_response.status_code == 200

    messages_response = client.get(
        "/api/conversations/mock-account-9b/conv-9b/messages",
        params={"include_translations": "true"},
    )
    assert messages_response.status_code == 200
    messages = messages_response.json()

    assert messages[0]["original_text"] == "bonjour, commande 456"
    assert messages[0]["translated_text"] is None
    assert messages[0]["translation_kind"] is None


def test_manual_outbound_message_auto_translates_from_chinese_to_customer_language(
    client: TestClient,
) -> None:
    register_agent_response = client.post(
        "/api/runtime/agents",
        json={
            "agent_id": "agent-cn-1",
            "display_name": "CN Agent",
            "status": "online",
            "is_active": True,
        },
    )
    assert register_agent_response.status_code == 200

    client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "mock-account-10",
            "conversation_id": "conv-10",
            "user_id": "user-10",
            "text": "hola",
            "mode": "echo",
        },
    )
    assignment_response = client.post(
        "/api/conversations/mock-account-10/conv-10/assignment",
        json={
            "agent_id": "agent-cn-1",
            "assigned_by_agent_id": "agent-cn-1",
            "reason": "manual_reply",
        },
    )
    assert assignment_response.status_code == 200

    outbound_response = client.post(
        "/api/conversations/mock-account-10/conv-10/messages/outbound",
        json={
            "text": "\u60a8\u597d\uff0c\u8ba2\u5355\u5df2\u7ecf\u53d1\u8d27\u3002",
            "agent_id": "agent-cn-1",
        },
    )
    assert outbound_response.status_code == 200
    payload = outbound_response.json()

    assert payload["source_language"] == "zh-CN"
    assert payload["target_language"] == "es"
    assert payload["translated"] is True
    assert "auto-translated zh-CN->es" in payload["delivered_text"]

    messages_response = client.get("/api/conversations/mock-account-10/conv-10/messages")
    messages = messages_response.json()
    outbound_message = messages[-1]

    assert outbound_message["original_text"] == "\u60a8\u597d\uff0c\u8ba2\u5355\u5df2\u7ecf\u53d1\u8d27\u3002"
    assert "auto-translated zh-CN->es" in outbound_message["translated_text"]
    assert "auto-translated zh-CN->es" in outbound_message["delivered_text"]
    assert outbound_message["translation_kind"] == "outbound_operator_translation"


def test_manual_outbound_message_uses_support_actor_identity_when_agent_id_is_omitted(
    client: TestClient,
) -> None:
    for agent_id, display_name in (
        ("agent-implicit-owner-1", "Implicit Owner"),
        ("agent-implicit-other-1", "Implicit Other"),
    ):
        register_agent_response = client.post(
            "/api/runtime/agents",
            json={
                "account_id": "implicit-reply-account-1",
                "agent_id": agent_id,
                "display_name": display_name,
                "status": "online",
                "is_active": True,
            },
        )
        assert register_agent_response.status_code == 200

    _post_mock_inbound_message(
        client,
        account_id="implicit-reply-account-1",
        conversation_id="implicit-reply-conv-1",
        user_id="implicit-reply-user-1",
        text="need assigned operator reply",
    )

    assignment_response = client.post(
        "/api/conversations/implicit-reply-account-1/implicit-reply-conv-1/assignment",
        json={
            "agent_id": "agent-implicit-owner-1",
            "assigned_by_agent_id": "agent-implicit-owner-1",
            "reason": "manual_takeover",
        },
    )
    assert assignment_response.status_code == 200

    blocked_response = client.post(
        "/api/conversations/implicit-reply-account-1/implicit-reply-conv-1/messages/outbound",
        headers={
            "X-Actor-Id": "agent-implicit-other-1",
            "X-Actor-Role": "support_agent",
            "X-Actor-Account-Ids": "implicit-reply-account-1",
        },
        json={"text": "rogue reply without explicit agent id"},
    )
    assert blocked_response.status_code == 403
    assert "assigned to 'agent-implicit-owner-1'" in blocked_response.json()["detail"]

    owner_response = client.post(
        "/api/conversations/implicit-reply-account-1/implicit-reply-conv-1/messages/outbound",
        headers={
            "X-Actor-Id": "agent-implicit-owner-1",
            "X-Actor-Role": "support_agent",
            "X-Actor-Account-Ids": "implicit-reply-account-1",
        },
        json={"text": "owner reply without explicit agent id"},
    )
    assert owner_response.status_code == 200
    assert owner_response.json()["account_id"] == "implicit-reply-account-1"


def test_manual_outbound_message_rejects_inactive_phone_number_scope(client: TestClient) -> None:
    register_agent_response = client.post(
        "/api/runtime/agents",
        json={
            "agent_id": "agent-cn-inactive-phone",
            "display_name": "CN Agent Inactive Phone",
            "status": "online",
            "is_active": True,
        },
    )
    assert register_agent_response.status_code == 200

    manual_account_response = client.post(
        "/api/meta/accounts/manual",
        json={
            "account_id": "inactive-phone-account-1",
            "display_name": "Inactive Phone Account",
            "meta_business_portfolio_id": "portfolio-inactive-phone-1",
            "waba_id": "waba-inactive-phone-1",
            "access_token": "token-inactive-phone-1",
            "verify_token": "verify-inactive-phone-1",
            "app_secret": "secret-inactive-phone-1",
            "token_source": "system_user",
            "phone_numbers": [
                {
                    "phone_number_id": "pn-inactive-phone-1",
                    "display_phone_number": "+1 555 000 0301",
                    "verified_name": "Inactive Phone Number",
                    "quality_rating": "GREEN",
                    "is_registered": True,
                }
            ],
        },
    )
    assert manual_account_response.status_code == 200

    inbound_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "inactive-phone-account-1",
            "conversation_id": "conv-inactive-phone-1",
            "user_id": "user-inactive-phone-1",
            "text": "hola",
            "mode": "echo",
            "phone_number_id": "pn-inactive-phone-1",
        },
    )
    assert inbound_response.status_code == 200

    assignment_response = client.post(
        "/api/conversations/inactive-phone-account-1/conv-inactive-phone-1/assignment",
        json={
            "agent_id": "agent-cn-inactive-phone",
            "assigned_by_agent_id": "agent-cn-inactive-phone",
            "reason": "manual_reply",
        },
    )
    assert assignment_response.status_code == 200

    deactivate_phone_response = client.patch(
        "/api/meta/accounts/inactive-phone-account-1/wabas/waba-inactive-phone-1/phone-numbers/pn-inactive-phone-1/status",
        json={"is_active": False},
    )
    assert deactivate_phone_response.status_code == 200

    outbound_response = client.post(
        "/api/conversations/inactive-phone-account-1/conv-inactive-phone-1/messages/outbound",
        json={
            "text": "\u8fd9\u6761\u6d88\u606f\u4e0d\u5e94\u53d1\u51fa",
            "agent_id": "agent-cn-inactive-phone",
        },
    )
    assert outbound_response.status_code == 409
    assert "inactive" in outbound_response.json()["detail"]


def test_manual_outbound_message_rejects_missing_meta_access_token(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    register_agent_response = client.post(
        "/api/runtime/agents",
        json={
            "agent_id": "agent-cn-missing-token",
            "display_name": "CN Agent Missing Token",
            "status": "online",
            "is_active": True,
        },
    )
    assert register_agent_response.status_code == 200

    _create_manual_meta_account(
        client,
        account_id="missing-token-account-1",
        portfolio_id="portfolio-missing-token-1",
        waba_id="waba-missing-token-1",
        phone_numbers=[
            {
                "phone_number_id": "pn-missing-token-1",
                "display_phone_number": "+1 555 000 0302",
                "verified_name": "Missing Token Number",
                "quality_rating": "GREEN",
                "is_registered": True,
            }
        ],
    )

    with db_session_factory() as session:
        waba_account = session.query(WhatsAppBusinessAccount).filter_by(
            account_id="missing-token-account-1",
            waba_id="waba-missing-token-1",
        ).one()
        waba_account.access_token = None
        session.commit()

    _post_mock_inbound_message(
        client,
        account_id="missing-token-account-1",
        conversation_id="conv-missing-token-1",
        user_id="user-missing-token-1",
        text="hola",
        phone_number_id="pn-missing-token-1",
    )

    assignment_response = client.post(
        "/api/conversations/missing-token-account-1/conv-missing-token-1/assignment",
        json={
            "agent_id": "agent-cn-missing-token",
            "assigned_by_agent_id": "agent-cn-missing-token",
            "reason": "manual_reply",
        },
    )
    assert assignment_response.status_code == 200

    outbound_response = client.post(
        "/api/conversations/missing-token-account-1/conv-missing-token-1/messages/outbound",
        json={
            "text": "this message should be blocked",
            "agent_id": "agent-cn-missing-token",
        },
    )
    assert outbound_response.status_code == 503
    assert "access token" in outbound_response.json()["detail"].lower()


def test_manual_outbound_message_returns_502_for_provider_runtime_failure(
    client: TestClient,
) -> None:
    register_agent_response = client.post(
        "/api/runtime/agents",
        json={
            "account_id": "runtime-fail-account-1",
            "agent_id": "agent-runtime-fail-1",
            "display_name": "Runtime Fail Agent",
            "status": "online",
            "is_active": True,
        },
    )
    assert register_agent_response.status_code == 200

    _post_mock_inbound_message(
        client,
        account_id="runtime-fail-account-1",
        conversation_id="conv-runtime-fail-1",
        user_id="user-runtime-fail-1",
        text="need outbound runtime failure coverage",
    )

    assignment_response = client.post(
        "/api/conversations/runtime-fail-account-1/conv-runtime-fail-1/assignment",
        json={
            "agent_id": "agent-runtime-fail-1",
            "assigned_by_agent_id": "agent-runtime-fail-1",
            "reason": "manual_reply",
        },
    )
    assert assignment_response.status_code == 200

    client.app.dependency_overrides[get_messaging_service] = (
        lambda: RuntimeErrorOutboundMessagingProvider()
    )
    try:
        outbound_response = client.post(
            "/api/conversations/runtime-fail-account-1/conv-runtime-fail-1/messages/outbound",
            json={
                "text": "this message should surface as provider upstream failure",
                "agent_id": "agent-runtime-fail-1",
            },
        )
    finally:
        client.app.dependency_overrides.pop(get_messaging_service, None)

    assert outbound_response.status_code == 502
    assert outbound_response.json()["detail"] == "provider_send_unavailable"


def test_manual_outbound_message_rejects_unregistered_phone_number_scope(
    client: TestClient,
) -> None:
    register_agent_response = client.post(
        "/api/runtime/agents",
        json={
            "agent_id": "agent-cn-unregistered-phone",
            "display_name": "CN Agent Unregistered Phone",
            "status": "online",
            "is_active": True,
        },
    )
    assert register_agent_response.status_code == 200

    _create_manual_meta_account(
        client,
        account_id="unregistered-phone-account-1",
        portfolio_id="portfolio-unregistered-phone-1",
        waba_id="waba-unregistered-phone-1",
        phone_numbers=[
            {
                "phone_number_id": "pn-unregistered-phone-1",
                "display_phone_number": "+1 555 000 0303",
                "verified_name": "Unregistered Phone Number",
                "quality_rating": "GREEN",
                "is_registered": False,
            }
        ],
    )

    _post_mock_inbound_message(
        client,
        account_id="unregistered-phone-account-1",
        conversation_id="conv-unregistered-phone-1",
        user_id="user-unregistered-phone-1",
        text="hola",
        phone_number_id="pn-unregistered-phone-1",
    )

    assignment_response = client.post(
        "/api/conversations/unregistered-phone-account-1/conv-unregistered-phone-1/assignment",
        json={
            "agent_id": "agent-cn-unregistered-phone",
            "assigned_by_agent_id": "agent-cn-unregistered-phone",
            "reason": "manual_reply",
        },
    )
    assert assignment_response.status_code == 200

    outbound_response = client.post(
        "/api/conversations/unregistered-phone-account-1/conv-unregistered-phone-1/messages/outbound",
        json={
            "text": "this message should be blocked",
            "agent_id": "agent-cn-unregistered-phone",
        },
    )
    assert outbound_response.status_code == 409
    assert "not registered" in outbound_response.json()["detail"].lower()


def test_manual_outbound_message_response_and_audit_include_meta_phone_scope(
    client: TestClient,
) -> None:
    register_agent_response = client.post(
        "/api/runtime/agents",
        json={
            "agent_id": "agent-phone-scope-1",
            "display_name": "Phone Scope Agent",
            "status": "online",
            "is_active": True,
        },
    )
    assert register_agent_response.status_code == 200

    _create_manual_meta_account(
        client,
        account_id="phone-scope-account-1",
        portfolio_id="portfolio-phone-scope-1",
        waba_id="waba-phone-scope-1",
        phone_numbers=[
            {
                "phone_number_id": "pn-phone-scope-1",
                "display_phone_number": "+1 555 000 0401",
                "verified_name": "Phone Scope Number",
                "quality_rating": "GREEN",
                "is_registered": True,
            }
        ],
    )
    _post_mock_inbound_message(
        client,
        account_id="phone-scope-account-1",
        conversation_id="conv-phone-scope-1",
        user_id="user-phone-scope-1",
        text="hello",
        phone_number_id="pn-phone-scope-1",
    )

    assignment_response = client.post(
        "/api/conversations/phone-scope-account-1/conv-phone-scope-1/assignment",
        json={
            "agent_id": "agent-phone-scope-1",
            "assigned_by_agent_id": "agent-phone-scope-1",
            "reason": "manual_reply",
        },
    )
    assert assignment_response.status_code == 200

    outbound_response = client.post(
        "/api/conversations/phone-scope-account-1/conv-phone-scope-1/messages/outbound",
        json={
            "text": "Manual reply with explicit phone scope.",
            "agent_id": "agent-phone-scope-1",
        },
    )
    assert outbound_response.status_code == 200
    outbound_payload = outbound_response.json()
    assert outbound_payload["account_id"] == "phone-scope-account-1"
    assert outbound_payload["waba_id"] == "waba-phone-scope-1"
    assert outbound_payload["phone_number_id"] == "pn-phone-scope-1"

    messages_response = client.get(
        "/api/conversations/phone-scope-account-1/conv-phone-scope-1/messages"
    )
    assert messages_response.status_code == 200
    outbound_message = messages_response.json()[-1]
    assert outbound_message["waba_id"] == "waba-phone-scope-1"
    assert outbound_message["phone_number_id"] == "pn-phone-scope-1"
    assert outbound_message["provider_message_id"] == outbound_payload["provider_message_id"]
    assert outbound_message["provider_media_id"] is None
    assert outbound_message["payload"]["waba_id"] == "waba-phone-scope-1"
    assert outbound_message["payload"]["phone_number_id"] == "pn-phone-scope-1"

    audit_response = client.get(
        "/api/runtime/audit-logs",
        params={
            "account_id": "phone-scope-account-1",
            "waba_id": "waba-phone-scope-1",
            "phone_number_id": "pn-phone-scope-1",
            "action": "manual_outbound_message_sent",
        },
    )
    assert audit_response.status_code == 200
    audit_logs = audit_response.json()
    assert len(audit_logs) == 1
    assert audit_logs[0]["waba_id"] == "waba-phone-scope-1"
    assert audit_logs[0]["phone_number_id"] == "pn-phone-scope-1"
    assert audit_logs[0]["payload"]["waba_id"] == "waba-phone-scope-1"
    assert audit_logs[0]["payload"]["phone_number_id"] == "pn-phone-scope-1"


def test_whatsapp_manual_outbound_requires_conversation_phone_number_scope(
    client: TestClient,
) -> None:
    register_agent_response = client.post(
        "/api/runtime/agents",
        json={
            "agent_id": "agent-whatsapp-no-phone-1",
            "display_name": "WhatsApp No Phone Agent",
            "status": "online",
            "is_active": True,
        },
    )
    assert register_agent_response.status_code == 200

    _post_mock_inbound_message(
        client,
        account_id="whatsapp-no-phone-account-1",
        conversation_id="conv-whatsapp-no-phone-1",
        user_id="user-whatsapp-no-phone-1",
        text="hello",
    )

    assignment_response = client.post(
        "/api/conversations/whatsapp-no-phone-account-1/conv-whatsapp-no-phone-1/assignment",
        json={
            "agent_id": "agent-whatsapp-no-phone-1",
            "assigned_by_agent_id": "agent-whatsapp-no-phone-1",
            "reason": "manual_reply",
        },
    )
    assert assignment_response.status_code == 200

    original_messaging_provider = os.environ.get("MESSAGING_PROVIDER")
    try:
        os.environ["MESSAGING_PROVIDER"] = "whatsapp"
        get_settings.cache_clear()
        outbound_response = client.post(
            "/api/conversations/whatsapp-no-phone-account-1/conv-whatsapp-no-phone-1/messages/outbound",
            json={
                "text": "This should fail before provider send.",
                "agent_id": "agent-whatsapp-no-phone-1",
            },
        )
    finally:
        if original_messaging_provider is None:
            os.environ.pop("MESSAGING_PROVIDER", None)
        else:
            os.environ["MESSAGING_PROVIDER"] = original_messaging_provider
        get_settings.cache_clear()

    assert outbound_response.status_code == 409
    assert "phone_number_id" in outbound_response.json()["detail"]


def test_conversation_summary_exposes_latest_intent_and_handover_recommendation(
    client: TestClient,
) -> None:
    inbound_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "intent-summary-account-1",
            "conversation_id": "intent-summary-conv-1",
            "user_id": "intent-summary-user-1",
            "text": "I want to talk to a human agent.",
            "mode": "ai",
            "language_hint": "en",
        },
    )
    assert inbound_response.status_code == 200

    conversations_response = client.get("/api/conversations")
    assert conversations_response.status_code == 200
    conversations = conversations_response.json()["items"]
    conversation = next(
        item
        for item in conversations
        if item["account_id"] == "intent-summary-account-1"
        and item["conversation_id"] == "intent-summary-conv-1"
    )

    assert conversation["latest_intent_name"] == "human_handover_request"
    assert conversation["latest_handover_recommended"] is True
    assert conversation["latest_handover_reason"] == "customer_requested_human_support"


def test_conversation_summary_exposes_phone_number_id_when_bound(client: TestClient) -> None:
    manual_account_response = client.post(
        "/api/meta/accounts/manual",
        json={
            "account_id": "conversation-phone-account-1",
            "display_name": "Conversation Phone Account",
            "meta_business_portfolio_id": "portfolio-conversation-1",
            "waba_id": "waba-conversation-1",
            "access_token": "token-conversation-1",
            "verify_token": "verify-conversation-1",
            "app_secret": "secret-conversation-1",
            "token_source": "system_user",
            "phone_numbers": [
                {
                    "phone_number_id": "pn-conversation-1",
                    "display_phone_number": "+1 555 000 0002",
                    "verified_name": "Conversation Number",
                    "quality_rating": "GREEN",
                    "is_registered": True,
                }
            ],
        },
    )
    assert manual_account_response.status_code == 200

    inbound_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "conversation-phone-account-1",
            "conversation_id": "conv-phone-1",
            "user_id": "user-phone-1",
            "text": "hello from bound number",
            "mode": "echo",
            "phone_number_id": "pn-conversation-1",
        },
    )
    assert inbound_response.status_code == 200

    conversations_response = client.get(
        "/api/conversations",
        params={"account_id": "conversation-phone-account-1"},
    )
    assert conversations_response.status_code == 200
    conversations = conversations_response.json()["items"]

    assert conversations[0]["phone_number_id"] == "pn-conversation-1"
    assert conversations[0]["waba_id"] == "waba-conversation-1"

    messages_response = client.get(
        "/api/conversations/conversation-phone-account-1/conv-phone-1/messages",
    )
    assert messages_response.status_code == 200
    assert messages_response.json()[0]["phone_number_id"] == "pn-conversation-1"


def test_list_messages_extracts_nested_scope_from_message_payload(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _create_manual_meta_account(
        client,
        account_id="conversation-nested-scope-account-1",
        portfolio_id="portfolio-conversation-nested-scope-1",
        waba_id="waba-conversation-nested-scope-1",
        phone_numbers=[
            {
                "phone_number_id": "pn-conversation-nested-scope-1",
                "display_phone_number": "+1 555 000 0003",
                "verified_name": "Conversation Nested Scope Number",
                "quality_rating": "GREEN",
                "is_registered": True,
            }
        ],
    )

    _post_mock_inbound_message(
        client,
        account_id="conversation-nested-scope-account-1",
        conversation_id="conv-nested-scope-1",
        user_id="user-nested-scope-1",
        text="hello from nested scope",
        phone_number_id="pn-conversation-nested-scope-1",
    )

    with db_session_factory() as session:
        inbound_message = (
            session.query(Message)
            .filter(
                Message.account_id == "conversation-nested-scope-account-1",
                Message.direction == "inbound",
                Message.provider_message_id.isnot(None),
            )
            .order_by(Message.created_at.asc())
            .first()
        )
        assert inbound_message is not None
        inbound_message.phone_number_id = None
        inbound_message.payload = {
            "provider": "mock",
            "provider_message_id": inbound_message.provider_message_id,
            "provider_payload": {
                "metadata": {
                    "waba_id": "waba-conversation-nested-scope-1",
                    "phone_number_id": "pn-conversation-nested-scope-1",
                    "provider_media_id": "provider-media-nested-scope-1",
                }
            },
        }
        session.commit()

    messages_response = client.get(
        "/api/conversations/conversation-nested-scope-account-1/conv-nested-scope-1/messages",
    )

    assert messages_response.status_code == 200
    messages = messages_response.json()
    inbound_message = next(message for message in messages if message["direction"] == "inbound")
    assert inbound_message["waba_id"] == "waba-conversation-nested-scope-1"
    assert inbound_message["phone_number_id"] == "pn-conversation-nested-scope-1"
    assert inbound_message["provider_media_id"] == "provider-media-nested-scope-1"


def test_list_conversations_filters_by_phone_number_id_within_account_scope(
    client: TestClient,
) -> None:
    _create_manual_meta_account(
        client,
        account_id="conversation-phone-filter-account-1",
        portfolio_id="portfolio-phone-filter-1",
        waba_id="waba-phone-filter-1",
        phone_numbers=[
            {
                "phone_number_id": "pn-conversation-filter-1a",
                "display_phone_number": "+1 555 000 1001",
                "verified_name": "Conversation Filter A",
                "quality_rating": "GREEN",
                "is_registered": True,
            },
            {
                "phone_number_id": "pn-conversation-filter-1b",
                "display_phone_number": "+1 555 000 1002",
                "verified_name": "Conversation Filter B",
                "quality_rating": "GREEN",
                "is_registered": True,
            },
        ],
    )
    _post_mock_inbound_message(
        client,
        account_id="conversation-phone-filter-account-1",
        conversation_id="conv-phone-filter-1a",
        user_id="user-phone-filter-1a",
        text="hello from phone a",
        phone_number_id="pn-conversation-filter-1a",
    )
    _post_mock_inbound_message(
        client,
        account_id="conversation-phone-filter-account-1",
        conversation_id="conv-phone-filter-1b",
        user_id="user-phone-filter-1b",
        text="hello from phone b",
        phone_number_id="pn-conversation-filter-1b",
    )

    response = client.get(
        "/api/conversations",
        params={
            "account_id": "conversation-phone-filter-account-1",
            "phone_number_id": "pn-conversation-filter-1a",
        },
    )

    assert response.status_code == 200
    conversations = response.json()["items"]
    assert {item["conversation_id"] for item in conversations} == {"conv-phone-filter-1a"}
    assert all(item["phone_number_id"] == "pn-conversation-filter-1a" for item in conversations)


def test_list_conversations_phone_number_filter_still_respects_actor_account_scope(
    client: TestClient,
) -> None:
    _create_manual_meta_account(
        client,
        account_id="conversation-actor-scope-account-a",
        portfolio_id="portfolio-actor-scope-a",
        waba_id="waba-actor-scope-a",
        phone_numbers=[
            {
                "phone_number_id": "pn-actor-scope-a",
                "display_phone_number": "+1 555 000 1101",
                "verified_name": "Actor Scope A",
                "quality_rating": "GREEN",
                "is_registered": True,
            }
        ],
    )
    _create_manual_meta_account(
        client,
        account_id="conversation-actor-scope-account-b",
        portfolio_id="portfolio-actor-scope-b",
        waba_id="waba-actor-scope-b",
        phone_numbers=[
            {
                "phone_number_id": "pn-actor-scope-b",
                "display_phone_number": "+1 555 000 1102",
                "verified_name": "Actor Scope B",
                "quality_rating": "GREEN",
                "is_registered": True,
            }
        ],
    )
    _post_mock_inbound_message(
        client,
        account_id="conversation-actor-scope-account-a",
        conversation_id="conv-actor-scope-a",
        user_id="user-actor-scope-a",
        text="hello from scope a",
        phone_number_id="pn-actor-scope-a",
    )
    _post_mock_inbound_message(
        client,
        account_id="conversation-actor-scope-account-b",
        conversation_id="conv-actor-scope-b",
        user_id="user-actor-scope-b",
        text="hello from scope b",
        phone_number_id="pn-actor-scope-b",
    )

    super_admin_response = client.get(
        "/api/conversations",
        params={"phone_number_id": "pn-actor-scope-b"},
    )
    assert super_admin_response.status_code == 200
    assert {item["conversation_id"] for item in super_admin_response.json()["items"]} == {
        "conv-actor-scope-b"
    }

    scoped_response = client.get(
        "/api/conversations",
        params={"phone_number_id": "pn-actor-scope-b"},
        headers={
            "X-Actor-Id": "operator-conversation-scope-a",
            "X-Actor-Role": "operator",
            "X-Actor-Account-Ids": "conversation-actor-scope-account-a",
        },
    )

    assert scoped_response.status_code == 200
    assert scoped_response.json()["items"] == []


def test_list_conversations_rejects_mismatched_waba_and_phone_scope_filters(
    client: TestClient,
) -> None:
    _create_manual_meta_account(
        client,
        account_id="conversation-scope-mismatch-account-1",
        portfolio_id="portfolio-conversation-scope-mismatch-1",
        waba_id="waba-conversation-scope-mismatch-1",
        phone_numbers=[
            {
                "phone_number_id": "pn-conversation-scope-mismatch-1",
                "display_phone_number": "+1 555 000 1151",
                "verified_name": "Conversation Scope Mismatch",
                "quality_rating": "GREEN",
                "is_registered": True,
            }
        ],
    )
    _post_mock_inbound_message(
        client,
        account_id="conversation-scope-mismatch-account-1",
        conversation_id="conv-conversation-scope-mismatch-1",
        user_id="user-conversation-scope-mismatch-1",
        text="hello from mismatched scope",
        phone_number_id="pn-conversation-scope-mismatch-1",
    )

    response = client.get(
        "/api/conversations",
        params={
            "account_id": "conversation-scope-mismatch-account-1",
            "waba_id": "waba-conversation-scope-mismatch-other",
            "phone_number_id": "pn-conversation-scope-mismatch-1",
        },
    )

    assert response.status_code == 400
    assert "belongs to WABA 'waba-conversation-scope-mismatch-1'" in str(
        response.json()["detail"]
    )


def test_list_conversations_rejects_account_and_phone_scope_mismatch_for_accessible_accounts(
    client: TestClient,
) -> None:
    _create_manual_meta_account(
        client,
        account_id="conversation-account-scope-a",
        portfolio_id="portfolio-conversation-account-scope-a",
        waba_id="waba-conversation-account-scope-a",
        phone_numbers=[
            {
                "phone_number_id": "pn-conversation-account-scope-a",
                "display_phone_number": "+1 555 000 1161",
                "verified_name": "Conversation Account Scope A",
                "quality_rating": "GREEN",
                "is_registered": True,
            }
        ],
    )
    _create_manual_meta_account(
        client,
        account_id="conversation-account-scope-b",
        portfolio_id="portfolio-conversation-account-scope-b",
        waba_id="waba-conversation-account-scope-b",
        phone_numbers=[
            {
                "phone_number_id": "pn-conversation-account-scope-b",
                "display_phone_number": "+1 555 000 1162",
                "verified_name": "Conversation Account Scope B",
                "quality_rating": "GREEN",
                "is_registered": True,
            }
        ],
    )
    _post_mock_inbound_message(
        client,
        account_id="conversation-account-scope-a",
        conversation_id="conv-conversation-account-scope-a",
        user_id="user-conversation-account-scope-a",
        text="hello from account scope a",
        phone_number_id="pn-conversation-account-scope-a",
    )
    _post_mock_inbound_message(
        client,
        account_id="conversation-account-scope-b",
        conversation_id="conv-conversation-account-scope-b",
        user_id="user-conversation-account-scope-b",
        text="hello from account scope b",
        phone_number_id="pn-conversation-account-scope-b",
    )

    response = client.get(
        "/api/conversations",
        params={
            "account_id": "conversation-account-scope-a",
            "phone_number_id": "pn-conversation-account-scope-b",
        },
        headers={
            "X-Actor-Id": "operator-conversation-account-scope",
            "X-Actor-Role": "operator",
            "X-Actor-Account-Ids": (
                "conversation-account-scope-a,conversation-account-scope-b"
            ),
        },
    )

    assert response.status_code == 400
    assert "belongs to account 'conversation-account-scope-b'" in str(
        response.json()["detail"]
    )


def test_list_conversations_without_phone_number_filter_preserves_existing_account_behavior(
    client: TestClient,
) -> None:
    _create_manual_meta_account(
        client,
        account_id="conversation-phone-unfiltered-account-1",
        portfolio_id="portfolio-phone-unfiltered-1",
        waba_id="waba-phone-unfiltered-1",
        phone_numbers=[
            {
                "phone_number_id": "pn-conversation-unfiltered-1a",
                "display_phone_number": "+1 555 000 1201",
                "verified_name": "Conversation Unfiltered A",
                "quality_rating": "GREEN",
                "is_registered": True,
            },
            {
                "phone_number_id": "pn-conversation-unfiltered-1b",
                "display_phone_number": "+1 555 000 1202",
                "verified_name": "Conversation Unfiltered B",
                "quality_rating": "GREEN",
                "is_registered": True,
            },
        ],
    )
    _post_mock_inbound_message(
        client,
        account_id="conversation-phone-unfiltered-account-1",
        conversation_id="conv-phone-unfiltered-1a",
        user_id="user-phone-unfiltered-1a",
        text="hello from unfiltered phone a",
        phone_number_id="pn-conversation-unfiltered-1a",
    )
    _post_mock_inbound_message(
        client,
        account_id="conversation-phone-unfiltered-account-1",
        conversation_id="conv-phone-unfiltered-1b",
        user_id="user-phone-unfiltered-1b",
        text="hello from unfiltered phone b",
        phone_number_id="pn-conversation-unfiltered-1b",
    )

    response = client.get(
        "/api/conversations",
        params={"account_id": "conversation-phone-unfiltered-account-1"},
    )

    assert response.status_code == 200
    conversations = response.json()["items"]
    assert {item["conversation_id"] for item in conversations} == {
        "conv-phone-unfiltered-1a",
        "conv-phone-unfiltered-1b",
    }


def test_list_conversations_filters_by_waba_id_within_account_scope(
    client: TestClient,
) -> None:
    _create_manual_meta_account(
        client,
        account_id="conversation-waba-filter-account-1",
        portfolio_id="portfolio-waba-filter-1a",
        waba_id="waba-conversation-filter-1a",
        phone_numbers=[
            {
                "phone_number_id": "pn-conversation-waba-1a",
                "display_phone_number": "+1 555 000 1301",
                "verified_name": "Conversation WABA A",
                "quality_rating": "GREEN",
                "is_registered": True,
            }
        ],
    )
    _create_manual_meta_account(
        client,
        account_id="conversation-waba-filter-account-1",
        portfolio_id="portfolio-waba-filter-1b",
        waba_id="waba-conversation-filter-1b",
        phone_numbers=[
            {
                "phone_number_id": "pn-conversation-waba-1b",
                "display_phone_number": "+1 555 000 1302",
                "verified_name": "Conversation WABA B",
                "quality_rating": "GREEN",
                "is_registered": True,
            }
        ],
    )
    _post_mock_inbound_message(
        client,
        account_id="conversation-waba-filter-account-1",
        conversation_id="conv-waba-filter-1a",
        user_id="user-waba-filter-1a",
        text="hello from waba a",
        phone_number_id="pn-conversation-waba-1a",
    )
    _post_mock_inbound_message(
        client,
        account_id="conversation-waba-filter-account-1",
        conversation_id="conv-waba-filter-1b",
        user_id="user-waba-filter-1b",
        text="hello from waba b",
        phone_number_id="pn-conversation-waba-1b",
    )

    response = client.get(
        "/api/conversations",
        params={
            "account_id": "conversation-waba-filter-account-1",
            "waba_id": "waba-conversation-filter-1a",
        },
    )

    assert response.status_code == 200
    conversations = response.json()["items"]
    assert {item["conversation_id"] for item in conversations} == {"conv-waba-filter-1a"}
    assert all(item["waba_id"] == "waba-conversation-filter-1a" for item in conversations)
    assert all(
        item["phone_number_id"] == "pn-conversation-waba-1a" for item in conversations
    )


def test_conversation_summary_prefers_phone_snapshot_waba_when_relationship_drifts(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _create_manual_meta_account(
        client,
        account_id="conversation-waba-snapshot-account-1",
        portfolio_id="portfolio-conversation-snapshot-1",
        waba_id="waba-conversation-snapshot-1",
        phone_numbers=[
            {
                "phone_number_id": "pn-conversation-snapshot-1",
                "display_phone_number": "+1 555 000 1351",
                "verified_name": "Conversation Snapshot Number",
                "quality_rating": "GREEN",
                "is_registered": True,
            }
        ],
    )
    _post_mock_inbound_message(
        client,
        account_id="conversation-waba-snapshot-account-1",
        conversation_id="conv-waba-snapshot-1",
        user_id="user-waba-snapshot-1",
        text="hello from snapshot scope",
        phone_number_id="pn-conversation-snapshot-1",
    )

    with db_session_factory() as session:
        waba_account = (
            session.query(WhatsAppBusinessAccount)
            .filter(
                WhatsAppBusinessAccount.account_id == "conversation-waba-snapshot-account-1",
                WhatsAppBusinessAccount.waba_id == "waba-conversation-snapshot-1",
            )
            .one()
        )
        waba_account.waba_id = "waba-conversation-relationship-drifted-1"
        session.commit()

    response = client.get(
        "/api/conversations",
        params={"account_id": "conversation-waba-snapshot-account-1"},
    )

    assert response.status_code == 200
    conversations = response.json()["items"]
    assert len(conversations) == 1
    assert conversations[0]["conversation_id"] == "conv-waba-snapshot-1"
    assert conversations[0]["phone_number_id"] == "pn-conversation-snapshot-1"
    assert conversations[0]["waba_id"] == "waba-conversation-snapshot-1"


def test_list_conversations_waba_filter_still_respects_actor_account_scope(
    client: TestClient,
) -> None:
    _create_manual_meta_account(
        client,
        account_id="conversation-waba-scope-account-a",
        portfolio_id="portfolio-waba-scope-a",
        waba_id="waba-conversation-scope-a",
        phone_numbers=[
            {
                "phone_number_id": "pn-conversation-scope-a",
                "display_phone_number": "+1 555 000 1401",
                "verified_name": "Conversation Scope A",
                "quality_rating": "GREEN",
                "is_registered": True,
            }
        ],
    )
    _create_manual_meta_account(
        client,
        account_id="conversation-waba-scope-account-b",
        portfolio_id="portfolio-waba-scope-b",
        waba_id="waba-conversation-scope-b",
        phone_numbers=[
            {
                "phone_number_id": "pn-conversation-scope-b",
                "display_phone_number": "+1 555 000 1402",
                "verified_name": "Conversation Scope B",
                "quality_rating": "GREEN",
                "is_registered": True,
            }
        ],
    )
    _post_mock_inbound_message(
        client,
        account_id="conversation-waba-scope-account-a",
        conversation_id="conv-waba-scope-a",
        user_id="user-waba-scope-a",
        text="hello from scoped waba a",
        phone_number_id="pn-conversation-scope-a",
    )
    _post_mock_inbound_message(
        client,
        account_id="conversation-waba-scope-account-b",
        conversation_id="conv-waba-scope-b",
        user_id="user-waba-scope-b",
        text="hello from scoped waba b",
        phone_number_id="pn-conversation-scope-b",
    )

    super_admin_response = client.get(
        "/api/conversations",
        params={"waba_id": "waba-conversation-scope-b"},
    )
    assert super_admin_response.status_code == 200
    payload = super_admin_response.json()["items"]
    assert {item["conversation_id"] for item in payload} == {"conv-waba-scope-b"}
    assert payload[0]["account_id"] == "conversation-waba-scope-account-b"
    assert payload[0]["waba_id"] == "waba-conversation-scope-b"

    scoped_response = client.get(
        "/api/conversations",
        params={"waba_id": "waba-conversation-scope-b"},
        headers={
            "X-Actor-Id": "operator-conversation-waba-scope-a",
            "X-Actor-Role": "operator",
            "X-Actor-Account-Ids": "conversation-waba-scope-account-a",
        },
    )

    assert scoped_response.status_code == 400
    assert (
        scoped_response.json()["detail"]
        == "WABA 'waba-conversation-scope-b' is outside the accessible account scope."
    )


def test_list_conversations_can_filter_by_latest_intent_and_handover_flag(
    client: TestClient,
) -> None:
    human_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "intent-filter-account-1",
            "conversation_id": "intent-filter-conv-human",
            "user_id": "intent-filter-user-human",
            "text": "I need a human agent right now.",
            "mode": "ai",
            "language_hint": "en",
        },
    )
    assert human_response.status_code == 200

    faq_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "intent-filter-account-1",
            "conversation_id": "intent-filter-conv-faq",
            "user_id": "intent-filter-user-faq",
            "text": "What is your refund policy?",
            "mode": "ai",
            "language_hint": "en",
        },
    )
    assert faq_response.status_code == 200

    handover_filtered = client.get(
        "/api/conversations",
        params={
            "account_id": "intent-filter-account-1",
            "latest_handover_recommended": "true",
        },
    )
    assert handover_filtered.status_code == 200
    handover_payload = handover_filtered.json()["items"]
    assert len(handover_payload) == 1
    assert handover_payload[0]["conversation_id"] == "intent-filter-conv-human"

    intent_filtered = client.get(
        "/api/conversations",
        params={
            "account_id": "intent-filter-account-1",
            "latest_intent_name": "human_handover_request",
        },
    )
    assert intent_filtered.status_code == 200
    intent_payload = intent_filtered.json()["items"]
    assert len(intent_payload) == 1
    assert intent_payload[0]["conversation_id"] == "intent-filter-conv-human"


def test_conversation_service_prefers_phone_number_waba_snapshot_over_relationship() -> None:
    phone_number = SimpleNamespace(
        waba_id="waba-snapshot-conversation",
        waba_account=SimpleNamespace(waba_id="waba-relationship-conversation"),
    )

    assert (
        ConversationService._resolve_phone_number_waba_id(phone_number)
        == "waba-snapshot-conversation"
    )


class TestConversationTags:
    def _create_account_and_conversation(self, client: TestClient, suffix: str = "") -> str:
        """Create meta account and send mock inbound message, return internal conversation_id."""
        account_id = f"tags-test-account{suffix}"
        _create_manual_meta_account(
            client,
            account_id=account_id,
            portfolio_id=f"portfolio-tags-1{suffix}",
            waba_id=f"waba-tags-1{suffix}",
            phone_numbers=[
                {
                    "phone_number_id": f"pn-tags-1{suffix}",
                    "display_phone_number": "+1 555 000 0001",
                    "verified_name": "Tags Test",
                    "quality_rating": "GREEN",
                    "is_registered": True,
                }
            ],
        )
        _post_mock_inbound_message(
            client,
            account_id=account_id,
            conversation_id=f"conv-tags-1{suffix}",
            user_id=f"user-tags-1{suffix}",
            text="Test conversation for tags",
        )
        list_resp = client.get(f"/api/conversations?account_id={account_id}")
        assert list_resp.status_code == 200
        items = list_resp.json().get("items", [])
        assert len(items) > 0, "No conversations created"
        return items[0]["conversation_id"], account_id

    def test_get_tags_returns_list(self, client: TestClient) -> None:
        internal_conv_id, account_id = self._create_account_and_conversation(client, "")
        resp = client.get(f"/api/conversations/{account_id}/{internal_conv_id}/tags")
        assert resp.status_code == 200
        data = resp.json()
        assert "tags" in data
        assert isinstance(data["tags"], list)

    def test_update_tags(self, client: TestClient) -> None:
        internal_conv_id, account_id = self._create_account_and_conversation(client, "_update")
        resp = client.put(
            f"/api/conversations/{account_id}/{internal_conv_id}/tags",
            json={"tags": ["VIP", "urgent", "complaint"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert set(data["tags"]) == {"VIP", "urgent", "complaint"}

    def test_get_tags_after_update(self, client: TestClient) -> None:
        internal_conv_id, account_id = self._create_account_and_conversation(client, "_getafter")
        # First update tags
        put_resp = client.put(
            f"/api/conversations/{account_id}/{internal_conv_id}/tags",
            json={"tags": ["VIP", "urgent", "complaint"]},
        )
        assert put_resp.status_code == 200
        # Then verify via GET
        resp = client.get(f"/api/conversations/{account_id}/{internal_conv_id}/tags")
        assert resp.status_code == 200
        data = resp.json()
        assert set(data["tags"]) == {"VIP", "urgent", "complaint"}

    def test_tags_include_conversation_id_and_account_id(self, client: TestClient) -> None:
        internal_conv_id, account_id = self._create_account_and_conversation(client, "_fields")
        resp = client.get(f"/api/conversations/{account_id}/{internal_conv_id}/tags")
        assert resp.status_code == 200
        data = resp.json()
        assert data["conversation_id"] == internal_conv_id
        assert data["account_id"] == account_id

    def test_list_conversations_filters_by_tag(self, client: TestClient) -> None:
        account_id = "tags-filter-account"
        _create_manual_meta_account(
            client,
            account_id=account_id,
            portfolio_id="portfolio-tags-2",
            waba_id="waba-tags-2",
            phone_numbers=[
                {
                    "phone_number_id": "pn-tags-2",
                    "display_phone_number": "+1 555 000 0002",
                    "verified_name": "Tags Filter",
                    "quality_rating": "GREEN",
                    "is_registered": True,
                }
            ],
        )
        _post_mock_inbound_message(
            client,
            account_id=account_id,
            conversation_id="conv-tags-filter",
            user_id="user-tags-filter",
            text="Filter by tag test",
        )
        list_resp = client.get(f"/api/conversations?account_id={account_id}")
        items = list_resp.json().get("items", [])
        assert len(items) > 0
        tag_conv_id = items[0]["conversation_id"]
        client.put(
            f"/api/conversations/{account_id}/{tag_conv_id}/tags",
            json={"tags": ["VIP"]},
        )
        resp = client.get(f"/api/conversations?account_id={account_id}&tag=VIP")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
