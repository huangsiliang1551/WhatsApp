from typing import Literal

from pydantic import BaseModel, Field, model_validator


TemplateCategory = Literal["MARKETING", "UTILITY", "AUTHENTICATION"]
TemplateStatus = Literal["PENDING", "APPROVED", "REJECTED", "DRAFT", "DISABLED", "PAUSED"]
TemplateSendStatus = Literal["QUEUED", "SENT", "DELIVERED", "READ", "FAILED"]


class TemplateDraftRequest(BaseModel):
    account_id: str = Field(min_length=1)
    waba_id: str | None = None
    name: str = Field(min_length=1, max_length=100)
    language: str = Field(min_length=1, max_length=16)
    category: TemplateCategory
    body_text: str = Field(min_length=1)
    header_text: str | None = None
    header_media_asset_id: str | None = Field(default=None, min_length=1)
    header_media_handle: str | None = Field(default=None, min_length=1)
    footer_text: str | None = None
    sample_variables: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_header_mode(self) -> "TemplateDraftRequest":
        if self.header_text and self.header_media_asset_id:
            raise ValueError("Template header_text and header_media_asset_id cannot both be set.")
        if self.header_media_handle and not self.header_media_asset_id:
            raise ValueError("Template header_media_handle requires header_media_asset_id.")
        return self


class TemplateDraftUpdateRequest(BaseModel):
    waba_id: str | None = Field(default=None)
    name: str | None = Field(default=None, min_length=1, max_length=100)
    language: str | None = Field(default=None, min_length=1, max_length=16)
    category: TemplateCategory | None = None
    body_text: str | None = Field(default=None, min_length=1)
    header_text: str | None = None
    header_media_asset_id: str | None = Field(default=None, min_length=1)
    header_media_handle: str | None = Field(default=None, min_length=1)
    footer_text: str | None = None
    sample_variables: dict[str, str] | None = None


class TemplateStatusUpdateRequest(BaseModel):
    status: TemplateStatus
    rejected_reason: str | None = None
    meta_template_id: str | None = None


class TemplateSendRequest(BaseModel):
    account_id: str = Field(min_length=1)
    conversation_id: str = Field(min_length=1)
    phone_number_id: str | None = Field(default=None, min_length=1)
    variables: dict[str, str] = Field(default_factory=dict)
    agent_id: str | None = None
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=128)


class MessageTemplateView(BaseModel):
    template_id: str
    account_id: str
    waba_id: str | None = None
    name: str
    language: str
    category: TemplateCategory
    status: TemplateStatus
    meta_template_id: str | None = None
    rejected_reason: str | None = None
    body_text: str
    header_text: str | None = None
    header_media_asset_id: str | None = None
    header_media_asset_name: str | None = None
    header_media_asset_type: str | None = None
    header_media_handle: str | None = None
    footer_text: str | None = None
    sample_variables: dict[str, str] = Field(default_factory=dict)
    submitted_at: str | None = None
    last_synced_at: str | None = None
    created_at: str
    updated_at: str


class TemplateSyncRequest(BaseModel):
    account_id: str = Field(min_length=1)
    waba_id: str = Field(min_length=1)
    import_missing: bool = True


class TemplateSubmitResponse(BaseModel):
    provider: str
    action: str
    remote_status: str
    template: MessageTemplateView


class TemplateSyncResponse(BaseModel):
    account_id: str
    waba_id: str
    provider: str
    created_count: int
    updated_count: int
    skipped_count: int
    templates: list[MessageTemplateView] = Field(default_factory=list)


class TemplateSendLogView(BaseModel):
    id: str
    account_id: str
    template_id: str | None = None
    waba_id: str | None = None
    template_name: str | None = None
    template_language: str | None = None
    template_category: TemplateCategory | None = None
    template_code: str | None = None
    header_media_asset_id: str | None = None
    header_media_asset_name: str | None = None
    header_media_asset_type: str | None = None
    header_media_provider_media_id: str | None = Field(
        default=None,
        description="Phone-Number-ID scoped provider media reference used for the template header.",
    )
    header_media_meta_media_id: str | None = Field(
        default=None,
        deprecated=True,
        description="Legacy compatibility field. Prefer header_media_provider_media_id.",
    )
    header_media_sync_status: str | None = None
    conversation_id: str | None = None
    external_conversation_id: str | None = None
    internal_conversation_id: str | None = None
    phone_number_id: str | None = None
    wa_id: str
    message_id: str | None = None
    idempotency_key: str | None = None
    status: TemplateSendStatus
    error_code: str | None = None
    conversation_origin_type: str | None = None
    conversation_category: str | None = None
    pricing_model: str | None = None
    billable: bool = False
    estimated_cost: float = 0
    sent_at: str | None = None
    delivered_at: str | None = None
    read_at: str | None = None
    failed_at: str | None = None
    last_status_at: str | None = None
    created_at: str


class TemplateSendResponse(BaseModel):
    template_id: str
    account_id: str
    conversation_id: str
    external_conversation_id: str
    internal_conversation_id: str
    phone_number_id: str | None = None
    status: TemplateSendStatus
    delivered_text: str
    template_language: str
    header_media_asset_id: str | None = None
    header_media_asset_name: str | None = None
    header_media_asset_type: str | None = None
    header_media_provider_media_id: str | None = Field(
        default=None,
        description="Phone-Number-ID scoped provider media reference used for the template header.",
    )
    header_media_meta_media_id: str | None = Field(
        default=None,
        deprecated=True,
        description="Legacy compatibility field. Prefer header_media_provider_media_id.",
    )
    header_media_sync_status: str | None = None
    message_id: str | None = None
    send_log_id: str
    provider: str | None = None


class TemplateStatsSummary(BaseModel):
    send_count: int = 0
    delivered_count: int = 0
    delivery_rate: float = 0
    read_count: int = 0
    read_rate: float = 0
    read_rate_by_send: float = 0
    failed_count: int = 0
    billable_count: int = 0
    estimated_cost: float = 0
    estimated_cost_status: str = "not_applicable"
    estimated_cost_note: str | None = None


class TemplateStatsDailyRow(BaseModel):
    date: str
    account_id: str
    template_id: str | None = None
    waba_id: str | None = None
    phone_number_id: str | None = None
    template_name: str
    template_code: str | None = None
    template_category: TemplateCategory
    template_language: str
    send_count: int
    delivered_count: int
    delivery_rate: float
    read_count: int
    read_rate: float
    read_rate_by_send: float
    failed_count: int
    billable_count: int = 0
    estimated_cost: float = 0
    estimated_cost_status: str = "not_applicable"
    estimated_cost_note: str | None = None


class TemplateStatsFailureReason(BaseModel):
    error_code: str
    failed_count: int


class TemplateStatsHourlyRow(BaseModel):
    hour_bucket: int
    send_count: int
    delivered_count: int
    read_count: int
    failed_count: int


class TemplateStatsDetailResponse(BaseModel):
    template_id: str
    template_name: str
    account_id: str
    template_language: str
    template_category: TemplateCategory
    summary: TemplateStatsSummary
    daily_rows: list[TemplateStatsDailyRow] = Field(default_factory=list)
    hourly_rows: list[TemplateStatsHourlyRow] = Field(default_factory=list)
    failure_reasons: list[TemplateStatsFailureReason] = Field(default_factory=list)


class TemplateStatsRebuildResponse(BaseModel):
    account_id: str | None = None
    waba_id: str | None = None
    phone_number_id: str | None = None
    date_from: str | None = None
    date_to: str | None = None
    rebuilt_at: str
