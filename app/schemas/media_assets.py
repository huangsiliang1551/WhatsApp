from typing import Literal

from pydantic import BaseModel, Field, model_validator


MediaAssetType = Literal["image", "audio", "video", "document"]


class MediaAssetCreateRequest(BaseModel):
    account_id: str = Field(min_length=1)
    waba_id: str | None = None
    phone_number_id: str | None = None
    name: str = Field(min_length=1, max_length=255)
    asset_type: MediaAssetType
    mime_type: str = Field(min_length=1, max_length=128)
    file_size: int | None = Field(default=None, ge=0)
    storage_key: str | None = None
    storage_url: str | None = None
    provider_media_id: str | None = Field(
        default=None,
        description="Phone-Number-ID scoped media reference returned by the messaging provider.",
    )
    provider_media_status: str | None = Field(
        default=None,
        description="Status for the phone-scoped provider media reference.",
    )
    meta_media_id: str | None = Field(
        default=None,
        deprecated=True,
        description="Legacy compatibility field. Prefer provider_media_id with phone_number_id.",
    )
    meta_media_status: str | None = Field(
        default=None,
        deprecated=True,
        description="Legacy compatibility field. Prefer provider_media_status.",
    )
    source: str = Field(default="manual_upload", min_length=1, max_length=64)
    tags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_reference(self) -> "MediaAssetCreateRequest":
        provider_media_id = self.__dict__.get("provider_media_id")
        meta_media_id = self.__dict__.get("meta_media_id")
        resolved_provider_media_id = provider_media_id or meta_media_id
        if not self.storage_key and not self.storage_url and not resolved_provider_media_id:
            raise ValueError(
                "Media asset requires storage_key, storage_url, or provider_media_id."
        )
        if provider_media_id and meta_media_id and provider_media_id != meta_media_id:
            raise ValueError("provider_media_id and legacy meta_media_id must match when both are provided.")
        if resolved_provider_media_id and not self.phone_number_id:
            raise ValueError(
                "provider_media_id requires phone_number_id so the media reference stays scoped to a Phone-Number-ID."
            )
        return self

    @property
    def resolved_provider_media_id(self) -> str | None:
        return self.__dict__.get("provider_media_id") or self.__dict__.get("meta_media_id")

    @property
    def resolved_provider_media_status(self) -> str | None:
        return self.__dict__.get("provider_media_status") or self.__dict__.get("meta_media_status")


class MediaAssetUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    waba_id: str | None = None
    phone_number_id: str | None = None
    is_active: bool | None = None
    tags: list[str] | None = None

    @model_validator(mode="after")
    def validate_mutation(self) -> "MediaAssetUpdateRequest":
        if not self.model_fields_set:
            raise ValueError("Media asset update requires at least one field.")
        return self


class MediaAssetEventView(BaseModel):
    id: str
    account_id: str
    asset_id: str
    waba_id: str | None = None
    phone_number_id: str | None = None
    event_type: str
    provider_media_id: str | None = None
    meta_media_id: str | None = Field(default=None, deprecated=True)
    created_by: str | None = None
    payload: dict[str, object] | None = None
    created_at: str


class MediaAssetProviderSyncView(BaseModel):
    id: str
    account_id: str
    asset_id: str
    provider_name: str
    waba_id: str | None = None
    phone_number_id: str | None = None
    provider_media_id: str | None = None
    meta_media_id: str | None = Field(default=None, deprecated=True)
    sync_status: str
    last_synced_at: str | None = None
    last_error_code: str | None = None
    last_error_message: str | None = None
    raw_response: dict[str, object] | None = None
    created_at: str
    updated_at: str


class MediaAssetView(BaseModel):
    asset_id: str
    account_id: str
    waba_id: str | None = None
    phone_number_id: str | None = None
    name: str
    asset_type: MediaAssetType
    mime_type: str
    file_size: int | None = None
    storage_key: str | None = None
    storage_url: str | None = None
    legacy_meta_media_id: str | None = None
    legacy_meta_media_status: str | None = None
    meta_media_id: str | None = Field(default=None, deprecated=True)
    meta_media_status: str | None = Field(default=None, deprecated=True)
    provider_references: list[MediaAssetProviderSyncView] = Field(default_factory=list)
    source: str
    tags: list[str] = Field(default_factory=list)
    created_by: str | None = None
    is_active: bool
    created_at: str
    updated_at: str


class MediaAssetDetailResponse(BaseModel):
    asset: MediaAssetView
    usage: "MediaAssetUsageSummary"
    provider_syncs: list[MediaAssetProviderSyncView] = Field(default_factory=list)
    events: list[MediaAssetEventView] = Field(default_factory=list)


class MediaAssetUsageSummary(BaseModel):
    total_events: int = 0
    sync_count: int = 0
    sync_failed_count: int = 0
    send_count: int = 0
    send_failed_count: int = 0
    template_send_count: int = 0
    template_send_failed_count: int = 0
    delivered_status_count: int = 0
    read_status_count: int = 0
    provider_failed_status_count: int = 0
    last_event_at: str | None = None
    last_synced_at: str | None = None
    last_sync_failed_at: str | None = None
    last_sent_at: str | None = None
    last_failed_at: str | None = None
    last_delivered_at: str | None = None
    last_read_at: str | None = None
    last_provider_failed_at: str | None = None


class MediaAssetSendRequest(BaseModel):
    asset_id: str = Field(min_length=1)
    caption: str | None = None
    file_name: str | None = None
    agent_id: str | None = None


class MediaAssetSendResponse(BaseModel):
    account_id: str
    conversation_id: str
    external_conversation_id: str
    internal_conversation_id: str
    asset_id: str
    waba_id: str | None = None
    phone_number_id: str | None = None
    provider_media_id: str | None = None
    message_type: MediaAssetType
    caption: str | None = None
    delivered_caption: str | None = None
    translated: bool
    message_id: str
    provider: str
    provider_message_id: str | None = None


class MediaAssetSyncRequest(BaseModel):
    phone_number_id: str | None = None
    force_resync: bool = False


class MediaAssetSyncResponse(BaseModel):
    asset_id: str
    account_id: str
    provider_name: str
    waba_id: str | None = None
    phone_number_id: str | None = None
    provider_media_id: str | None = None
    meta_media_id: str | None = Field(default=None, deprecated=True)
    sync_status: str
    last_error_code: str | None = None
    last_error_message: str | None = None
    reused_existing: bool = False
    synced_at: str | None = None
