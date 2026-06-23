from pydantic import BaseModel, Field


class WhatsAppStatsSummary(BaseModel):
    conversation_count: int = 0
    unique_customer_count: int = 0
    inbound_message_count: int = 0
    outbound_message_count: int = 0
    delivered_count: int = 0
    read_count: int = 0
    failed_count: int = 0
    billable_count: int = 0
    estimated_cost: float = 0
    estimated_cost_status: str = "not_applicable"
    estimated_cost_note: str | None = None


class WhatsAppStatsDailyRow(BaseModel):
    date: str
    hour_bucket: int | None = None
    account_id: str
    waba_id: str | None = None
    phone_number_id: str | None = None
    conversation_origin_type: str | None = None
    conversation_category: str | None = None
    pricing_model: str | None = None
    billable: bool = False
    conversation_count: int = 0
    unique_customer_count: int = 0
    inbound_message_count: int = 0
    outbound_message_count: int = 0
    delivered_count: int = 0
    read_count: int = 0
    failed_count: int = 0
    billable_count: int = 0
    estimated_cost: float = 0
    estimated_cost_status: str = "not_applicable"
    estimated_cost_note: str | None = None


class WhatsAppStatsDetailResponse(BaseModel):
    summary: WhatsAppStatsSummary
    daily_rows: list[WhatsAppStatsDailyRow] = Field(default_factory=list)
    generated_at: str | None = None


class WhatsAppStatsRebuildResponse(BaseModel):
    account_id: str | None = None
    waba_id: str | None = None
    phone_number_id: str | None = None
    date_from: str | None = None
    date_to: str | None = None
    rebuilt_at: str
