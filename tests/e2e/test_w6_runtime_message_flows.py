from __future__ import annotations

from collections.abc import Callable
from uuid import uuid4

from fastapi.testclient import TestClient

from app.providers.meta_management.base import MetaPhoneNumberRecord
from tests.conftest import StubMetaManagementProvider


def _mock_inbound(
    client: TestClient,
    *,
    account_id: str,
    conversation_id: str,
    user_id: str,
    text: str,
    mode: str = "echo",
    **kwargs: object,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "account_id": account_id,
        "conversation_id": conversation_id,
        "user_id": user_id,
        "text": text,
        "mode": mode,
    }
    payload.update(kwargs)
    response = client.post("/dev/mock/inbound-message", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def _conversation_items(client: TestClient, *, account_id: str) -> list[dict[str, object]]:
    response = client.get("/api/conversations", params={"account_id": account_id})
    assert response.status_code == 200, response.text
    payload = response.json()
    assert isinstance(payload, dict)
    items = payload.get("items")
    assert isinstance(items, list)
    return items


def _messages(
    client: TestClient,
    *,
    account_id: str,
    conversation_id: str,
) -> list[dict[str, object]]:
    response = client.get(f"/api/conversations/{account_id}/{conversation_id}/messages")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert isinstance(payload, list)
    return payload


def _ai_status(
    client: TestClient,
    *,
    account_id: str,
    conversation_id: str,
) -> dict[str, object]:
    response = client.get(
        f"/api/runtime/conversations/{conversation_id}/ai-status",
        params={"account_id": account_id},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _set_account_ai(client: TestClient, *, account_id: str, enabled: bool) -> dict[str, object]:
    response = client.post(
        f"/api/runtime/accounts/{account_id}/ai",
        json={"enabled": enabled},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_w6_e2e_message_flow_and_handover_cycle(client: TestClient) -> None:
    uid = uuid4().hex[:8]
    account_id = f"w6-msg-{uid}"
    conversation_id = f"w6-conv-{uid}"
    user_id = f"w6-user-{uid}"
    agent_id = f"w6-agent-{uid}"

    inbound = _mock_inbound(
        client,
        account_id=account_id,
        conversation_id=conversation_id,
        user_id=user_id,
        text="hello from w6",
        mode="echo",
    )
    assert inbound["outbound"]["delivery_mode"] == "echo"
    assert inbound["outbound"]["text"] == "Echo: hello from w6"

    items = _conversation_items(client, account_id=account_id)
    conversation = next(item for item in items if item["conversation_id"] == conversation_id)
    assert conversation["status"] == "open"
    assert conversation["management_mode"] == "ai_managed"

    message_rows = _messages(client, account_id=account_id, conversation_id=conversation_id)
    assert {row["direction"] for row in message_rows} == {"inbound", "outbound"}

    register_agent = client.post(
        "/api/runtime/agents",
        json={
            "agent_id": agent_id,
            "display_name": "W6 Agent",
            "status": "online",
            "is_active": True,
        },
    )
    assert register_agent.status_code == 200, register_agent.text

    assign = client.post(
        f"/api/conversations/{account_id}/{conversation_id}/assignment",
        json={
            "agent_id": agent_id,
            "assigned_by_agent_id": agent_id,
            "reason": "w6_handover",
        },
    )
    assert assign.status_code == 200, assign.text
    assert assign.json()["management_mode"] == "human_managed"

    after_takeover = _ai_status(client, account_id=account_id, conversation_id=conversation_id)
    assert after_takeover["effective_ai_enabled"] is False
    assert after_takeover["management_mode"] == "human_managed"

    human_reply = client.post(
        f"/api/conversations/{account_id}/{conversation_id}/messages/outbound",
        json={"text": "manual follow-up", "agent_id": agent_id},
    )
    assert human_reply.status_code == 200, human_reply.text

    restore = client.post(
        f"/api/runtime/conversations/{conversation_id}/handover",
        params={"account_id": account_id},
        json={
            "management_mode": "ai_managed",
            "agent_id": agent_id,
            "reason": "w6_resume_ai",
        },
    )
    assert restore.status_code == 200, restore.text
    assert restore.json()["management_mode"] == "ai_managed"

    after_restore = _ai_status(client, account_id=account_id, conversation_id=conversation_id)
    assert after_restore["effective_ai_enabled"] is True


def test_w6_e2e_meta_signup_to_message_flow(
    client: TestClient,
    override_meta_management_provider: Callable[[TestClient, StubMetaManagementProvider], None],
) -> None:
    uid = uuid4().hex[:8]
    account_id = f"w6-meta-{uid}"
    waba_id = f"w6-waba-{uid}"
    portfolio_id = f"w6-portfolio-{uid}"
    phone_number_id = f"w6-pn-{uid}"

    override_meta_management_provider(
        client,
        StubMetaManagementProvider(
            sync_phone_numbers=[
                MetaPhoneNumberRecord(
                    phone_number_id=phone_number_id,
                    display_phone_number="+15550009999",
                    verified_name="W6 E2E",
                    quality_rating="GREEN",
                    is_registered=True,
                )
            ],
            completion_phone_number_ids=[phone_number_id],
            completion_resolved_waba_id=waba_id,
            completion_resolved_portfolio_id=portfolio_id,
        ),
    )

    session_response = client.post(
        "/api/meta/accounts/embedded-signup/session",
        json={
            "account_id": account_id,
            "display_name": "W6 Meta Account",
            "redirect_uri": "https://example.com/callback",
            "webhook_subscription": {
                "callback_url": "https://example.com/webhook",
                "verify_token": f"verify-{uid}",
                "app_id": "app-w6",
            },
        },
    )
    assert session_response.status_code == 200, session_response.text
    session_id = session_response.json()["session_id"]

    complete_response = client.post(
        f"/api/meta/accounts/embedded-signup/session/{session_id}/callback",
        json={
            "status": "completed",
            "waba_id": waba_id,
            "meta_business_portfolio_id": portfolio_id,
            "phone_number_ids": [phone_number_id],
            "authorization_code": "auth-code-w6",
            "system_user_access_token": "system-token-w6",
        },
    )
    assert complete_response.status_code == 200, complete_response.text

    subscriptions = client.post(
        f"/api/meta/accounts/{account_id}/wabas/{waba_id}/webhook-subscription",
        json={
            "callback_url": "https://example.com/webhook",
            "verify_token": f"verify-{uid}",
            "app_id": "app-w6",
        },
    )
    assert subscriptions.status_code == 200, subscriptions.text

    inbound = _mock_inbound(
        client,
        account_id=account_id,
        conversation_id=f"w6-meta-conv-{uid}",
        user_id=f"w6-meta-user-{uid}",
        text="meta onboarding hello",
        mode="echo",
        phone_number_id=phone_number_id,
        waba_id=waba_id,
    )
    assert inbound["outbound"]["text"] == "Echo: meta onboarding hello"

    phone_numbers = client.get(f"/api/meta/accounts/{account_id}/phone-numbers")
    assert phone_numbers.status_code == 200, phone_numbers.text
    assert any(
        row["phone_number_id"] == phone_number_id for row in phone_numbers.json()
    )


def test_w6_e2e_multi_account_ai_isolation(client: TestClient) -> None:
    uid = uuid4().hex[:8]
    account_a = f"w6-a-{uid}"
    account_b = f"w6-b-{uid}"
    conv_a = f"conv-a-{uid}"
    conv_b = f"conv-b-{uid}"

    _mock_inbound(
        client,
        account_id=account_a,
        conversation_id=conv_a,
        user_id=f"user-a-{uid}",
        text="echo from account a",
        mode="echo",
    )
    _mock_inbound(
        client,
        account_id=account_b,
        conversation_id=conv_b,
        user_id=f"user-b-{uid}",
        text="echo from account b",
        mode="echo",
    )

    _set_account_ai(client, account_id=account_a, enabled=False)

    ai_a = _ai_status(client, account_id=account_a, conversation_id=conv_a)
    ai_b = _ai_status(client, account_id=account_b, conversation_id=conv_b)
    assert ai_a["effective_ai_enabled"] is False
    assert ai_b["effective_ai_enabled"] is True

    routed_a = _mock_inbound(
        client,
        account_id=account_a,
        conversation_id=conv_a,
        user_id=f"user-a-{uid}",
        text="need billing help",
        mode="ai",
    )
    routed_b = _mock_inbound(
        client,
        account_id=account_b,
        conversation_id=conv_b,
        user_id=f"user-b-{uid}",
        text="need shipping help",
        mode="ai",
    )
    assert routed_a["outbound"]["delivery_mode"] == "manual_queue"
    assert routed_b["outbound"]["delivery_mode"] in {
        "rule_auto_reply",
        "ai_async_queued",
        "handover_recommended",
    }

    texts_a = [row.get("original_text", "") for row in _messages(client, account_id=account_a, conversation_id=conv_a)]
    texts_b = [row.get("original_text", "") for row in _messages(client, account_id=account_b, conversation_id=conv_b)]
    assert all("account b" not in str(text).lower() for text in texts_a)
    assert all("account a" not in str(text).lower() for text in texts_b)
