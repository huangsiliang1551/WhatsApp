from collections.abc import Iterable, Mapping

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, generate_latest

from app.db.models import utc_now
from app.schemas.metrics import MetricsSummaryResponse

mock_inbound_messages_total = Counter(
    "mock_inbound_messages_total",
    "Total number of mock inbound messages processed.",
)

business_inbound_messages_total = Counter(
    "business_inbound_messages_total",
    "Total number of inbound messages by provider and processing outcome.",
    labelnames=("provider", "outcome"),
)

whatsapp_webhook_messages_total = Counter(
    "whatsapp_webhook_messages_total",
    "Total number of WhatsApp webhook messages accepted by the webhook route.",
    labelnames=("provider", "outcome"),
)

whatsapp_webhook_status_updates_total = Counter(
    "whatsapp_webhook_status_updates_total",
    "Total number of WhatsApp webhook status updates accepted by the webhook route.",
    labelnames=("provider", "outcome"),
)

whatsapp_webhook_signature_failures_total = Counter(
    "whatsapp_webhook_signature_failures_total",
    "Total number of WhatsApp webhook requests rejected due to invalid signatures.",
)

whatsapp_webhook_messages_scoped_total = Counter(
    "whatsapp_webhook_messages_scoped_total",
    "Total number of WhatsApp webhook messages accepted by account, WABA, and phone number.",
    labelnames=("account_id", "waba_id", "phone_number_id"),
)

whatsapp_webhook_status_updates_scoped_total = Counter(
    "whatsapp_webhook_status_updates_scoped_total",
    "Total number of WhatsApp webhook status updates accepted by account, WABA, and phone number.",
    labelnames=("account_id", "waba_id", "phone_number_id"),
)

whatsapp_webhook_template_updates_total = Counter(
    "whatsapp_webhook_template_updates_total",
    "Total number of WhatsApp template management webhook updates by account, WABA, event type, and outcome.",
    labelnames=("account_id", "waba_id", "event_type", "outcome"),
)

whatsapp_webhook_phone_number_updates_total = Counter(
    "whatsapp_webhook_phone_number_updates_total",
    "Total number of WhatsApp phone number management webhook updates by account, WABA, phone number, event type, and outcome.",
    labelnames=("account_id", "waba_id", "phone_number_id", "event_type", "outcome"),
)

whatsapp_webhook_signature_failures_scoped_total = Counter(
    "whatsapp_webhook_signature_failures_scoped_total",
    "Total number of WhatsApp webhook signature failures by account and WABA.",
    labelnames=("account_id", "waba_id"),
)

whatsapp_webhook_phone_scope_rejections_total = Counter(
    "whatsapp_webhook_phone_scope_rejections_total",
    "Total number of WhatsApp webhook items rejected by account, WABA, phone number, item type, and reason.",
    labelnames=("account_id", "waba_id", "phone_number_id", "item_type", "reason"),
)

message_processing_failures_total = Counter(
    "message_processing_failures_total",
    "Total number of inbound or outbound processing failures by provider and stage.",
    labelnames=("provider", "stage"),
)

business_outbound_messages_total = Counter(
    "business_outbound_messages_total",
    "Total number of outbound messages by provider, delivery mode, and outcome.",
    labelnames=("provider", "delivery_mode", "outcome"),
)

business_ai_replies_total = Counter(
    "business_ai_replies_total",
    "Total number of AI reply decisions by provider and outcome.",
    labelnames=("provider", "outcome"),
)

business_template_sends_total = Counter(
    "business_template_sends_total",
    "Total number of template send attempts and provider status updates by provider and status.",
    labelnames=("provider", "status"),
)

business_template_send_failures_total = Counter(
    "business_template_send_failures_total",
    "Total number of template send failures by provider and reason.",
    labelnames=("provider", "reason"),
)

message_delivery_events_total = Counter(
    "message_delivery_events_total",
    "Total number of provider delivery status events by provider and status.",
    labelnames=("provider", "status"),
)

provider_status_event_buffer_pending_current = Gauge(
    "provider_status_event_buffer_pending_current",
    "Current unmatched provider status callback count by provider and account scope.",
    labelnames=("provider", "account_id", "waba_id", "phone_number_id"),
)

provider_status_event_buffer_oldest_age_seconds = Gauge(
    "provider_status_event_buffer_oldest_age_seconds",
    "Age in seconds of the oldest pending unmatched provider status callback by provider and account scope.",
    labelnames=("provider", "account_id", "waba_id", "phone_number_id"),
)

provider_status_event_buffer_events_total = Counter(
    "provider_status_event_buffer_events_total",
    "Total number of provider status buffer lifecycle events by provider, account scope, and outcome.",
    labelnames=("provider", "account_id", "waba_id", "phone_number_id", "outcome"),
)

translation_operations_total = Counter(
    "translation_operations_total",
    "Total number of translation operations by provider, direction, and outcome.",
    labelnames=("provider", "direction", "outcome"),
)

queue_jobs_total = Counter(
    "queue_jobs_total",
    "Total number of queue jobs by queue and status transition.",
    labelnames=("queue", "status"),
)

queue_jobs_current = Gauge(
    "queue_jobs_current",
    "Current queue job counts by queue and status.",
    labelnames=("queue", "status"),
)

for _queue_status in ("queued", "processing", "completed", "failed"):
    queue_jobs_current.labels(queue="ai_generation", status=_queue_status).set(0)

task_submissions_total = Counter(
    "task_submissions_total",
    "Total number of task submissions by status.",
    labelnames=("status",),
)

task_reviews_total = Counter(
    "task_reviews_total",
    "Total number of task review decisions by decision.",
    labelnames=("decision",),
)

tickets_created_total = Counter(
    "tickets_created_total",
    "Total number of tickets created by type.",
    labelnames=("ticket_type",),
)

tickets_status_transition_total = Counter(
    "tickets_status_transition_total",
    "Total number of ticket status transitions by resulting status.",
    labelnames=("status",),
)

# DB pool metrics

db_pool_checked_in = Gauge(
    "db_pool_checked_in",
    "Current number of database connections checked into the pool.",
)

db_pool_checked_out = Gauge(
    "db_pool_checked_out",
    "Current number of database connections checked out of the pool.",
)

db_pool_size = Gauge(
    "db_pool_size",
    "Current total size of the database connection pool.",
)

# Redis metrics

redis_commands_total = Counter(
    "redis_commands_total",
    "Total number of Redis commands executed.",
)

redis_errors_total = Counter(
    "redis_errors_total",
    "Total number of Redis command errors.",
)


def render_metrics() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST


def build_metrics_summary() -> MetricsSummaryResponse:
    return MetricsSummaryResponse(
        generated_at=utc_now().isoformat(),
        inbound={
            "mock_total": _read_sample(mock_inbound_messages_total, "mock_inbound_messages_total"),
            "whatsapp_webhook_total": _read_sample(
                whatsapp_webhook_messages_total,
                "whatsapp_webhook_messages_total",
            ),
            "accepted_total": _sum_samples(
                business_inbound_messages_total,
                "business_inbound_messages_total",
                (
                    {"outcome": "accepted"},
                ),
            ),
            "duplicate_total": _sum_samples(
                business_inbound_messages_total,
                "business_inbound_messages_total",
                (
                    {"outcome": "duplicate"},
                ),
            ),
            "skipped_total": _sum_samples(
                business_inbound_messages_total,
                "business_inbound_messages_total",
                (
                    {"outcome": "skipped"},
                ),
            ),
        },
        outbound={
            "accepted_total": _sum_samples(
                business_outbound_messages_total,
                "business_outbound_messages_total",
                (
                    {"outcome": "accepted"},
                ),
            ),
            "failed_total": _sum_samples(
                business_outbound_messages_total,
                "business_outbound_messages_total",
                (
                    {"outcome": "failed"},
                ),
            ),
            "echo_total": _sum_samples(
                business_outbound_messages_total,
                "business_outbound_messages_total",
                (
                    {"delivery_mode": "echo", "outcome": "accepted"},
                ),
            ),
            "manual_operator_total": _sum_samples(
                business_outbound_messages_total,
                "business_outbound_messages_total",
                (
                    {"delivery_mode": "manual_operator_send", "outcome": "accepted"},
                    {"delivery_mode": "manual_operator_media_send", "outcome": "accepted"},
                ),
            ),
            "ai_auto_reply_total": _sum_samples(
                business_outbound_messages_total,
                "business_outbound_messages_total",
                (
                    {"delivery_mode": "ai_auto_reply", "outcome": "accepted"},
                    {"delivery_mode": "rule_auto_reply", "outcome": "accepted"},
                ),
            ),
            "template_send_total": _sum_samples(
                business_outbound_messages_total,
                "business_outbound_messages_total",
                (
                    {"delivery_mode": "template_send", "outcome": "accepted"},
                ),
            ),
        },
        ai={
            "queued_total": _sum_samples(
                business_ai_replies_total,
                "business_ai_replies_total",
                (
                    {"outcome": "queued"},
                ),
            ),
            "success_total": _sum_samples(
                business_ai_replies_total,
                "business_ai_replies_total",
                (
                    {"outcome": "success"},
                ),
            ),
            "routed_total": _sum_samples(
                business_ai_replies_total,
                "business_ai_replies_total",
                (
                    {"outcome": "routed"},
                ),
            ),
            "fallback_total": _sum_samples(
                business_ai_replies_total,
                "business_ai_replies_total",
                (
                    {"outcome": "fallback"},
                ),
            ),
            "disabled_total": _sum_samples(
                business_ai_replies_total,
                "business_ai_replies_total",
                (
                    {"outcome": "disabled"},
                ),
            ),
            "skipped_handover_total": _sum_samples(
                business_ai_replies_total,
                "business_ai_replies_total",
                (
                    {"outcome": "skipped_handover"},
                ),
            ),
        },
        templates={
            "sent_total": _sum_samples(
                business_template_sends_total,
                "business_template_sends_total",
                (
                    {"status": "SENT"},
                ),
            ),
            "delivered_total": _sum_samples(
                business_template_sends_total,
                "business_template_sends_total",
                (
                    {"status": "DELIVERED"},
                ),
            ),
            "read_total": _sum_samples(
                business_template_sends_total,
                "business_template_sends_total",
                (
                    {"status": "READ"},
                ),
            ),
            "failed_total": _sum_samples(
                business_template_sends_total,
                "business_template_sends_total",
                (
                    {"status": "FAILED"},
                ),
            ),
            "failure_event_total": _sum_samples(
                business_template_send_failures_total,
                "business_template_send_failures_total",
                (
                    {},
                ),
            ),
        },
        translation={
            "conversation_view_translated_total": _sum_samples(
                translation_operations_total,
                "translation_operations_total",
                (
                    {"direction": "conversation_view", "outcome": "translated"},
                ),
            ),
            "conversation_view_fallback_total": _sum_samples(
                translation_operations_total,
                "translation_operations_total",
                (
                    {"direction": "conversation_view", "outcome": "fallback"},
                ),
            ),
            "conversation_view_skipped_total": _sum_samples(
                translation_operations_total,
                "translation_operations_total",
                (
                    {"direction": "conversation_view", "outcome": "skipped"},
                ),
            ),
            "outbound_operator_translated_total": _sum_samples(
                translation_operations_total,
                "translation_operations_total",
                (
                    {"direction": "outbound_operator", "outcome": "translated"},
                ),
            ),
            "outbound_operator_fallback_total": _sum_samples(
                translation_operations_total,
                "translation_operations_total",
                (
                    {"direction": "outbound_operator", "outcome": "fallback"},
                ),
            ),
            "outbound_operator_skipped_total": _sum_samples(
                translation_operations_total,
                "translation_operations_total",
                (
                    {"direction": "outbound_operator", "outcome": "skipped"},
                ),
            ),
        },
        webhook={
            "message_total": _read_sample(
                whatsapp_webhook_messages_total,
                "whatsapp_webhook_messages_total",
            ),
            "status_update_total": _read_sample(
                whatsapp_webhook_status_updates_total,
                "whatsapp_webhook_status_updates_total",
            ),
            "template_update_total": _sum_samples(
                whatsapp_webhook_template_updates_total,
                "whatsapp_webhook_template_updates_total",
                (
                    {},
                ),
            ),
            "phone_number_update_total": _sum_samples(
                whatsapp_webhook_phone_number_updates_total,
                "whatsapp_webhook_phone_number_updates_total",
                (
                    {},
                ),
            ),
            "signature_failure_total": _read_sample(
                whatsapp_webhook_signature_failures_total,
                "whatsapp_webhook_signature_failures_total",
            ),
            "delivered_event_total": _sum_samples(
                message_delivery_events_total,
                "message_delivery_events_total",
                (
                    {"status": "delivered"},
                ),
            ),
            "read_event_total": _sum_samples(
                message_delivery_events_total,
                "message_delivery_events_total",
                (
                    {"status": "read"},
                ),
            ),
            "failed_event_total": _sum_samples(
                message_delivery_events_total,
                "message_delivery_events_total",
                (
                    {"status": "failed"},
                ),
            ),
        },
        queue={
            "queued_total": _read_sample(
                queue_jobs_total,
                "queue_jobs_total",
                {"queue": "ai_generation", "status": "queued"},
            ),
            "completed_total": _read_sample(
                queue_jobs_total,
                "queue_jobs_total",
                {"queue": "ai_generation", "status": "completed"},
            ),
            "retried_total": _read_sample(
                queue_jobs_total,
                "queue_jobs_total",
                {"queue": "ai_generation", "status": "retried"},
            ),
            "failed_total": _read_sample(
                queue_jobs_total,
                "queue_jobs_total",
                {"queue": "ai_generation", "status": "failed"},
            ),
            "queued_current": _read_sample(
                queue_jobs_current,
                "queue_jobs_current",
                {"queue": "ai_generation", "status": "queued"},
            ),
            "processing_current": _read_sample(
                queue_jobs_current,
                "queue_jobs_current",
                {"queue": "ai_generation", "status": "processing"},
            ),
            "completed_current": _read_sample(
                queue_jobs_current,
                "queue_jobs_current",
                {"queue": "ai_generation", "status": "completed"},
            ),
            "failed_current": _read_sample(
                queue_jobs_current,
                "queue_jobs_current",
                {"queue": "ai_generation", "status": "failed"},
            ),
        },
        processing_failures={
            "mock_inbound_total": _read_sample(
                message_processing_failures_total,
                "message_processing_failures_total",
                {"provider": "mock", "stage": "mock_inbound"},
            ),
            "webhook_inbound_total": _read_sample(
                message_processing_failures_total,
                "message_processing_failures_total",
                {"provider": "whatsapp", "stage": "webhook_inbound"},
            ),
            "webhook_signature_total": _read_sample(
                message_processing_failures_total,
                "message_processing_failures_total",
                {"provider": "whatsapp", "stage": "webhook_signature"},
            ),
            "manual_operator_total": _sum_samples(
                message_processing_failures_total,
                "message_processing_failures_total",
                (
                    {"stage": "manual_operator_send"},
                    {"stage": "manual_operator_media_send"},
                ),
            ),
            "ai_auto_reply_total": _sum_samples(
                message_processing_failures_total,
                "message_processing_failures_total",
                (
                    {"stage": "ai_auto_reply"},
                    {"stage": "rule_auto_reply"},
                ),
            ),
            "template_send_total": _sum_samples(
                message_processing_failures_total,
                "message_processing_failures_total",
                (
                    {"stage": "template_send"},
                ),
            ),
        },
        task_reviews={
            "submissions_total": _sum_samples(
                task_submissions_total,
                "task_submissions_total",
                ({},),
            ),
            "under_review_total": _sum_samples(
                task_submissions_total,
                "task_submissions_total",
                ({"status": "under_review"},),
            ),
            "approved_total": _sum_samples(
                task_reviews_total,
                "task_reviews_total",
                ({"decision": "approved"},),
            ),
            "rejected_total": _sum_samples(
                task_reviews_total,
                "task_reviews_total",
                ({"decision": "rejected"},),
            ),
        },
        tickets={
            "created_total": _sum_samples(
                tickets_created_total,
                "tickets_created_total",
                ({},),
            ),
            "appeal_total": _sum_samples(
                tickets_created_total,
                "tickets_created_total",
                ({"ticket_type": "appeal"},),
            ),
            "help_total": _sum_samples(
                tickets_created_total,
                "tickets_created_total",
                ({"ticket_type": "help"},),
            ),
            "complaint_total": _sum_samples(
                tickets_created_total,
                "tickets_created_total",
                ({"ticket_type": "complaint"},),
            ),
            "resolved_total": _sum_samples(
                tickets_status_transition_total,
                "tickets_status_transition_total",
                ({"status": "resolved"},),
            ),
            "rejected_total": _sum_samples(
                tickets_status_transition_total,
                "tickets_status_transition_total",
                ({"status": "rejected"},),
            ),
            "closed_total": _sum_samples(
                tickets_status_transition_total,
                "tickets_status_transition_total",
                ({"status": "closed"},),
            ),
        },
    )


def _read_sample(
    metric: Counter | Gauge,
    sample_name: str,
    labels: Mapping[str, str] | None = None,
) -> float:
    for sample in _iter_metric_samples(metric):
        if sample.name != sample_name:
            continue
        if _labels_match(sample.labels, labels):
            return float(sample.value)
    return 0.0


def _sum_samples(
    metric: Counter | Gauge,
    sample_name: str,
    filters: Iterable[Mapping[str, str]],
) -> float:
    total = 0.0
    matched_any_filter = False
    for label_filter in filters:
        matched_any_filter = True
        total += _sum_matching_samples(metric, sample_name, label_filter)
    if matched_any_filter:
        return total
    return _sum_matching_samples(metric, sample_name, None)


def _sum_matching_samples(
    metric: Counter | Gauge,
    sample_name: str,
    labels: Mapping[str, str] | None,
) -> float:
    total = 0.0
    for sample in _iter_metric_samples(metric):
        if sample.name != sample_name:
            continue
        if _labels_match(sample.labels, labels):
            total += float(sample.value)
    return total


def _iter_metric_samples(metric: Counter | Gauge):
    for collected_metric in metric.collect():
        yield from collected_metric.samples


def _labels_match(
    actual: Mapping[str, str],
    expected: Mapping[str, str] | None,
) -> bool:
    if expected is None:
        return True
    return all(actual.get(key) == value for key, value in expected.items())
