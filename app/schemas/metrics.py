from pydantic import BaseModel, Field


class InboundMetricsSummary(BaseModel):
    mock_total: float = 0
    whatsapp_webhook_total: float = 0
    accepted_total: float = 0
    duplicate_total: float = 0
    skipped_total: float = 0


class OutboundMetricsSummary(BaseModel):
    accepted_total: float = 0
    failed_total: float = 0
    echo_total: float = 0
    manual_operator_total: float = 0
    ai_auto_reply_total: float = 0
    template_send_total: float = 0


class AIMetricsSummary(BaseModel):
    queued_total: float = 0
    success_total: float = 0
    routed_total: float = 0
    fallback_total: float = 0
    disabled_total: float = 0
    skipped_handover_total: float = 0


class TemplateMetricsSummary(BaseModel):
    sent_total: float = 0
    delivered_total: float = 0
    read_total: float = 0
    failed_total: float = 0
    failure_event_total: float = 0


class TranslationMetricsSummary(BaseModel):
    conversation_view_translated_total: float = 0
    conversation_view_fallback_total: float = 0
    conversation_view_skipped_total: float = 0
    outbound_operator_translated_total: float = 0
    outbound_operator_fallback_total: float = 0
    outbound_operator_skipped_total: float = 0


class WebhookMetricsSummary(BaseModel):
    message_total: float = 0
    status_update_total: float = 0
    template_update_total: float = 0
    phone_number_update_total: float = 0
    signature_failure_total: float = 0
    delivered_event_total: float = 0
    read_event_total: float = 0
    failed_event_total: float = 0


class QueueMetricsSummary(BaseModel):
    queued_total: float = 0
    completed_total: float = 0
    retried_total: float = 0
    failed_total: float = 0
    queued_current: float = 0
    processing_current: float = 0
    completed_current: float = 0
    failed_current: float = 0


class ProcessingFailureMetricsSummary(BaseModel):
    mock_inbound_total: float = 0
    webhook_inbound_total: float = 0
    webhook_signature_total: float = 0
    manual_operator_total: float = 0
    ai_auto_reply_total: float = 0
    template_send_total: float = 0


class TaskReviewMetricsSummary(BaseModel):
    submissions_total: float = 0
    under_review_total: float = 0
    approved_total: float = 0
    rejected_total: float = 0


class TicketMetricsSummary(BaseModel):
    created_total: float = 0
    appeal_total: float = 0
    help_total: float = 0
    complaint_total: float = 0
    resolved_total: float = 0
    rejected_total: float = 0
    closed_total: float = 0


class MetricsSummaryResponse(BaseModel):
    generated_at: str
    inbound: InboundMetricsSummary = Field(default_factory=InboundMetricsSummary)
    outbound: OutboundMetricsSummary = Field(default_factory=OutboundMetricsSummary)
    ai: AIMetricsSummary = Field(default_factory=AIMetricsSummary)
    templates: TemplateMetricsSummary = Field(default_factory=TemplateMetricsSummary)
    translation: TranslationMetricsSummary = Field(default_factory=TranslationMetricsSummary)
    webhook: WebhookMetricsSummary = Field(default_factory=WebhookMetricsSummary)
    queue: QueueMetricsSummary = Field(default_factory=QueueMetricsSummary)
    processing_failures: ProcessingFailureMetricsSummary = Field(
        default_factory=ProcessingFailureMetricsSummary
    )
    task_reviews: TaskReviewMetricsSummary = Field(default_factory=TaskReviewMetricsSummary)
    tickets: TicketMetricsSummary = Field(default_factory=TicketMetricsSummary)
