from typing import Literal

from pydantic import BaseModel, Field


WebhookSubscriptionStatus = Literal[
    "pending",
    "mock_subscribed",
    "remote_subscribed",
    "remote_pending",
    "subscribed",
]
WebhookVerificationStatus = Literal["pending", "verified", "failed", "unavailable"]
WebhookRuntimeStatus = Literal[
    "pending",
    "healthy",
    "verification_pending",
    "signature_failed",
    "signature_unavailable",
    "payload_invalid",
]
EmbeddedSignupSessionStatus = Literal["created", "completed", "failed"]
EmbeddedSignupCompletionStage = Literal[
    "pending_callback",
    "callback_recorded",
    "remote_confirmed",
    "local_waba_linked",
    "webhook_verification_pending",
    "failed",
]
EmbeddedSignupEventSource = Literal["operator", "provider_callback", "system_sync"]


class MetaPhoneNumber(BaseModel):
    phone_number_id: str = Field(min_length=1)
    display_phone_number: str = Field(min_length=1)
    verified_name: str | None = None
    quality_rating: Literal["GREEN", "YELLOW", "RED", "UNKNOWN"] = "UNKNOWN"
    is_registered: bool = False
    is_active: bool = True


class MetaPhoneNumberScopeView(BaseModel):
    account_id: str
    account_display_name: str
    account_is_active: bool = True
    meta_business_portfolio_id: str | None = None
    waba_id: str
    phone_number_id: str
    display_phone_number: str
    verified_name: str | None = None
    quality_rating: Literal["GREEN", "YELLOW", "RED", "UNKNOWN"] = "UNKNOWN"
    quality_event: str | None = None
    previous_quality_rating: str | None = None
    messaging_limit_tier: str | None = None
    max_daily_conversations_per_business: int | None = None
    last_quality_event_at: str | None = None
    is_registered: bool = False
    is_active: bool = True
    webhook_subscribed: bool = False
    webhook_subscription_status: WebhookSubscriptionStatus | None = None
    ready_for_webhook_delivery: bool = False
    ready_for_outbound_messages: bool = False
    ready_for_meta_activation: bool = False
    blocking_reasons: list[str] = Field(default_factory=list)


class ManualMetaAccountRequest(BaseModel):
    account_id: str | None = Field(default=None, min_length=1, description="可选，留空则系统自动生成")
    display_name: str = Field(min_length=1)
    meta_business_portfolio_id: str | None = None
    waba_id: str = Field(min_length=1)
    access_token: str = Field(min_length=1)
    token_source: Literal["system_user", "user_access_token"] = "system_user"
    app_secret: str | None = None
    notes: str | None = None
    phone_numbers: list[MetaPhoneNumber] = Field(default_factory=list)


class MetaAccountUpdateRequest(BaseModel):
    display_name: str = Field(min_length=1)
    meta_business_portfolio_id: str | None = None
    access_token: str | None = None
    verify_token: str | None = None
    app_secret: str | None = None
    token_source: Literal["system_user", "user_access_token", "embedded_signup"] | None = None
    notes: str | None = None
    phone_numbers: list[MetaPhoneNumber] = Field(default_factory=list)


class MetaScopeStatusUpdateRequest(BaseModel):
    is_active: bool


class EmbeddedSignupWebhookSubscriptionRequest(BaseModel):
    callback_url: str = Field(min_length=1)
    verify_token: str | None = None
    app_id: str | None = None


class EmbeddedSignupSessionRequest(BaseModel):
    account_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    redirect_uri: str = Field(min_length=1)
    webhook_subscription: EmbeddedSignupWebhookSubscriptionRequest | None = None


class EmbeddedSignupSessionSnapshot(BaseModel):
    waba_id: str | None = None
    meta_business_portfolio_id: str | None = None
    linked_phone_number_ids: list[str] = Field(default_factory=list)
    webhook_callback_url: str | None = None
    webhook_verify_token_present: bool = False
    webhook_app_secret_present: bool = False
    webhook_app_id: str | None = None
    webhook_subscription_status: WebhookSubscriptionStatus | None = None
    webhook_verification_status: WebhookVerificationStatus | None = None
    webhook_runtime_status: WebhookRuntimeStatus | None = None
    ready_for_webhook_delivery: bool | None = None
    ready_for_outbound_messages: bool | None = None
    ready_for_meta_activation: bool | None = None
    webhook_blocking_reasons: list[str] = Field(default_factory=list)


class EmbeddedSignupLaunchContext(BaseModel):
    session_id: str
    state: str
    callback_url: str
    redirect_uri: str
    expires_at: str
    parameters: dict[str, object] = Field(default_factory=dict)


class EmbeddedSignupCurrentWabaState(BaseModel):
    waba_id: str | None = None
    meta_business_portfolio_id: str | None = None
    webhook_callback_url: str | None = None
    webhook_verify_token_present: bool = False
    webhook_app_secret_present: bool = False
    webhook_app_id: str | None = None
    webhook_subscription_status: WebhookSubscriptionStatus | None = None
    webhook_verification_status: WebhookVerificationStatus | None = None
    webhook_runtime_status: WebhookRuntimeStatus | None = None
    ready_for_webhook_delivery: bool = False
    ready_for_outbound_messages: bool = False
    ready_for_meta_activation: bool = False
    webhook_blocking_reasons: list[str] = Field(default_factory=list)


class EmbeddedSignupSession(BaseModel):
    session_id: str
    account_id: str
    display_name: str
    redirect_uri: str
    provider_name: str
    status: EmbeddedSignupSessionStatus = "created"
    completion_stage: EmbeddedSignupCompletionStage
    event_source: EmbeddedSignupEventSource = "operator"
    remote_confirmed: bool = False
    waba_id: str | None = None
    linked_waba_id: str | None = None
    provider_waba_id: str | None = None
    meta_business_portfolio_id: str | None = None
    setup_session_id: str | None = None
    linked_phone_number_ids: list[str] = Field(default_factory=list)
    authorization_code_present: bool = False
    system_user_access_token_present: bool = False
    launch_context: EmbeddedSignupLaunchContext | None = None
    callback_received_at: str | None = None
    completed_at: str | None = None
    completion_message: str | None = None
    error_message: str | None = None
    webhook_callback_url: str | None = None
    webhook_verify_token_present: bool = False
    webhook_app_secret_present: bool = False
    webhook_app_id: str | None = None
    webhook_subscription_status: WebhookSubscriptionStatus | None = None
    webhook_verification_status: WebhookVerificationStatus | None = None
    webhook_runtime_status: WebhookRuntimeStatus | None = None
    ready_for_webhook_delivery: bool = False
    ready_for_outbound_messages: bool = False
    ready_for_meta_activation: bool = False
    webhook_blocking_reasons: list[str] = Field(default_factory=list)
    completion_webhook_subscription_status: WebhookSubscriptionStatus | None = None
    completion_webhook_verification_status: WebhookVerificationStatus | None = None
    completion_webhook_runtime_status: WebhookRuntimeStatus | None = None
    completion_ready_for_webhook_delivery: bool | None = None
    completion_ready_for_outbound_messages: bool | None = None
    completion_ready_for_meta_activation: bool | None = None
    completion_webhook_blocking_reasons: list[str] = Field(default_factory=list)
    session_snapshot: EmbeddedSignupSessionSnapshot | None = None
    current_waba_state: EmbeddedSignupCurrentWabaState | None = None


class CompleteEmbeddedSignupSessionRequest(BaseModel):
    waba_id: str | None = None
    meta_business_portfolio_id: str | None = None
    phone_number_ids: list[str] = Field(default_factory=list)
    setup_session_id: str | None = None
    authorization_code: str | None = None
    system_user_access_token: str | None = None
    raw_payload: dict[str, object] | None = None
    event_source: EmbeddedSignupEventSource = "operator"
    webhook_subscription: EmbeddedSignupWebhookSubscriptionRequest | None = None


class EmbeddedSignupCallbackRequest(BaseModel):
    status: Literal["completed", "failed"]
    state: str | None = None
    waba_id: str | None = None
    meta_business_portfolio_id: str | None = None
    phone_number_ids: list[str] = Field(default_factory=list)
    setup_session_id: str | None = None
    authorization_code: str | None = None
    system_user_access_token: str | None = None
    error_message: str | None = None
    raw_payload: dict[str, object] | None = None
    event_source: Literal["provider_callback", "system_sync"] = "provider_callback"
    webhook_subscription: EmbeddedSignupWebhookSubscriptionRequest | None = None


class FailEmbeddedSignupSessionRequest(BaseModel):
    error_message: str = Field(min_length=1)
    raw_payload: dict[str, object] | None = None
    event_source: EmbeddedSignupEventSource = "operator"


class WebhookSubscriptionRequest(BaseModel):
    callback_url: str = Field(min_length=1)
    verify_token: str | None = None
    app_id: str | None = None


class WebhookSubscriptionView(BaseModel):
    id: str
    account_id: str
    account_display_name: str
    meta_business_portfolio_id: str | None = None
    waba_id: str
    callback_url: str
    webhook_root_verify_path: str
    webhook_verify_path: str
    webhook_receive_path: str
    webhook_root_receive_path: str
    verify_token_present: bool = False
    app_secret_present: bool = False
    app_id: str | None = None
    status: WebhookSubscriptionStatus
    current_scope_state_applied: bool = False
    subscribed_at: str | None = None
    webhook_verification_status: WebhookVerificationStatus
    webhook_last_verified_at: str | None = None
    webhook_last_verification_error: str | None = None
    webhook_runtime_status: WebhookRuntimeStatus
    webhook_last_event_received_at: str | None = None
    webhook_last_message_received_at: str | None = None
    webhook_last_status_update_at: str | None = None
    webhook_last_management_event_at: str | None = None
    webhook_last_signature_failed_at: str | None = None
    webhook_signature_failure_count: int = 0
    webhook_runtime_error: str | None = None
    created_at: str
    updated_at: str


class MetaPhoneNumberSyncResponse(BaseModel):
    account_id: str
    waba_id: str
    provider_name: str
    sync_mode: str
    status: str
    synced_count: int = 0
    phone_numbers: list[MetaPhoneNumber] = Field(default_factory=list)
    message: str | None = None


class MetaWabaAccount(BaseModel):
    account_id: str
    display_name: str
    account_is_active: bool = True
    notes: str | None = None
    onboarding_mode: Literal["manual", "embedded_signup"]
    meta_business_portfolio_id: str
    waba_id: str
    token_source: Literal["system_user", "user_access_token", "embedded_signup"]
    is_active: bool = True
    webhook_subscribed: bool = False
    webhook_subscription_status: WebhookSubscriptionStatus | None = None
    webhook_callback_url: str | None = None
    webhook_root_verify_path: str
    webhook_verify_path: str
    webhook_receive_path: str
    webhook_root_receive_path: str
    webhook_verification_status: WebhookVerificationStatus = "pending"
    webhook_last_verified_at: str | None = None
    webhook_last_verification_error: str | None = None
    webhook_runtime_status: WebhookRuntimeStatus = "pending"
    webhook_last_event_received_at: str | None = None
    webhook_last_message_received_at: str | None = None
    webhook_last_status_update_at: str | None = None
    webhook_last_management_event_at: str | None = None
    webhook_last_signature_failed_at: str | None = None
    webhook_signature_failure_count: int = 0
    webhook_runtime_error: str | None = None
    has_access_token: bool = False
    has_verify_token: bool = False
    has_app_secret: bool = False
    phone_number_count: int = 0
    registered_phone_number_count: int = 0
    ready_for_webhook_verification: bool = False
    ready_for_webhook_delivery: bool = False
    ready_for_outbound_messages: bool = False
    ready_for_meta_activation: bool = False
    ready_for_formal_activation: bool = False
    has_root_webhook_routing_conflict: bool = False
    blocking_reasons: list[str] = Field(default_factory=list)
    phone_numbers: list[MetaPhoneNumber] = Field(default_factory=list)
