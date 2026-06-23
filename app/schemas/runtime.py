from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field


class AccountRegistrationRequest(BaseModel):
    account_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    provider_type: Literal["mock", "whatsapp"] = "mock"


class AiToggleRequest(BaseModel):
    enabled: bool
    agent_id: str | None = Field(default=None, min_length=1, max_length=255)


class StatusToggleRequest(BaseModel):
    is_active: bool


class ConversationHandoverRequest(BaseModel):
    management_mode: Literal["ai_managed", "human_managed", "paused"]
    agent_id: str | None = None
    reason: str | None = Field(default=None, min_length=1, max_length=255)


class AccountRuntimeState(BaseModel):
    account_id: str
    display_name: str
    provider_type: str
    is_active: bool
    ai_enabled: bool


class AiBlockingReason(BaseModel):
    scope: Literal["global", "account", "conversation", "management_mode", "waba", "phone_number"]
    code: str
    message: str


class ConversationRuntimeState(BaseModel):
    account_id: str
    conversation_id: str
    phone_number_id: str | None = None
    status: str
    ai_enabled: bool
    management_mode: Literal["ai_managed", "human_managed", "paused"]
    assigned_agent_id: str | None = None
    assigned_agent_name: str | None = None


class RuntimeStateResponse(BaseModel):
    global_ai_enabled: bool
    accounts: list[AccountRuntimeState]
    conversations: list[ConversationRuntimeState]


class ConversationAiStatusResponse(BaseModel):
    account_id: str
    conversation_id: str
    phone_number_id: str | None = None
    global_ai_enabled: bool
    account_ai_enabled: bool
    conversation_ai_enabled: bool
    status: str
    management_mode: Literal["ai_managed", "human_managed", "paused"]
    effective_ai_enabled: bool
    assigned_agent_id: str | None = None
    blocking_reasons: list[AiBlockingReason] = Field(default_factory=list)
    primary_blocking_reason: AiBlockingReason | None = None


class RuntimeConfigSummary(BaseModel):
    app_env: str
    test_mode: bool
    messaging_provider: str
    ai_provider: str
    ai_model: str
    ecommerce_provider: str
    openai_configured: bool
    deepseek_configured: bool
    translation_provider: str
    live_translation_enabled: bool
    console_language: str
    auto_translate_on_human_handover: bool
    auto_translate_on_conversation_open: bool
    auto_translate_operator_outbound: bool
    queue_backend: str
    queue_max_retries: int
    queue_poll_timeout_seconds: int


class ProviderStatusBufferEntry(BaseModel):
    id: str
    account_id: str
    provider_name: str
    waba_id: str | None = None
    phone_number_id: str | None = None
    provider_message_id: str
    external_status: str
    recipient_id: str | None = None
    occurred_at: str | None = None
    error_code: str | None = None
    payload: dict[str, object] = Field(default_factory=dict)
    first_seen_at: str
    last_seen_at: str
    seen_count: int
    replay_state: str
    replayed_at: str | None = None
    replayed_message_event_id: str | None = None
    replay_error: str | None = None
    pending_age_seconds: float


class ProviderStatusBufferReplayRequest(BaseModel):
    account_id: str = Field(min_length=1)
    provider_name: str | None = Field(default=None, min_length=1)
    provider_message_id: str | None = Field(default=None, min_length=1)
    external_status: str | None = Field(default=None, min_length=1)
    waba_id: str | None = Field(default=None, min_length=1)
    phone_number_id: str | None = Field(default=None, min_length=1)
    limit: int = Field(default=100, ge=1, le=500)


class ProviderStatusBufferListResponse(BaseModel):
    items: list[ProviderStatusBufferEntry] = Field(default_factory=list)
    returned_count: int
    pending_count: int
    replayed_count: int


class ProviderStatusBufferReplayResponse(BaseModel):
    account_id: str
    provider_name: str | None = None
    provider_message_id: str | None = None
    external_status: str | None = None
    waba_id: str | None = None
    phone_number_id: str | None = None
    checked_count: int
    replayed_count: int
    failed_count: int


class LaunchReadinessCheck(BaseModel):
    key: str
    category: Literal["runtime", "database", "queue", "ai", "messaging", "meta", "monitoring", "operations"]
    status: Literal["pass", "warning", "blocker"]
    scope: Literal["system", "account"] = "system"
    title: str
    message: str
    action_hint: str | None = None
    account_id: str | None = None
    waba_id: str | None = None
    phone_number_id: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)


class LaunchReadinessSummary(BaseModel):
    checked_at: str
    overall_status: Literal["ready", "needs_attention", "blocked"]
    scope: Literal["system", "account"] = "system"
    account_id: str | None = None
    blocker_count: int
    warning_count: int
    passed_count: int
    active_account_count: int
    meta_account_count: int
    meta_ready_account_count: int
    messaging_provider: str
    ai_provider: str
    queue_backend: str
    metadata: dict[str, object] = Field(default_factory=dict)


def _make_empty_summary() -> "LaunchReadinessSummary":
    return LaunchReadinessSummary(
        checked_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        overall_status="needs_attention",
        blocker_count=0,
        warning_count=0,
        passed_count=0,
        active_account_count=0,
        meta_account_count=0,
        meta_ready_account_count=0,
        messaging_provider="unavailable",
        ai_provider="unavailable",
        queue_backend="unavailable",
    )


class LaunchReadinessResponse(BaseModel):
    summary: LaunchReadinessSummary = Field(default_factory=_make_empty_summary)
    checks: list[LaunchReadinessCheck] = Field(default_factory=list)
