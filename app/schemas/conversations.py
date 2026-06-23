from pydantic import BaseModel, Field


class ConversationSummary(BaseModel):
    account_id: str
    conversation_id: str
    waba_id: str | None = None
    phone_number_id: str | None = None
    customer_id: str
    customer_language: str
    customer_language_source: str
    status: str
    management_mode: str
    ai_enabled: bool
    assigned_agent_id: str | None = None
    assigned_agent_name: str | None = None
    last_message_at: str | None = None
    last_message_preview: str | None = None
    latest_intent_name: str | None = None
    latest_handover_recommended: bool = False
    latest_handover_reason: str | None = None
    customer_lifecycle_status: str | None = None
    is_sleeping: bool = False
    last_customer_message_at: str | None = None


class ConversationMessageView(BaseModel):
    message_id: str
    waba_id: str | None = None
    phone_number_id: str | None = None
    provider_message_id: str | None = None
    provider_media_id: str | None = None
    direction: str
    message_type: str
    language_code: str | None = None
    translated_language_code: str | None = None
    original_text: str | None = None
    translated_text: str | None = None
    console_text: str | None = None
    delivered_text: str | None = None
    translation_kind: str | None = None
    sender_id: str | None = None
    recipient_id: str | None = None
    ai_generated: bool
    delivery_status: str | None = None
    delivered_at: str | None = None
    read_at: str | None = None
    delivery_status_updated_at: str | None = None
    created_at: str
    payload: dict[str, object] | None = None


class ConversationTimelineItem(BaseModel):
    id: str
    item_type: str
    label: str
    title: str
    summary: str
    actor_type: str | None = None
    actor_id: str | None = None
    created_at: str
    payload: dict[str, object] | None = None


class ForwardMessageRequest(BaseModel):
    target_conversation_id: str
    include_context: bool = False


class OutboundMessageRequest(BaseModel):
    text: str = Field(min_length=1)
    agent_id: str | None = None


class OutboundMessageResponse(BaseModel):
    conversation_id: str
    account_id: str
    waba_id: str | None = None
    phone_number_id: str | None = None
    original_text: str
    delivered_text: str
    source_language: str
    target_language: str
    translated: bool
    message_id: str
    provider: str
    provider_message_id: str | None = None
