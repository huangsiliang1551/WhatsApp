import os
import asyncio
import json
from contextlib import contextmanager

from fastapi.testclient import TestClient

from app.api.deps import get_db_session
from app.core.settings import get_settings
from app.services.queue_service import QueueService
from app.services.runtime_state import RuntimeStateStore
from app.worker import process_reserved_job
from app.providers.messaging.whatsapp_provider import WhatsAppProvider


def read_metric_value(
    payload: str,
    metric_name: str,
    labels: dict[str, str] | None = None,
) -> float:
    for line in payload.splitlines():
        if not line.startswith(metric_name):
            continue
        metric_key, value = line.split(" ", 1)
        if labels is None:
            if metric_key == metric_name:
                return float(value)
            continue
        if not metric_key.startswith(f"{metric_name}{{") or not metric_key.endswith("}"):
            continue
        label_blob = metric_key[len(metric_name) + 1 : -1]
        parsed_labels: dict[str, str] = {}
        for item in label_blob.split(","):
            key, raw_value = item.split("=", 1)
            parsed_labels[key] = raw_value.strip('"')
        if all(parsed_labels.get(key) == expected for key, expected in labels.items()):
            return float(value)
    return 0.0


def fetch_metrics(client: TestClient) -> str:
    response = client.get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    return response.text


def fetch_metrics_summary(client: TestClient) -> dict[str, object]:
    response = client.get("/api/metrics/summary")
    assert response.status_code == 200
    return response.json()


def register_meta_account_with_webhook_secret(client: TestClient) -> None:
    response = client.post(
        "/api/meta/accounts/manual",
        json={
            "account_id": "metrics-meta-account",
            "display_name": "Metrics Meta Account",
            "meta_business_portfolio_id": "portfolio-metrics-1",
            "waba_id": "waba-metrics-1",
            "access_token": "token-metrics-1",
            "verify_token": "verify-metrics-1",
            "app_secret": "secret-metrics-1",
            "token_source": "system_user",
            "phone_numbers": [
                {
                    "phone_number_id": "pn-metrics-1",
                    "display_phone_number": "+1 555 000 0100",
                    "verified_name": "Metrics Brand",
                    "quality_rating": "GREEN",
                    "is_registered": True,
                }
            ],
        },
    )
    assert response.status_code == 200


@contextmanager
def whatsapp_provider_mode() -> object:
    original_provider = os.environ.get("MESSAGING_PROVIDER")
    os.environ["MESSAGING_PROVIDER"] = "whatsapp"
    get_settings.cache_clear()
    try:
        yield
    finally:
        if original_provider is None:
            os.environ.pop("MESSAGING_PROVIDER", None)
        else:
            os.environ["MESSAGING_PROVIDER"] = original_provider
        get_settings.cache_clear()


def register_verified_meta_account_with_webhook_secret(client: TestClient) -> None:
    register_meta_account_with_webhook_secret(client)
    subscribe_response = client.post(
        "/api/meta/accounts/metrics-meta-account/wabas/waba-metrics-1/webhook-subscription",
        json={"callback_url": "https://example.com/webhooks/metrics-meta-account"},
    )
    assert subscribe_response.status_code == 200
    verify_response = client.get(
        "/webhooks/whatsapp/metrics-meta-account/wabas/waba-metrics-1",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "verify-metrics-1",
            "hub.challenge": "metrics-challenge",
        },
    )
    assert verify_response.status_code == 200
    assert verify_response.text == "metrics-challenge"


def test_metrics_exposes_queue_gauge_samples_before_queue_activity(client: TestClient) -> None:
    payload = fetch_metrics(client)

    for status in ("queued", "processing", "completed", "failed"):
        assert f'queue_jobs_current{{queue="ai_generation",status="{status}"}}' in payload


def test_metrics_exposes_mock_inbound_counter_after_dev_message(client: TestClient) -> None:
    before = fetch_metrics(client)
    before_total = read_metric_value(before, "mock_inbound_messages_total")
    before_business_inbound = read_metric_value(
        before,
        "business_inbound_messages_total",
        {"provider": "mock", "outcome": "accepted"},
    )
    before_business_outbound = read_metric_value(
        before,
        "business_outbound_messages_total",
        {"provider": "mock", "delivery_mode": "echo", "outcome": "accepted"},
    )
    before_view_translation = read_metric_value(
        before,
        "translation_operations_total",
        {"provider": "fallback", "direction": "conversation_view", "outcome": "translated"},
    )

    response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "metrics-mock-account-1",
            "conversation_id": "metrics-conv-1",
            "user_id": "metrics-user-1",
            "text": "bonjour metrics",
            "mode": "echo",
        },
    )
    assert response.status_code == 200

    after = fetch_metrics(client)
    after_total = read_metric_value(after, "mock_inbound_messages_total")
    after_business_inbound = read_metric_value(
        after,
        "business_inbound_messages_total",
        {"provider": "mock", "outcome": "accepted"},
    )
    after_business_outbound = read_metric_value(
        after,
        "business_outbound_messages_total",
        {"provider": "mock", "delivery_mode": "echo", "outcome": "accepted"},
    )
    after_view_translation = read_metric_value(
        after,
        "translation_operations_total",
        {"provider": "fallback", "direction": "conversation_view", "outcome": "translated"},
    )

    assert after_total == before_total + 1
    assert after_business_inbound == before_business_inbound + 1
    assert after_business_outbound == before_business_outbound + 1
    assert after_view_translation == before_view_translation


def test_metrics_exposes_queue_counters_and_current_gauges(client: TestClient) -> None:
    queue_service = QueueService(get_settings())
    stats_response = client.get("/api/queue/stats")
    assert stats_response.status_code == 200

    before = fetch_metrics(client)
    before_queued_total = read_metric_value(
        before,
        "queue_jobs_total",
        {"queue": "ai_generation", "status": "queued"},
    )
    before_completed_total = read_metric_value(
        before,
        "queue_jobs_total",
        {"queue": "ai_generation", "status": "completed"},
    )
    before_ai_success_total = read_metric_value(
        before,
        "business_ai_replies_total",
        {"provider": "mock", "outcome": "success"},
    )
    before_ai_outbound_total = read_metric_value(
        before,
        "business_outbound_messages_total",
        {"provider": "mock", "delivery_mode": "ai_auto_reply", "outcome": "accepted"},
    )
    assert (
        read_metric_value(
            before,
            "queue_jobs_current",
            {"queue": "ai_generation", "status": "queued"},
        )
        == 0
    )

    response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "metrics-queue-account-1",
            "conversation_id": "metrics-queue-conv-1",
            "user_id": "metrics-queue-user-1",
            "text": "please queue this",
            "mode": "ai",
        },
    )
    assert response.status_code == 200
    job_id = response.json()["queue"]["job_id"]
    assert queue_service.get_job(job_id) is not None

    queued_metrics = fetch_metrics(client)
    assert read_metric_value(
        queued_metrics,
        "queue_jobs_total",
        {"queue": "ai_generation", "status": "queued"},
    ) == (before_queued_total + 1)
    assert (
        read_metric_value(
            queued_metrics,
            "queue_jobs_current",
            {"queue": "ai_generation", "status": "queued"},
        )
        == 1
    )
    assert (
        read_metric_value(
            queued_metrics,
            "queue_jobs_current",
            {"queue": "ai_generation", "status": "processing"},
        )
        == 0
    )

    session_generator = client.app.dependency_overrides[get_db_session]()
    session = next(session_generator)
    try:
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
    assert processed_job.status == "completed"

    completed_metrics = fetch_metrics(client)
    assert read_metric_value(
        completed_metrics,
        "queue_jobs_total",
        {"queue": "ai_generation", "status": "completed"},
    ) == (before_completed_total + 1)
    assert (
        read_metric_value(
            completed_metrics,
            "queue_jobs_current",
            {"queue": "ai_generation", "status": "queued"},
        )
        == 0
    )
    assert (
        read_metric_value(
            completed_metrics,
            "queue_jobs_current",
            {"queue": "ai_generation", "status": "processing"},
        )
        == 0
    )
    assert (
        read_metric_value(
            completed_metrics,
            "queue_jobs_current",
            {"queue": "ai_generation", "status": "completed"},
        )
        == 1
    )
    assert read_metric_value(
        completed_metrics,
        "business_ai_replies_total",
        {"provider": "mock", "outcome": "success"},
    ) == (before_ai_success_total + 1)
    assert read_metric_value(
        completed_metrics,
        "business_outbound_messages_total",
        {"provider": "mock", "delivery_mode": "ai_auto_reply", "outcome": "accepted"},
    ) == (before_ai_outbound_total + 1)


def test_metrics_exposes_webhook_message_and_status_update_counters(client: TestClient) -> None:
    with whatsapp_provider_mode():
        register_verified_meta_account_with_webhook_secret(client)

        before = fetch_metrics(client)
        before_messages_total = read_metric_value(
            before,
            "whatsapp_webhook_messages_total",
            {"provider": "whatsapp", "outcome": "accepted"},
        )
        before_status_total = read_metric_value(
            before,
            "whatsapp_webhook_status_updates_total",
            {"provider": "whatsapp", "outcome": "accepted"},
        )
        before_scoped_messages_total = read_metric_value(
            before,
            "whatsapp_webhook_messages_scoped_total",
            {
                "account_id": "metrics-meta-account",
                "waba_id": "waba-metrics-1",
                "phone_number_id": "pn-metrics-1",
            },
        )
        before_scoped_status_total = read_metric_value(
            before,
            "whatsapp_webhook_status_updates_scoped_total",
            {
                "account_id": "metrics-meta-account",
                "waba_id": "waba-metrics-1",
                "phone_number_id": "pn-metrics-1",
            },
        )
        before_business_inbound = read_metric_value(
            before,
            "business_inbound_messages_total",
            {"provider": "whatsapp", "outcome": "accepted"},
        )
        before_delivery_events = read_metric_value(
            before,
            "message_delivery_events_total",
            {"provider": "whatsapp", "status": "delivered"},
        )

        message_payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "waba-metrics-1",
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {
                                    "display_phone_number": "+1 555 000 0100",
                                    "phone_number_id": "pn-metrics-1",
                                },
                                "contacts": [
                                    {
                                        "wa_id": "14150000100",
                                        "profile": {"name": "Metrics Customer"},
                                    }
                                ],
                                "messages": [
                                    {
                                        "from": "14150000100",
                                        "id": "wamid.metrics.1",
                                        "timestamp": "1712345800",
                                        "type": "text",
                                        "text": {"body": "hola metrics webhook"},
                                    }
                                ],
                            },
                        }
                    ],
                }
            ],
        }
        raw_message_body = json.dumps(message_payload, separators=(",", ":")).encode("utf-8")
        message_signature = WhatsAppProvider.build_signature("secret-metrics-1", raw_message_body)

        message_response = client.post(
            "/webhooks/whatsapp/metrics-meta-account/wabas/waba-metrics-1",
            content=raw_message_body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": message_signature,
            },
        )
        assert message_response.status_code == 200
        assert message_response.json()["accepted_messages"] == 1

        status_payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "waba-metrics-1",
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {
                                    "display_phone_number": "+1 555 000 0100",
                                    "phone_number_id": "pn-metrics-1",
                                },
                                "statuses": [
                                    {
                                        "id": "wamid.metrics.1",
                                        "status": "delivered",
                                        "timestamp": "1712345801",
                                        "recipient_id": "14150000100",
                                    }
                                ],
                            },
                        }
                    ],
                }
            ],
        }
        raw_status_body = json.dumps(status_payload, separators=(",", ":")).encode("utf-8")
        status_signature = WhatsAppProvider.build_signature("secret-metrics-1", raw_status_body)

        status_response = client.post(
            "/webhooks/whatsapp/metrics-meta-account/wabas/waba-metrics-1",
            content=raw_status_body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": status_signature,
            },
        )
        assert status_response.status_code == 200
        assert status_response.json()["accepted_status_updates"] == 1
        assert status_response.json()["matched_status_updates"] == 1

        after = fetch_metrics(client)
        after_messages_total = read_metric_value(
            after,
            "whatsapp_webhook_messages_total",
            {"provider": "whatsapp", "outcome": "accepted"},
        )
        after_status_total = read_metric_value(
            after,
            "whatsapp_webhook_status_updates_total",
            {"provider": "whatsapp", "outcome": "accepted"},
        )
        after_scoped_messages_total = read_metric_value(
            after,
            "whatsapp_webhook_messages_scoped_total",
            {
                "account_id": "metrics-meta-account",
                "waba_id": "waba-metrics-1",
                "phone_number_id": "pn-metrics-1",
            },
        )
        after_scoped_status_total = read_metric_value(
            after,
            "whatsapp_webhook_status_updates_scoped_total",
            {
                "account_id": "metrics-meta-account",
                "waba_id": "waba-metrics-1",
                "phone_number_id": "pn-metrics-1",
            },
        )
        after_business_inbound = read_metric_value(
            after,
            "business_inbound_messages_total",
            {"provider": "whatsapp", "outcome": "accepted"},
        )
        after_delivery_events = read_metric_value(
            after,
            "message_delivery_events_total",
            {"provider": "whatsapp", "status": "delivered"},
        )

        assert after_messages_total == before_messages_total + 1
        assert after_status_total == before_status_total + 1
        assert after_scoped_messages_total == before_scoped_messages_total + 1
        assert after_scoped_status_total == before_scoped_status_total + 1
        assert after_business_inbound == before_business_inbound + 1
        assert after_delivery_events == before_delivery_events + 1


def test_metrics_exposes_webhook_management_update_counters(client: TestClient) -> None:
    register_meta_account_with_webhook_secret(client)

    template_response = client.post(
        "/api/templates/drafts",
        json={
            "account_id": "metrics-meta-account",
            "waba_id": "waba-metrics-1",
            "name": "metrics_management_template",
            "language": "en",
            "category": "UTILITY",
            "body_text": "Hello {{first_name}}, metrics management update.",
            "sample_variables": {"first_name": "Customer"},
        },
    )
    assert template_response.status_code == 200
    template_id = template_response.json()["template_id"]
    status_response = client.post(
        f"/api/templates/{template_id}/status",
        json={"status": "PENDING", "meta_template_id": "meta-template-metrics-management"},
    )
    assert status_response.status_code == 200

    before = fetch_metrics(client)
    before_summary = fetch_metrics_summary(client)
    template_labels = {
        "account_id": "metrics-meta-account",
        "waba_id": "waba-metrics-1",
        "event_type": "message_template_status_update",
        "outcome": "matched",
    }
    phone_labels = {
        "account_id": "metrics-meta-account",
        "waba_id": "waba-metrics-1",
        "phone_number_id": "pn-metrics-1",
        "event_type": "phone_number_quality_update",
        "outcome": "matched",
    }
    before_template_updates = read_metric_value(
        before,
        "whatsapp_webhook_template_updates_total",
        template_labels,
    )
    before_phone_updates = read_metric_value(
        before,
        "whatsapp_webhook_phone_number_updates_total",
        phone_labels,
    )

    template_payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba-metrics-1",
                "changes": [
                    {
                        "field": "message_template_status_update",
                        "value": {
                            "event": "APPROVED",
                            "message_template_id": "meta-template-metrics-management",
                            "message_template_name": "metrics_management_template",
                            "message_template_language": "en",
                        },
                    }
                ],
            }
        ],
    }
    raw_template_body = json.dumps(template_payload, separators=(",", ":")).encode("utf-8")
    template_signature = WhatsAppProvider.build_signature("secret-metrics-1", raw_template_body)
    template_webhook_response = client.post(
        "/webhooks/whatsapp/metrics-meta-account/wabas/waba-metrics-1",
        content=raw_template_body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": template_signature,
        },
    )
    assert template_webhook_response.status_code == 200
    assert template_webhook_response.json()["matched_template_updates"] == 1

    phone_payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba-metrics-1",
                "changes": [
                    {
                        "field": "phone_number_quality_update",
                        "value": {
                            "event": "DOWNGRADE",
                            "phone_number_id": "pn-metrics-1",
                            "display_phone_number": "+1 555 000 0100",
                            "new_quality_rating": "YELLOW",
                            "current_limit": "TIER_250",
                        },
                    }
                ],
            }
        ],
    }
    raw_phone_body = json.dumps(phone_payload, separators=(",", ":")).encode("utf-8")
    phone_signature = WhatsAppProvider.build_signature("secret-metrics-1", raw_phone_body)
    phone_webhook_response = client.post(
        "/webhooks/whatsapp/metrics-meta-account/wabas/waba-metrics-1",
        content=raw_phone_body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": phone_signature,
        },
    )
    assert phone_webhook_response.status_code == 200
    assert phone_webhook_response.json()["matched_phone_number_updates"] == 1

    after = fetch_metrics(client)
    after_summary = fetch_metrics_summary(client)
    assert read_metric_value(
        after,
        "whatsapp_webhook_template_updates_total",
        template_labels,
    ) == before_template_updates + 1
    assert read_metric_value(
        after,
        "whatsapp_webhook_phone_number_updates_total",
        phone_labels,
    ) == before_phone_updates + 1
    assert (
        after_summary["webhook"]["template_update_total"]
        >= before_summary["webhook"]["template_update_total"] + 1
    )
    assert (
        after_summary["webhook"]["phone_number_update_total"]
        >= before_summary["webhook"]["phone_number_update_total"] + 1
    )


def test_metrics_exposes_provider_status_buffer_pending_and_replay(
    client: TestClient,
) -> None:
    register_meta_account_with_webhook_secret(client)
    provider_message_id = "wamid.metrics.buffer.pending.1"
    labels = {
        "provider": "whatsapp",
        "account_id": "metrics-meta-account",
        "waba_id": "waba-metrics-1",
        "phone_number_id": "pn-metrics-1",
    }

    before = fetch_metrics(client)
    before_buffered_total = read_metric_value(
        before,
        "provider_status_event_buffer_events_total",
        {**labels, "outcome": "buffered"},
    )
    before_applied_total = read_metric_value(
        before,
        "provider_status_event_buffer_events_total",
        {**labels, "outcome": "applied"},
    )

    status_payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba-metrics-1",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "+1 555 000 0100",
                                "phone_number_id": "pn-metrics-1",
                            },
                            "statuses": [
                                {
                                    "id": provider_message_id,
                                    "status": "delivered",
                                    "timestamp": "1712346801",
                                    "recipient_id": "14150000120",
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }
    raw_status_body = json.dumps(status_payload, separators=(",", ":")).encode("utf-8")
    status_signature = WhatsAppProvider.build_signature("secret-metrics-1", raw_status_body)
    status_response = client.post(
        "/webhooks/whatsapp/metrics-meta-account/wabas/waba-metrics-1",
        content=raw_status_body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": status_signature,
        },
    )
    assert status_response.status_code == 200
    assert status_response.json()["accepted_status_updates"] == 1
    assert status_response.json()["matched_status_updates"] == 0

    buffered_metrics = fetch_metrics(client)
    assert read_metric_value(
        buffered_metrics,
        "provider_status_event_buffer_pending_current",
        labels,
    ) == 1
    assert read_metric_value(
        buffered_metrics,
        "provider_status_event_buffer_oldest_age_seconds",
        labels,
    ) >= 0
    assert read_metric_value(
        buffered_metrics,
        "provider_status_event_buffer_events_total",
        {**labels, "outcome": "buffered"},
    ) == before_buffered_total + 1

    session_generator = client.app.dependency_overrides[get_db_session]()
    session = next(session_generator)
    try:
        runtime_state = RuntimeStateStore(session)
        asyncio.run(
            runtime_state.ensure_conversation(
                account_id="metrics-meta-account",
                conversation_id="metrics-buffer-conv-1",
                customer_id="metrics-buffer-customer",
                customer_language="en",
                provider_phone_number_id="pn-metrics-1",
            )
        )
        asyncio.run(
            runtime_state.record_outbound_message(
                account_id="metrics-meta-account",
                conversation_id="metrics-buffer-conv-1",
                recipient_id="14150000120",
                text="buffer replay marker",
                language_code="en",
                translated_text=None,
                translated_language_code=None,
                delivery_mode="template_send",
                ai_generated=False,
                payload={},
                provider_message_id=provider_message_id,
            )
        )
        replayed_count = asyncio.run(
            runtime_state.replay_unmatched_provider_status_events(
                account_id="metrics-meta-account",
                provider_message_id=provider_message_id,
            )
        )
    finally:
        session_generator.close()

    assert replayed_count == 1
    replayed_metrics = fetch_metrics(client)
    assert read_metric_value(
        replayed_metrics,
        "provider_status_event_buffer_pending_current",
        labels,
    ) == 0
    assert read_metric_value(
        replayed_metrics,
        "provider_status_event_buffer_oldest_age_seconds",
        labels,
    ) == 0
    assert read_metric_value(
        replayed_metrics,
        "provider_status_event_buffer_events_total",
        {**labels, "outcome": "applied"},
    ) == before_applied_total + 1


def test_metrics_exposes_webhook_signature_failure_counter(client: TestClient) -> None:
    with whatsapp_provider_mode():
        register_verified_meta_account_with_webhook_secret(client)

        before = fetch_metrics(client)
        before_signature_failures = read_metric_value(
            before,
            "whatsapp_webhook_signature_failures_total",
        )
        before_scoped_signature_failures = read_metric_value(
            before,
            "whatsapp_webhook_signature_failures_scoped_total",
            {
                "account_id": "metrics-meta-account",
                "waba_id": "waba-metrics-1",
            },
        )
        before_processing_failures = read_metric_value(
            before,
            "message_processing_failures_total",
            {"provider": "whatsapp", "stage": "webhook_signature"},
        )

        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "waba-metrics-1",
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {
                                    "display_phone_number": "+1 555 000 0100",
                                    "phone_number_id": "pn-metrics-1",
                                },
                                "messages": [
                                    {
                                        "from": "14150000101",
                                        "id": "wamid.metrics.invalidsig.1",
                                        "timestamp": "1712345900",
                                        "type": "text",
                                        "text": {"body": "invalid signature"},
                                    }
                                ],
                            },
                        }
                    ],
                }
            ],
        }
        raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")

        response = client.post(
            "/webhooks/whatsapp/metrics-meta-account/wabas/waba-metrics-1",
            content=raw_body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": "sha256=invalid",
            },
        )
        assert response.status_code == 403

        after = fetch_metrics(client)
        after_signature_failures = read_metric_value(
            after,
            "whatsapp_webhook_signature_failures_total",
        )
        after_scoped_signature_failures = read_metric_value(
            after,
            "whatsapp_webhook_signature_failures_scoped_total",
            {
                "account_id": "metrics-meta-account",
                "waba_id": "waba-metrics-1",
            },
        )
        after_processing_failures = read_metric_value(
            after,
            "message_processing_failures_total",
            {"provider": "whatsapp", "stage": "webhook_signature"},
        )

        assert after_signature_failures == before_signature_failures + 1
        assert after_scoped_signature_failures == before_scoped_signature_failures + 1
        assert after_processing_failures == before_processing_failures + 1


def test_metrics_summary_reflects_mock_inbound_and_queue_activity(client: TestClient) -> None:
    queue_service = QueueService(get_settings())
    before = fetch_metrics_summary(client)

    response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "metrics-summary-account-1",
            "conversation_id": "metrics-summary-conv-1",
            "user_id": "metrics-summary-user-1",
            "text": "bonjour summary",
            "mode": "echo",
        },
    )
    assert response.status_code == 200
    translation_response = client.get(
        "/api/conversations/metrics-summary-account-1/metrics-summary-conv-1/messages",
        params={"include_translations": "true"},
    )
    assert translation_response.status_code == 200
    translated_messages = translation_response.json()
    assert translated_messages[0]["translation_kind"] is None

    queue_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "metrics-summary-account-2",
            "conversation_id": "metrics-summary-conv-2",
            "user_id": "metrics-summary-user-2",
            "text": "please queue summary",
            "mode": "ai",
        },
    )
    assert queue_response.status_code == 200
    job_id = queue_response.json()["queue"]["job_id"]
    assert queue_service.get_job(job_id) is not None

    session_generator = client.app.dependency_overrides[get_db_session]()
    session = next(session_generator)
    try:
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
    after = fetch_metrics_summary(client)

    assert after["inbound"]["accepted_total"] >= before["inbound"]["accepted_total"] + 2
    assert after["outbound"]["echo_total"] >= before["outbound"]["echo_total"] + 1
    assert after["queue"]["queued_total"] >= before["queue"]["queued_total"] + 1
    assert after["queue"]["completed_total"] >= before["queue"]["completed_total"] + 1
    assert after["ai"]["queued_total"] >= before["ai"]["queued_total"] + 1
    assert after["ai"]["success_total"] >= before["ai"]["success_total"] + 1
    assert after["translation"]["conversation_view_translated_total"] == (
        before["translation"]["conversation_view_translated_total"]
    )


def test_metrics_summary_reflects_webhook_and_signature_failures(client: TestClient) -> None:
    with whatsapp_provider_mode():
        register_verified_meta_account_with_webhook_secret(client)
        before = fetch_metrics_summary(client)

        message_payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "waba-metrics-1",
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {
                                    "display_phone_number": "+1 555 000 0100",
                                    "phone_number_id": "pn-metrics-1",
                                },
                                "contacts": [
                                    {
                                        "wa_id": "14150000110",
                                        "profile": {"name": "Metrics Summary Customer"},
                                    }
                                ],
                                "messages": [
                                    {
                                        "from": "14150000110",
                                        "id": "wamid.metrics.summary.1",
                                        "timestamp": "1712346000",
                                        "type": "text",
                                        "text": {"body": "hola webhook summary"},
                                    }
                                ],
                            },
                        }
                    ],
                }
            ],
        }
        raw_message_body = json.dumps(message_payload, separators=(",", ":")).encode("utf-8")
        message_signature = WhatsAppProvider.build_signature("secret-metrics-1", raw_message_body)
        message_response = client.post(
            "/webhooks/whatsapp/metrics-meta-account/wabas/waba-metrics-1",
            content=raw_message_body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": message_signature,
            },
        )
        assert message_response.status_code == 200

        invalid_response = client.post(
            "/webhooks/whatsapp/metrics-meta-account/wabas/waba-metrics-1",
            content=raw_message_body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": "sha256=invalid",
            },
        )
        assert invalid_response.status_code == 403

        after = fetch_metrics_summary(client)

        assert after["webhook"]["message_total"] >= before["webhook"]["message_total"] + 1
        assert after["inbound"]["whatsapp_webhook_total"] >= before["inbound"]["whatsapp_webhook_total"] + 1
        assert after["inbound"]["accepted_total"] >= before["inbound"]["accepted_total"] + 1
        assert after["webhook"]["signature_failure_total"] >= (
            before["webhook"]["signature_failure_total"] + 1
        )
        assert after["processing_failures"]["webhook_signature_total"] >= (
            before["processing_failures"]["webhook_signature_total"] + 1
        )
