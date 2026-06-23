from fastapi.testclient import TestClient

from app.core.settings import get_settings
from app.services.queue_service import QueueService


def test_mock_inbound_message_echo(client: TestClient) -> None:
    response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "mock-account-1",
            "conversation_id": "conv-1",
            "user_id": "user-1",
            "text": "hola, pedido listo",
            "mode": "echo",
        },
    )

    assert response.status_code == 200
    assert response.json()["outbound"]["text"] == "Echo: hola, pedido listo"
    assert response.json()["translation"]["source_language"] == "es"
    assert response.json()["translation"]["console_text"] == "hola, pedido listo"
    assert response.json()["translation"]["translated"] is False


def test_mock_inbound_message_preserves_provider_scope_and_deduplicates_external_message_id(
    client: TestClient,
) -> None:
    first_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "mock-account-scope-1",
            "conversation_id": "conv-scope-1",
            "user_id": "user-scope-1",
            "text": "[image attachment]",
            "mode": "echo",
            "waba_id": "waba-mock-scope-1",
            "phone_number_id": "pn-mock-scope-1",
            "message_type": "image",
            "external_message_id": "mock-inbound-duplicate-1",
            "metadata": {
                "media_kind": "image",
                "has_meaningful_text": False,
            },
        },
    )
    assert first_response.status_code == 200
    assert "deduplicated" not in first_response.json()

    second_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "mock-account-scope-1",
            "conversation_id": "conv-scope-1",
            "user_id": "user-scope-1",
            "text": "[image attachment]",
            "mode": "echo",
            "waba_id": "waba-mock-scope-1",
            "phone_number_id": "pn-mock-scope-1",
            "message_type": "image",
            "external_message_id": "mock-inbound-duplicate-1",
            "metadata": {
                "media_kind": "image",
                "has_meaningful_text": False,
            },
        },
    )
    assert second_response.status_code == 200
    assert second_response.json()["deduplicated"] is True
    assert second_response.json()["existing_message_id"] is not None

    messages_response = client.get("/api/conversations/mock-account-scope-1/conv-scope-1/messages")
    assert messages_response.status_code == 200
    messages = messages_response.json()
    inbound_messages = [message for message in messages if message["direction"] == "inbound"]
    assert len(inbound_messages) == 1
    assert inbound_messages[0]["message_type"] == "image"
    assert inbound_messages[0]["payload"]["waba_id"] == "waba-mock-scope-1"
    assert inbound_messages[0]["payload"]["phone_number_id"] == "pn-mock-scope-1"
    assert inbound_messages[0]["payload"]["external_message_id"] == "mock-inbound-duplicate-1"
    assert inbound_messages[0]["payload"]["metadata"]["media_kind"] == "image"


def test_mock_inbound_message_respects_handover_pause(client: TestClient) -> None:
    register_agent_response = client.post(
        "/api/runtime/agents",
        json={
            "agent_id": "agent-7",
            "display_name": "Agent 7",
            "status": "online",
            "is_active": True,
        },
    )
    assert register_agent_response.status_code == 200

    bootstrap_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "mock-account-1",
            "conversation_id": "conv-2",
            "user_id": "user-2",
            "text": "hello",
            "mode": "echo",
        },
    )
    assert bootstrap_response.status_code == 200

    handover_response = client.post(
        "/api/runtime/conversations/conv-2/handover?account_id=mock-account-1",
        json={
            "management_mode": "human_managed",
            "agent_id": "agent-7",
            "reason": "mock_pause_setup",
        },
    )
    assert handover_response.status_code == 200

    response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "mock-account-1",
            "conversation_id": "conv-2",
            "user_id": "user-2",
            "text": "need help",
            "mode": "ai",
        },
    )

    assert response.status_code == 200
    assert response.json()["outbound"]["text"] is None
    assert response.json()["runtime"]["management_mode"] == "human_managed"
    assert response.json()["runtime"]["effective_ai_enabled"] is False
    assert response.json()["runtime"]["primary_blocking_reason"]["code"] == "human_managed"


def test_mock_inbound_message_respects_paused_management_mode(client: TestClient) -> None:
    register_agent_response = client.post(
        "/api/runtime/agents",
        json={
            "agent_id": "agent-paused-1",
            "display_name": "Paused Agent",
            "status": "online",
            "is_active": True,
        },
    )
    assert register_agent_response.status_code == 200

    bootstrap_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "mock-account-paused-1",
            "conversation_id": "conv-paused-1",
            "user_id": "user-paused-1",
            "text": "hello",
            "mode": "echo",
        },
    )
    assert bootstrap_response.status_code == 200

    handover_response = client.post(
        "/api/runtime/conversations/conv-paused-1/handover?account_id=mock-account-paused-1",
        json={
            "management_mode": "human_managed",
            "agent_id": "agent-paused-1",
            "reason": "manual_takeover",
        },
    )
    assert handover_response.status_code == 200

    pause_response = client.post(
        "/api/runtime/conversations/conv-paused-1/handover?account_id=mock-account-paused-1",
        json={
            "management_mode": "paused",
            "agent_id": "agent-paused-1",
            "reason": "manual_pause",
        },
    )
    assert pause_response.status_code == 200
    assert pause_response.json()["management_mode"] == "paused"

    response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "mock-account-paused-1",
            "conversation_id": "conv-paused-1",
            "user_id": "user-paused-1",
            "text": "please queue no AI",
            "mode": "ai",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["queue"] is None
    assert payload["outbound"]["text"] is None
    assert payload["runtime"]["management_mode"] == "paused"
    assert payload["runtime"]["effective_ai_enabled"] is False
    assert payload["runtime"]["primary_blocking_reason"]["code"] == "paused"


def test_mock_inbound_message_handover_recommendation_skips_ai_queue(client: TestClient) -> None:
    response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "mock-account-intent-1",
            "conversation_id": "conv-intent-1",
            "user_id": "user-intent-1",
            "text": "I want to talk to a human agent now.",
            "mode": "ai",
            "language_hint": "en",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["queue"] is None
    assert payload["outbound"]["text"] is None
    assert payload["outbound"]["delivery_mode"] == "handover_recommended"
    assert payload["ai"]["provider"] == "intent_router"
    assert payload["ai"]["model"] == "human_handover_request"
    assert payload["intent"]["handover_recommended"] is True
    assert payload["intent"]["handover_reason"] == "customer_requested_human_support"

    messages_response = client.get("/api/conversations/mock-account-intent-1/conv-intent-1/messages")
    assert messages_response.status_code == 200
    messages = messages_response.json()
    assert [message["direction"] for message in messages] == ["inbound"]

    audit_response = client.get(
        "/api/runtime/audit-logs",
        params={
            "account_id": "mock-account-intent-1",
            "action": "support_intent_evaluated",
        },
    )
    assert audit_response.status_code == 200
    audit_logs = audit_response.json()
    assert len(audit_logs) == 1
    assert audit_logs[0]["payload"]["intent_name"] == "human_handover_request"


def test_mock_inbound_message_rule_hits_order_and_skips_ai_queue(client: TestClient) -> None:
    response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "demo-account-es",
            "conversation_id": "conv-rule-order-1",
            "user_id": "user-rule-order-1",
            "text": "Estado del pedido MOCK-1001",
            "mode": "ai",
            "language_hint": "es",
        },
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["queue"] is None
    assert payload["outbound"]["delivery_mode"] == "rule_auto_reply"
    assert payload["ai"]["provider"] == "rule_router"
    assert payload["ai"]["model"] == "order_lookup"
    assert payload["outbound"]["text"].startswith("[auto-translated en->es] Order MOCK-1001")

    stats_response = client.get("/api/queue/stats")
    assert stats_response.status_code == 200
    stats = stats_response.json()
    assert stats["queues"][0]["queued"] == 0


def test_mock_inbound_message_faq_hit_skips_ai_queue(client: TestClient) -> None:
    response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "demo-account-fr",
            "conversation_id": "conv-faq-1",
            "user_id": "user-faq-1",
            "text": "bonjour, quelle est votre politique de retour et remboursement ?",
            "mode": "ai",
            "language_hint": "fr",
        },
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["queue"] is None
    assert payload["outbound"]["delivery_mode"] == "rule_auto_reply"
    assert payload["ai"]["provider"] == "rule_router"
    assert payload["ai"]["model"] == "faq_refund_policy"
    assert payload["outbound"]["text"].startswith(
        "[auto-translated en->fr] Refund and return requests should be submitted"
    )

    audit_response = client.get(
        "/api/runtime/audit-logs",
        params={
            "account_id": "demo-account-fr",
            "action": "support_route_resolved",
        },
    )
    assert audit_response.status_code == 200
    audit_logs = audit_response.json()
    assert len(audit_logs) == 1
    assert audit_logs[0]["payload"]["route_name"] == "faq_refund_policy"


def test_mock_inbound_message_knowledge_base_hit_skips_ai_queue(client: TestClient) -> None:
    response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "demo-account-ar",
            "conversation_id": "conv-kb-1",
            "user_id": "user-kb-1",
            "text": "أريد تعديل الطلب وتغيير العنوان",
            "mode": "ai",
            "language_hint": "ar",
        },
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["queue"] is None
    assert payload["outbound"]["delivery_mode"] == "rule_auto_reply"
    assert payload["ai"]["provider"] == "rule_router"
    assert payload["ai"]["model"] == "knowledge_order_change"
    assert payload["outbound"]["text"].startswith(
        "[auto-translated en->ar] Orders can usually be changed before the warehouse starts packing."
    )


def test_mock_inbound_message_prefers_database_support_knowledge(client: TestClient) -> None:
    register_account_response = client.post(
        "/api/runtime/accounts",
        json={
            "account_id": "knowledge-account-runtime",
            "display_name": "Knowledge Runtime",
            "provider_type": "mock",
        },
    )
    assert register_account_response.status_code == 200

    create_response = client.post(
        "/api/runtime/support-knowledge",
        json={
            "account_id": "knowledge-account-runtime",
            "article_id": "kb-db-1",
            "route_name": "faq_custom_refund_runtime",
            "category": "faq",
            "title": "Custom runtime refund",
            "answer": "Custom refund policy from database.",
            "source_language": "en",
            "keywords": ["refund runtime", "custom refund"],
            "minimum_score": 1,
            "priority": 1,
            "is_active": True,
        },
    )
    assert create_response.status_code == 200

    response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "knowledge-account-runtime",
            "conversation_id": "conv-db-kb-1",
            "user_id": "user-db-kb-1",
            "text": "refund runtime please",
            "mode": "ai",
            "language_hint": "en",
        },
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["queue"] is None
    assert payload["ai"]["provider"] == "rule_router"
    assert payload["ai"]["model"] == "faq_custom_refund_runtime"
    assert payload["outbound"]["text"] == "Custom refund policy from database."


def test_disabled_database_support_knowledge_falls_back_to_ai_queue(client: TestClient) -> None:
    register_account_response = client.post(
        "/api/runtime/accounts",
        json={
            "account_id": "knowledge-account-disabled",
            "display_name": "Knowledge Disabled",
            "provider_type": "mock",
        },
    )
    assert register_account_response.status_code == 200

    create_response = client.post(
        "/api/runtime/support-knowledge",
        json={
            "account_id": "knowledge-account-disabled",
            "article_id": "kb-disabled-1",
            "route_name": "knowledge_disabled_route",
            "category": "knowledge_base",
            "title": "Disabled entry",
            "answer": "This should not be sent.",
            "source_language": "en",
            "keywords": ["disabled route token"],
            "minimum_score": 1,
            "priority": 1,
            "is_active": True,
        },
    )
    assert create_response.status_code == 200

    update_response = client.post(
        "/api/runtime/support-knowledge/kb-disabled-1",
        params={"account_id": "knowledge-account-disabled"},
        json={"is_active": False},
    )
    assert update_response.status_code == 200

    response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "knowledge-account-disabled",
            "conversation_id": "conv-db-kb-disabled",
            "user_id": "user-db-kb-disabled",
            "text": "disabled route token",
            "mode": "ai",
            "language_hint": "en",
        },
    )
    assert response.status_code == 200
    payload = response.json()

    assert payload["outbound"]["text"] is None
    assert payload["outbound"]["delivery_mode"] == "ai_async_queued"
    assert payload["queue"] is not None


def test_ai_queue_payload_keeps_inbound_waba_and_phone_scope(client: TestClient) -> None:
    create_account_response = client.post(
        "/api/meta/accounts/manual",
        json={
            "account_id": "queue-scope-account-1",
            "display_name": "Queue Scope Account",
            "meta_business_portfolio_id": "portfolio-queue-scope-1",
            "waba_id": "waba-queue-scope-1",
            "access_token": "token-queue-scope-1",
            "verify_token": "verify-queue-scope-1",
            "app_secret": "secret-queue-scope-1",
            "token_source": "system_user",
            "phone_numbers": [
                {
                    "phone_number_id": "pn-queue-scope-1",
                    "display_phone_number": "+1 555 000 0701",
                    "verified_name": "Queue Scope Number",
                    "quality_rating": "GREEN",
                    "is_registered": True,
                }
            ],
        },
    )
    assert create_account_response.status_code == 200

    response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "queue-scope-account-1",
            "conversation_id": "conv-queue-scope-1",
            "user_id": "user-queue-scope-1",
            "text": "Can you help me compare the available support options?",
            "mode": "ai",
            "language_hint": "en",
            "phone_number_id": "pn-queue-scope-1",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["outbound"]["delivery_mode"] == "ai_async_queued"
    assert payload["queue"] is not None

    queue_service = QueueService(get_settings())
    queued_job = queue_service.get_job(payload["queue"]["job_id"])
    assert queued_job is not None
    assert queued_job.payload["account_id"] == "queue-scope-account-1"
    assert queued_job.payload["conversation_id"] == "conv-queue-scope-1"
    assert queued_job.payload["waba_id"] == "waba-queue-scope-1"
    assert queued_job.payload["phone_number_id"] == "pn-queue-scope-1"


def test_mock_inbound_message_rule_still_respects_handover_pause(client: TestClient) -> None:
    register_agent_response = client.post(
        "/api/runtime/agents",
        json={
            "agent_id": "agent-order-1",
            "display_name": "Agent Order",
            "status": "online",
            "is_active": True,
        },
    )
    assert register_agent_response.status_code == 200

    bootstrap_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "demo-account-es",
            "conversation_id": "conv-rule-order-paused",
            "user_id": "user-rule-order-paused",
            "text": "hola",
            "mode": "echo",
            "language_hint": "es",
        },
    )
    assert bootstrap_response.status_code == 200

    handover_response = client.post(
        "/api/runtime/conversations/conv-rule-order-paused/handover?account_id=demo-account-es",
        json={
            "management_mode": "human_managed",
            "agent_id": "agent-order-1",
            "reason": "mock_pause_setup",
        },
    )
    assert handover_response.status_code == 200

    response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "demo-account-es",
            "conversation_id": "conv-rule-order-paused",
            "user_id": "user-rule-order-paused",
            "text": "Estado del pedido MOCK-1001",
            "mode": "ai",
            "language_hint": "es",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["queue"] is None
    assert payload["outbound"]["text"] is None
    assert payload["runtime"]["management_mode"] == "human_managed"
    assert payload["runtime"]["effective_ai_enabled"] is False
    assert payload["runtime"]["primary_blocking_reason"]["code"] == "human_managed"
