from typing import Literal

from pydantic import BaseModel, Field


TemplateRegistryStatus = Literal["PENDING", "APPROVED", "REJECTED", "DRAFT", "DISABLED", "PAUSED"]


class TemplateRegistrySubmitRequest(BaseModel):
    account_id: str
    waba_id: str
    access_token: str | None = None
    name: str
    language: str
    category: str
    components: dict[str, object] = Field(default_factory=dict)


class TemplateRegistryRemoteTemplate(BaseModel):
    provider_template_id: str | None = None
    name: str
    language: str
    category: str
    status: TemplateRegistryStatus
    rejected_reason: str | None = None
    components: dict[str, object] = Field(default_factory=dict)
    raw_payload: dict[str, object] = Field(default_factory=dict)


class TemplateRegistrySubmitResult(BaseModel):
    provider_name: str
    action: str
    remote_status: TemplateRegistryStatus
    provider_template_id: str | None = None
    remote_template: TemplateRegistryRemoteTemplate | None = None
    raw_response: dict[str, object] = Field(default_factory=dict)


class TemplateRegistrySyncResult(BaseModel):
    provider_name: str
    templates: list[TemplateRegistryRemoteTemplate] = Field(default_factory=list)
