import asyncio

from app.api.deps import get_db_session
from app.core.settings import get_settings
from app.services.queue_service import QueueService
from app.services.runtime_state import RuntimeStateStore
from app.worker import process_reserved_job


def test_worker_uses_rule_router_for_order_lookup_before_llm(client) -> None:
    queue_service = QueueService(get_settings())
    queue_service.enqueue_ai_generation(
        {
            "account_id": "demo-account-es",
            "conversation_id": "conv-order-route-1",
            "recipient_id": "user-order-route-1",
            "user_message": "Estado del pedido MOCK-1001",
            "language_code": "es",
        }
    )
    session_generator = client.app.dependency_overrides[get_db_session]()
    session = next(session_generator)
    try:
        asyncio.run(
            RuntimeStateStore(session).ensure_conversation(
                account_id="demo-account-es",
                conversation_id="conv-order-route-1",
                customer_id="user-order-route-1",
                customer_language="es",
                customer_language_source="hint",
            )
        )
        processed_job = asyncio.run(
            process_reserved_job(
                "ai_generation",
                queue_service,
                runtime_state=RuntimeStateStore(session),
            )
        )
    finally:
        session_generator.close()

    assert processed_job is not None
    assert processed_job.result is not None
    assert processed_job.result["provider"] == "rule_router"
    assert processed_job.result["route_name"] == "order_lookup"

    messages_response = client.get("/api/conversations/demo-account-es/conv-order-route-1/messages")
    assert messages_response.status_code == 200
    messages = messages_response.json()

    assert messages[-1]["direction"] == "outbound"
    assert messages[-1]["ai_generated"] is False
    assert messages[-1]["payload"]["provider"] == "rule_router"
    assert messages[-1]["payload"]["route_name"] == "order_lookup"
    assert messages[-1]["payload"]["route_metadata"]["order_id"] == "MOCK-1001"
    assert messages[-1]["original_text"].startswith("[auto-translated en->es] Order MOCK-1001")


def test_worker_returns_rule_not_found_reply_for_unknown_tracking_number(client) -> None:
    queue_service = QueueService(get_settings())
    queue_service.enqueue_ai_generation(
        {
            "account_id": "demo-account-es",
            "conversation_id": "conv-tracking-route-1",
            "recipient_id": "user-tracking-route-1",
            "user_message": "tracking UNKNOWN123456",
            "language_code": "en",
        }
    )
    session_generator = client.app.dependency_overrides[get_db_session]()
    session = next(session_generator)
    try:
        asyncio.run(
            RuntimeStateStore(session).ensure_conversation(
                account_id="demo-account-es",
                conversation_id="conv-tracking-route-1",
                customer_id="user-tracking-route-1",
                customer_language="en",
                customer_language_source="hint",
            )
        )
        processed_job = asyncio.run(
            process_reserved_job(
                "ai_generation",
                queue_service,
                runtime_state=RuntimeStateStore(session),
            )
        )
    finally:
        session_generator.close()

    assert processed_job is not None
    assert processed_job.result is not None
    assert processed_job.result["provider"] == "rule_router"
    assert processed_job.result["route_name"] == "tracking_lookup_not_found"

    messages_response = client.get("/api/conversations/demo-account-es/conv-tracking-route-1/messages")
    assert messages_response.status_code == 200
    messages = messages_response.json()

    assert messages[-1]["payload"]["route_name"] == "tracking_lookup_not_found"
    assert "UNKNOWN123456" in messages[-1]["original_text"]


def test_worker_rechecks_faq_rule_before_calling_ai_provider(client, monkeypatch) -> None:
    queue_service = QueueService(get_settings())
    queue_service.enqueue_ai_generation(
        {
            "account_id": "demo-account-fr",
            "conversation_id": "conv-faq-route-1",
            "recipient_id": "user-faq-route-1",
            "user_message": "bonjour, retour et remboursement ?",
            "language_code": "fr",
        }
    )
    session_generator = client.app.dependency_overrides[get_db_session]()
    session = next(session_generator)
    try:
        asyncio.run(
            RuntimeStateStore(session).ensure_conversation(
                account_id="demo-account-fr",
                conversation_id="conv-faq-route-1",
                customer_id="user-faq-route-1",
                customer_language="fr",
                customer_language_source="hint",
            )
        )

        class ShouldNotBeCalledProvider:
            provider_name = "openai"
            model = "blocked"

            async def generate_reply(self, request) -> str:
                del request
                raise AssertionError("AI provider should not be called when FAQ route hits.")

        monkeypatch.setattr(
            "app.services.ai_queue_processor.get_ai_provider",
            lambda settings: ShouldNotBeCalledProvider(),
        )
        processed_job = asyncio.run(
            process_reserved_job(
                "ai_generation",
                queue_service,
                runtime_state=RuntimeStateStore(session),
            )
        )
    finally:
        session_generator.close()

    assert processed_job is not None
    assert processed_job.result is not None
    assert processed_job.result["provider"] == "rule_router"
    assert processed_job.result["route_name"] == "faq_refund_policy"

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


def test_worker_skips_ai_when_handover_is_recommended(client) -> None:
    queue_service = QueueService(get_settings())
    queue_service.enqueue_ai_generation(
        {
            "account_id": "demo-account-es",
            "conversation_id": "conv-intent-worker-1",
            "recipient_id": "user-intent-worker-1",
            "user_message": "Please connect me to a human agent.",
            "language_code": "en",
            "intent_name": "human_handover_request",
            "intent_confidence": 0.98,
            "handover_recommended": True,
            "handover_reason": "customer_requested_human_support",
        }
    )
    session_generator = client.app.dependency_overrides[get_db_session]()
    session = next(session_generator)
    try:
        asyncio.run(
            RuntimeStateStore(session).ensure_conversation(
                account_id="demo-account-es",
                conversation_id="conv-intent-worker-1",
                customer_id="user-intent-worker-1",
                customer_language="en",
                customer_language_source="hint",
            )
        )
        processed_job = asyncio.run(
            process_reserved_job(
                "ai_generation",
                queue_service,
                runtime_state=RuntimeStateStore(session),
            )
        )
    finally:
        session_generator.close()

    assert processed_job is not None
    assert processed_job.result is not None
    assert processed_job.result["status"] == "skipped"
    assert processed_job.result["reason"] == "handover_recommended_before_ai"
    assert processed_job.result["intent_name"] == "human_handover_request"
