from typing import Literal

from pydantic import BaseModel, Field, model_validator


class OutboundDispatchRequest(BaseModel):
    account_id: str
    conversation_id: str
    recipient_id: str
    text: str | None = None
    message_type: Literal["text", "template", "image", "audio", "video", "document", "interactive"] = "text"
    phone_number_id: str | None = None
    access_token: str | None = None
    waba_id: str | None = None
    template_name: str | None = None
    template_language: str | None = None
    template_variables: dict[str, str] = Field(default_factory=dict)
    template_header_media_type: Literal["image", "video", "document"] | None = None
    media_asset_id: str | None = None
    media_url: str | None = None
    media_caption: str | None = None
    mime_type: str | None = None
    file_name: str | None = None
    interactive_payload: dict[str, object] = Field(default_factory=dict)
    metadata: dict[str, object] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_payload(self) -> "OutboundDispatchRequest":
        if self.message_type == "text" and not self.text:
            raise ValueError("Text outbound dispatch requires text.")
        if self.message_type == "template":
            if not self.template_name or not self.template_language:
                raise ValueError("Template outbound dispatch requires template_name and template_language.")
            if self.template_header_media_type and not self.media_asset_id and not self.media_url:
                raise ValueError(
                    "Template header media dispatch requires media_asset_id or media_url."
                )
        if self.message_type in {"image", "audio", "video", "document"}:
            if not self.media_asset_id and not self.media_url:
                raise ValueError("Media outbound dispatch requires media_asset_id or media_url.")
        if self.message_type == "interactive" and not self.interactive_payload:
            raise ValueError("Interactive outbound dispatch requires interactive_payload.")
        return self


class MediaAssetSyncRequest(BaseModel):
    account_id: str
    asset_id: str
    asset_name: str
    asset_type: Literal["image", "audio", "video", "document"]
    mime_type: str
    phone_number_id: str | None = None
    access_token: str | None = None
    waba_id: str | None = None
    storage_key: str | None = None
    storage_url: str | None = None
    existing_provider_media_id: str | None = Field(
        default=None,
        description="Phone-Number-ID scoped media reference already available at the messaging provider.",
    )
    existing_meta_media_id: str | None = Field(
        default=None,
        deprecated=True,
        description="Legacy compatibility field. Prefer existing_provider_media_id.",
    )
    metadata: dict[str, object] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_reference(self) -> "MediaAssetSyncRequest":
        existing_provider_media_id = self.__dict__.get("existing_provider_media_id")
        existing_meta_media_id = self.__dict__.get("existing_meta_media_id")
        resolved_provider_media_id = existing_provider_media_id or existing_meta_media_id
        if (
            existing_provider_media_id
            and existing_meta_media_id
            and existing_provider_media_id != existing_meta_media_id
        ):
            raise ValueError(
                "existing_provider_media_id and legacy existing_meta_media_id must match when both are provided."
            )
        if resolved_provider_media_id and not self.phone_number_id:
            raise ValueError(
                "existing_provider_media_id requires phone_number_id so the media reference stays scoped to a Phone-Number-ID."
            )
        if not resolved_provider_media_id and not self.storage_key and not self.storage_url:
            raise ValueError(
                "Media asset sync requires existing_provider_media_id, storage_key, or storage_url."
            )
        return self

    @property
    def resolved_existing_provider_media_id(self) -> str | None:
        return self.__dict__.get("existing_provider_media_id") or self.__dict__.get("existing_meta_media_id")


class MediaAssetSyncResult(BaseModel):
    provider_name: str
    phone_number_id: str | None = None
    waba_id: str | None = None
    provider_media_id: str | None = Field(
        default=None,
        description="Phone-Number-ID scoped media reference returned by the messaging provider.",
    )
    meta_media_id: str | None = Field(
        default=None,
        deprecated=True,
        description="Legacy compatibility field. Prefer provider_media_id.",
    )
    sync_status: Literal["reused", "synced", "failed", "unsupported"]
    error_code: str | None = None
    error_message: str | None = None
    raw_response: dict[str, object] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_provider_reference(self) -> "MediaAssetSyncResult":
        provider_media_id = self.__dict__.get("provider_media_id")
        meta_media_id = self.__dict__.get("meta_media_id")
        if provider_media_id and meta_media_id and provider_media_id != meta_media_id:
            raise ValueError("provider_media_id and legacy meta_media_id must match when both are provided.")
        resolved_provider_media_id = provider_media_id or meta_media_id
        self.provider_media_id = resolved_provider_media_id
        self.meta_media_id = resolved_provider_media_id
        if resolved_provider_media_id and not self.phone_number_id:
            raise ValueError(
                "provider_media_id requires phone_number_id so the media reference stays scoped to a Phone-Number-ID."
            )
        return self


class OutboundDispatchResult(BaseModel):
    provider_name: str
    provider_message_id: str | None = None
    accepted: bool = True
    external_status: str = "accepted"
    raw_response: dict[str, object] = Field(default_factory=dict)


class ProviderStatusUpdate(BaseModel):
    provider_name: str
    account_id: str = ""
    waba_id: str | None = None
    phone_number_id: str | None = None
    provider_message_id: str
    external_status: str
    recipient_id: str | None = None
    occurred_at: str | None = None
    error_code: str | None = None
    payload: dict[str, object] = Field(default_factory=dict)
