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


def _get_conversation_items(
    client: TestClient,
    *,
    account_id: str,
) -> list[dict[str, object]]:
    response = client.get("/api/conversations", params={"account_id": account_id})
    assert response.status_code == 200, response.text
    payload = response.json()
    assert isinstance(payload, dict)
    items = payload.get("items")
    assert isinstance(items, list)
    return items


def _get_messages(
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


def _set_account_ai(client: TestClient, *, account_id: str, enabled: bool) -> dict[str, object]:
    response = client.post(
        f"/api/runtime/accounts/{account_id}/ai",
        json={"enabled": enabled},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _get_ai_status(
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


def test_legacy_e2e_message_flow_uses_current_conversation_payload(client: TestClient) -> None:
    uid = uuid4().hex[:8]
    account_id = f"legacy-msg-{uid}"
    conversation_id = f"legacy-conv-{uid}"
    user_id = f"legacy-user-{uid}"

    result = _mock_inbound(
        client,
        account_id=account_id,
        conversation_id=conversation_id,
        user_id=user_id,
        text="Hello from migrated legacy E2E",
        mode="echo",
    )
    assert result["outbound"]["text"] == "Echo: Hello from migrated legacy E2E"

    conversations = _get_conversation_items(client, account_id=account_id)
    conversation = next(item for item in conversations if item["conversation_id"] == conversation_id)
    assert conversation["status"] == "open"
    assert conversation["management_mode"] == "ai_managed"

    messages = _get_messages(client, account_id=account_id, conversation_id=conversation_id)
    assert any(row["direction"] == "inbound" for row in messages)
    assert any(row["direction"] == "outbound" for row in messages)

    ai_result = _mock_inbound(
        client,
        account_id=account_id,
        conversation_id=conversation_id,
        user_id=user_id,
        text="I need help with my order",
        mode="ai",
    )
    assert ai_result["outbound"]["delivery_mode"] in {
        "rule_auto_reply",
        "handover_recommended",
        "ai_async_queued",
    }


def test_legacy_e2e_human_handover_cycle_matches_current_runtime(client: TestClient) -> None:
    uid = uuid4().hex[:8]
    account_id = f"legacy-ho-{uid}"
    conversation_id = f"legacy-ho-conv-{uid}"
    user_id = f"legacy-ho-user-{uid}"
    agent_id = f"legacy-agent-{uid}"

    register = client.post(
        "/api/runtime/agents",
        json={
            "agent_id": agent_id,
            "display_name": "Legacy Migrated Agent",
            "status": "online",
            "is_active": True,
        },
    )
    assert register.status_code == 200, register.text

    _mock_inbound(
        client,
        account_id=account_id,
        conversation_id=conversation_id,
        user_id=user_id,
        text="Need human help",
    )

    before = _get_ai_status(client, account_id=account_id, conversation_id=conversation_id)
    assert before["effective_ai_enabled"] is True

    assign = client.post(
        f"/api/conversations/{account_id}/{conversation_id}/assignment",
        json={
            "agent_id": agent_id,
            "assigned_by_agent_id": agent_id,
            "reason": "legacy_migrated_takeover",
        },
    )
    assert assign.status_code == 200, assign.text
    assert assign.json()["management_mode"] == "human_managed"

    after_takeover = _get_ai_status(client, account_id=account_id, conversation_id=conversation_id)
    assert after_takeover["effective_ai_enabled"] is False

    reply = client.post(
        f"/api/conversations/{account_id}/{conversation_id}/messages/outbound",
        json={"text": "Human agent reply", "agent_id": agent_id},
    )
    assert reply.status_code == 200, reply.text

    restore = client.post(
        f"/api/runtime/conversations/{conversation_id}/handover",
        params={"account_id": account_id},
        json={
            "management_mode": "ai_managed",
            "agent_id": agent_id,
            "reason": "legacy_migrated_restore",
        },
    )
    assert restore.status_code == 200, restore.text
    assert restore.json()["management_mode"] == "ai_managed"

    after_restore = _get_ai_status(client, account_id=account_id, conversation_id=conversation_id)
    assert after_restore["effective_ai_enabled"] is True


def test_legacy_e2e_meta_onboarding_flow_matches_current_meta_routes(
    client: TestClient,
    override_meta_management_provider: Callable[[TestClient, StubMetaManagementProvider], None],
) -> None:
    uid = uuid4().hex[:8]
    account_id = f"legacy-meta-{uid}"
    waba_id = f"legacy-waba-{uid}"
    portfolio_id = f"legacy-portfolio-{uid}"
    phone_number_id = f"legacy-pn-{uid}"

    override_meta_management_provider(
        client,
        StubMetaManagementProvider(
            sync_phone_numbers=[
                MetaPhoneNumberRecord(
                    phone_number_id=phone_number_id,
                    display_phone_number="+15550001234",
                    verified_name="Legacy Migrated",
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
            "display_name": "Legacy Migrated Meta",
            "redirect_uri": "https://example.com/callback",
            "webhook_subscription": {
                "callback_url": f"https://example.com/webhooks/{uid}",
                "verify_token": f"verify-{uid}",
                "app_id": "app-legacy",
            },
        },
    )
    assert session_response.status_code == 200, session_response.text
    session_id = session_response.json()["session_id"]

    callback = client.post(
        f"/api/meta/accounts/embedded-signup/session/{session_id}/callback",
        json={
            "status": "completed",
            "waba_id": waba_id,
            "meta_business_portfolio_id": portfolio_id,
            "phone_number_ids": [phone_number_id],
            "authorization_code": "legacy-auth-code",
            "system_user_access_token": "legacy-system-token",
        },
    )
    assert callback.status_code == 200, callback.text

    subscription = client.post(
        f"/api/meta/accounts/{account_id}/wabas/{waba_id}/webhook-subscription",
        json={
            "callback_url": f"https://example.com/webhooks/{uid}",
            "verify_token": f"verify-{uid}",
            "app_id": "app-legacy",
        },
    )
    assert subscription.status_code == 200, subscription.text

    inbound = _mock_inbound(
        client,
        account_id=account_id,
        conversation_id=f"legacy-meta-conv-{uid}",
        user_id=f"legacy-meta-user-{uid}",
        text="Order inquiry from legacy migrated meta flow",
        mode="echo",
        phone_number_id=phone_number_id,
        waba_id=waba_id,
    )
    assert inbound["outbound"]["text"] == "Echo: Order inquiry from legacy migrated meta flow"


def test_legacy_e2e_multi_account_concurrency_uses_current_list_payload(client: TestClient) -> None:
    uid = uuid4().hex[:8]
    account_a = f"legacy-multi-a-{uid}"
    account_b = f"legacy-multi-b-{uid}"
    conv_a = f"legacy-conv-a-{uid}"
    conv_b = f"legacy-conv-b-{uid}"

    result_a = _mock_inbound(
        client,
        account_id=account_a,
        conversation_id=conv_a,
        user_id=f"legacy-user-a-{uid}",
        text="Message from account A",
        mode="echo",
    )
    result_b = _mock_inbound(
        client,
        account_id=account_b,
        conversation_id=conv_b,
        user_id=f"legacy-user-b-{uid}",
        text="Message from account B",
        mode="echo",
    )
    assert "account A" in result_a["outbound"]["text"]
    assert "account B" in result_b["outbound"]["text"]

    convs_a = _get_conversation_items(client, account_id=account_a)
    convs_b = _get_conversation_items(client, account_id=account_b)
    assert any(item["conversation_id"] == conv_a for item in convs_a)
    assert any(item["conversation_id"] == conv_b for item in convs_b)

    _set_account_ai(client, account_id=account_a, enabled=False)

    ai_a = _get_ai_status(client, account_id=account_a, conversation_id=conv_a)
    ai_b = _get_ai_status(client, account_id=account_b, conversation_id=conv_b)
    assert ai_a["effective_ai_enabled"] is False
    assert ai_b["effective_ai_enabled"] is True

    result_a_ai = _mock_inbound(
        client,
        account_id=account_a,
        conversation_id=conv_a,
        user_id=f"legacy-user-a-{uid}",
        text="Help A with billing",
        mode="ai",
    )
    result_b_ai = _mock_inbound(
        client,
        account_id=account_b,
        conversation_id=conv_b,
        user_id=f"legacy-user-b-{uid}",
        text="Help B with shipping",
        mode="ai",
    )
    assert result_a_ai["outbound"]["delivery_mode"] == "manual_queue"
    assert result_b_ai["outbound"]["delivery_mode"] in {
        "rule_auto_reply",
        "ai_async_queued",
        "handover_recommended",
    }
