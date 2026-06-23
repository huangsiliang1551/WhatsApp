from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class WhatsAppWebhookTextContent(BaseModel):
    body: str = Field(min_length=1)


class WhatsAppWebhookReplyContent(BaseModel):
    id: str | None = None
    title: str | None = None


class WhatsAppWebhookFlowReplyContent(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str | None = None
    body: str | None = None
    response_json: dict[str, Any] | None = None


class WhatsAppWebhookButtonContent(BaseModel):
    payload: str | None = None
    text: str | None = None


class WhatsAppWebhookInteractiveContent(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str = Field(min_length=1)
    button_reply: WhatsAppWebhookReplyContent | None = None
    list_reply: WhatsAppWebhookReplyContent | None = None
    nfm_reply: WhatsAppWebhookFlowReplyContent | None = None


class WhatsAppWebhookImageContent(BaseModel):
    id: str | None = None
    mime_type: str | None = None
    sha256: str | None = None
    caption: str | None = None


class WhatsAppWebhookAudioContent(BaseModel):
    id: str | None = None
    mime_type: str | None = None
    sha256: str | None = None
    voice: bool | None = None


class WhatsAppWebhookVideoContent(BaseModel):
    id: str | None = None
    mime_type: str | None = None
    sha256: str | None = None
    caption: str | None = None


class WhatsAppWebhookDocumentContent(BaseModel):
    id: str | None = None
    mime_type: str | None = None
    sha256: str | None = None
    filename: str | None = None
    caption: str | None = None


class WhatsAppWebhookStickerContent(BaseModel):
    id: str | None = None
    mime_type: str | None = None
    sha256: str | None = None
    animated: bool | None = None


class WhatsAppWebhookReactionContent(BaseModel):
    message_id: str | None = None
    emoji: str | None = None


class WhatsAppWebhookLocationContent(BaseModel):
    latitude: float | None = None
    longitude: float | None = None
    name: str | None = None
    address: str | None = None
    url: str | None = None


class WhatsAppWebhookOrderProductItem(BaseModel):
    product_retailer_id: str | None = None
    quantity: int | None = None
    item_price: str | int | float | None = None
    currency: str | None = None


class WhatsAppWebhookOrderContent(BaseModel):
    catalog_id: str | None = None
    product_items: list[WhatsAppWebhookOrderProductItem] = Field(default_factory=list)


class WhatsAppWebhookReferredProductContent(BaseModel):
    catalog_id: str | None = None
    product_retailer_id: str | None = None


class WhatsAppWebhookContextContent(BaseModel):
    model_config = ConfigDict(extra="allow")

    from_: str | None = Field(default=None, alias="from")
    id: str | None = None
    forwarded: bool | None = None
    frequently_forwarded: bool | None = None
    referred_product: WhatsAppWebhookReferredProductContent | None = None


class WhatsAppWebhookReferralContent(BaseModel):
    model_config = ConfigDict(extra="allow")

    source_url: str | None = None
    source_type: str | None = None
    source_id: str | None = None
    headline: str | None = None
    body: str | None = None
    media_type: str | None = None
    image_url: str | None = None
    video_url: str | None = None
    thumbnail_url: str | None = None
    ctwa_clid: str | None = None


class WhatsAppWebhookSystemContent(BaseModel):
    model_config = ConfigDict(extra="allow")

    body: str | None = None
    identity: str | None = None
    new_wa_id: str | None = None
    wa_id: str | None = None
    type: str | None = None


class WhatsAppWebhookSharedContactName(BaseModel):
    model_config = ConfigDict(extra="allow")

    formatted_name: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    middle_name: str | None = None
    suffix: str | None = None
    prefix: str | None = None


class WhatsAppWebhookSharedContactPhone(BaseModel):
    model_config = ConfigDict(extra="allow")

    phone: str | None = None
    type: str | None = None
    wa_id: str | None = None


class WhatsAppWebhookSharedContactEmail(BaseModel):
    model_config = ConfigDict(extra="allow")

    email: str | None = None
    type: str | None = None


class WhatsAppWebhookSharedContactUrl(BaseModel):
    model_config = ConfigDict(extra="allow")

    url: str | None = None
    type: str | None = None


class WhatsAppWebhookSharedContactAddress(BaseModel):
    model_config = ConfigDict(extra="allow")

    street: str | None = None
    city: str | None = None
    state: str | None = None
    zip: str | None = None
    country: str | None = None
    country_code: str | None = None
    type: str | None = None


class WhatsAppWebhookSharedContactOrg(BaseModel):
    model_config = ConfigDict(extra="allow")

    company: str | None = None
    department: str | None = None
    title: str | None = None


class WhatsAppWebhookSharedContact(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: WhatsAppWebhookSharedContactName | None = None
    birthday: str | None = None
    phones: list[WhatsAppWebhookSharedContactPhone] = Field(default_factory=list)
    emails: list[WhatsAppWebhookSharedContactEmail] = Field(default_factory=list)
    urls: list[WhatsAppWebhookSharedContactUrl] = Field(default_factory=list)
    addresses: list[WhatsAppWebhookSharedContactAddress] = Field(default_factory=list)
    org: WhatsAppWebhookSharedContactOrg | None = None


class WhatsAppWebhookMessage(BaseModel):
    from_: str = Field(alias="from", min_length=1)
    id: str = Field(min_length=1)
    timestamp: str | None = None
    type: str = Field(min_length=1)
    context: WhatsAppWebhookContextContent | None = None
    text: WhatsAppWebhookTextContent | None = None
    interactive: WhatsAppWebhookInteractiveContent | None = None
    image: WhatsAppWebhookImageContent | None = None
    audio: WhatsAppWebhookAudioContent | None = None
    video: WhatsAppWebhookVideoContent | None = None
    document: WhatsAppWebhookDocumentContent | None = None
    button: WhatsAppWebhookButtonContent | None = None
    sticker: WhatsAppWebhookStickerContent | None = None
    reaction: WhatsAppWebhookReactionContent | None = None
    location: WhatsAppWebhookLocationContent | None = None
    order: WhatsAppWebhookOrderContent | None = None
    referral: WhatsAppWebhookReferralContent | None = None
    system: WhatsAppWebhookSystemContent | None = None
    contacts: list[WhatsAppWebhookSharedContact] = Field(default_factory=list)


class WhatsAppWebhookContactProfile(BaseModel):
    name: str | None = None


class WhatsAppWebhookContact(BaseModel):
    wa_id: str | None = None
    profile: WhatsAppWebhookContactProfile | None = None


class WhatsAppWebhookMetadata(BaseModel):
    display_phone_number: str | None = None
    phone_number_id: str | None = None


class WhatsAppWebhookPricing(BaseModel):
    billable: bool | None = None
    category: str | None = None
    pricing_model: str | None = None


class WhatsAppWebhookConversationOrigin(BaseModel):
    type: str | None = None


class WhatsAppWebhookConversation(BaseModel):
    id: str | None = None
    expiration_timestamp: str | None = None
    origin: WhatsAppWebhookConversationOrigin | None = None


class WhatsAppWebhookStatusErrorData(BaseModel):
    details: str | None = None


class WhatsAppWebhookStatusError(BaseModel):
    code: int | str | None = None
    title: str | None = None
    message: str | None = None
    error_data: WhatsAppWebhookStatusErrorData | None = None


class WhatsAppWebhookStatus(BaseModel):
    id: str = Field(min_length=1)
    status: str = Field(min_length=1)
    timestamp: str | None = None
    recipient_id: str | None = None
    conversation: WhatsAppWebhookConversation | None = None
    pricing: WhatsAppWebhookPricing | None = None
    estimated_cost: float | None = None
    errors: list[WhatsAppWebhookStatusError] = Field(default_factory=list)


class WhatsAppWebhookValue(BaseModel):
    model_config = ConfigDict(extra="allow")

    messaging_product: str | None = None
    metadata: WhatsAppWebhookMetadata | None = None
    contacts: list[WhatsAppWebhookContact] = Field(default_factory=list)
    messages: list[WhatsAppWebhookMessage] = Field(default_factory=list)
    statuses: list[WhatsAppWebhookStatus] = Field(default_factory=list)
    event: str | None = None
    message_template_id: str | None = None
    message_template_name: str | None = None
    message_template_language: str | None = None
    reason: str | None = None
    previous_quality_score: str | None = None
    new_quality_score: str | None = None
    disable_info: dict[str, Any] | None = None
    phone_number_id: str | None = None
    display_phone_number: str | None = None
    current_limit: str | int | None = None
    decision: str | None = None
    requested_verified_name: str | None = None
    rejection_reason: str | None = None
    max_daily_conversations_per_business: int | None = None


class WhatsAppWebhookChange(BaseModel):
    field: str = Field(min_length=1)
    value: WhatsAppWebhookValue


class WhatsAppWebhookEntry(BaseModel):
    id: str = Field(min_length=1)
    changes: list[WhatsAppWebhookChange] = Field(default_factory=list)


class WhatsAppWebhookPayload(BaseModel):
    object: str = Field(min_length=1)
    entry: list[WhatsAppWebhookEntry] = Field(default_factory=list)
