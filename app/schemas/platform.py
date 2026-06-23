from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.constants.h5_templates import DEFAULT_H5_TEMPLATE_ID, SINGLE_TEMPLATE_MODE_ERROR


def _validate_single_template_binding(
    *,
    template_id: str | None,
    metadata_json: dict[str, Any] | None,
) -> str:
    metadata_template_id = None
    if metadata_json is not None:
        metadata_template_id = metadata_json.get("template_id")

    for candidate in (template_id, metadata_template_id):
        if candidate is not None and candidate != DEFAULT_H5_TEMPLATE_ID:
            raise ValueError(SINGLE_TEMPLATE_MODE_ERROR)

    return DEFAULT_H5_TEMPLATE_ID


class H5SiteCreateRequest(BaseModel):
    account_id: str | None = Field(default=None, max_length=128)
    site_key: str = Field(min_length=1, max_length=64)
    domain: str = Field(min_length=1, max_length=255)
    brand_name: str = Field(min_length=1, max_length=255)
    logo_url: str | None = Field(default=None, max_length=1024)
    favicon_url: str | None = Field(default=None, max_length=1024)
    default_language: str = Field(default="zh-CN", min_length=2, max_length=32)
    status: str = Field(default="active", min_length=1, max_length=32)
    metadata_json: dict[str, Any] | None = None
    template_id: str | None = Field(default=None, min_length=1, max_length=36)

    @model_validator(mode="after")
    def validate_single_template(self) -> "H5SiteCreateRequest":
        self.template_id = _validate_single_template_binding(
            template_id=self.template_id,
            metadata_json=self.metadata_json,
        )
        return self


class H5SiteResponse(BaseModel):
    id: str
    account_id: str | None = None
    site_key: str
    domain: str
    brand_name: str
    logo_url: str | None = None
    default_language: str
    status: str
    metadata_json: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class H5SiteUpdateRequest(BaseModel):
    """Partial update for an H5 site. All fields optional."""
    brand_name: str | None = Field(default=None, min_length=1, max_length=255)
    domain: str | None = Field(default=None, min_length=1, max_length=255)
    logo_url: str | None = Field(default=None, max_length=1024)
    default_language: str | None = Field(default=None, min_length=2, max_length=32)
    status: str | None = Field(default=None, min_length=1, max_length=32)
    metadata_json: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_single_template(self) -> "H5SiteUpdateRequest":
        _validate_single_template_binding(
            template_id=None,
            metadata_json=self.metadata_json,
        )
        return self


class H5SiteConfigResponse(BaseModel):
    """H5SiteConfig output schema."""
    id: str
    site_id: str
    logo_url: str | None = None
    favicon_url: str | None = None
    primary_color: str | None = None
    font_family: str | None = None
    footer_text: str | None = None
    enabled_pages: list | None = None
    custom_css: str | None = None
    deploy_type: str | None = None
    ssh_host: str | None = None
    ssh_user: str | None = None
    ssh_key_path: str | None = None
    domain: str | None = None
    ssl_enabled: bool = True
    created_at: datetime
    updated_at: datetime


class H5SiteConfigUpdateRequest(BaseModel):
    """Partial update for H5SiteConfig. All fields optional."""
    logo_url: str | None = Field(default=None, max_length=500)
    favicon_url: str | None = Field(default=None, max_length=500)
    primary_color: str | None = Field(default=None, max_length=7)
    font_family: str | None = Field(default=None, max_length=100)
    footer_text: str | None = Field(default=None, max_length=500)
    enabled_pages: list | None = None
    custom_css: str | None = None
    deploy_type: str | None = Field(default=None, max_length=32)
    ssh_host: str | None = Field(default=None, max_length=200)
    ssh_user: str | None = Field(default=None, max_length=50)
    ssh_key_path: str | None = Field(default=None, max_length=500)
    domain: str | None = Field(default=None, max_length=200)
    ssl_enabled: bool | None = None


class UserIdentityCreateRequest(BaseModel):
    identity_type: str = Field(min_length=1, max_length=32)
    identity_value: str = Field(min_length=1, max_length=255)
    country_code: str | None = Field(default=None, max_length=8)
    is_verified: bool = False
    is_primary: bool = False
    metadata_json: dict[str, Any] | None = None


class UserIdentityResponse(BaseModel):
    identity_type: str
    identity_value: str
    country_code: str | None = None
    is_verified: bool
    is_primary: bool


class PlatformUserCreateRequest(BaseModel):
    account_id: str | None = Field(default=None, max_length=128)
    public_user_id: str = Field(min_length=1, max_length=128)
    registration_site_id: str | None = Field(default=None, max_length=36)
    display_name: str | None = Field(default=None, max_length=255)
    country_code: str | None = Field(default=None, max_length=8)
    language_code: str = Field(default="zh-CN", min_length=2, max_length=32)
    is_anonymous: bool = False
    lifecycle_status: str = Field(default="active", min_length=1, max_length=32)
    restrict_task_claim: bool = False
    registration_invite_code: str | None = Field(default=None, max_length=64)
    registration_ip: str | None = Field(default=None, max_length=45)
    identities: list[UserIdentityCreateRequest] = Field(default_factory=list)
    tag_keys: list[str] = Field(default_factory=list)


class UserTagResponse(BaseModel):
    tag_key: str
    name: str
    description: str | None = None
    color: str | None = None
    source_type: str
    is_active: bool


class PlatformUserResponse(BaseModel):
    id: str
    account_id: str | None = None
    public_user_id: str
    registration_site_id: str | None = None
    registration_site_key: str | None = None
    registration_site_domain: str | None = None
    display_name: str | None = None
    country_code: str | None = None
    language_code: str
    is_anonymous: bool
    lifecycle_status: str
    has_phone: bool
    has_email: bool
    has_whatsapp: bool
    is_invited_user: bool
    is_new_user: bool
    restrict_task_claim: bool
    registration_invite_code: str | None = None
    registration_ip: str | None = None
    last_active_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    identities: list[UserIdentityResponse] = Field(default_factory=list)
    tags: list[UserTagResponse] = Field(default_factory=list)


class UserTagCreateRequest(BaseModel):
    tag_key: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    color: str | None = Field(default=None, max_length=32)
    source_type: str = Field(default="manual", min_length=1, max_length=32)
    rule_json: dict[str, Any] | None = None
    is_active: bool = True


class UserTagCreateResponse(UserTagResponse):
    id: str
    rule_json: dict[str, Any] | None = None
    created_by: str | None = None
    created_at: datetime
    updated_at: datetime


class PlatformUserEnhancedResponse(PlatformUserResponse):
    """Enhanced user response with aggregate fields for customer page."""
    conversation_count: int = 0
    open_conversation_count: int = 0
    ticket_count: int = 0
    wallet_balance: float = 0.0


class PlatformUserPaginatedResponse(BaseModel):
    """Paginated response wrapper for enhanced user list."""
    items: list[PlatformUserEnhancedResponse]
    total: int
    page: int | None = None
    size: int | None = None


class BatchLifecycleRequest(BaseModel):
    """Batch update lifecycle status for multiple customers."""
    customer_ids: list[str] = Field(min_length=1, max_length=100)
    account_id: str
    lifecycle_status: str = Field(pattern=r"^(active|frozen|blacklisted)$")


class BatchLifecycleResponse(BaseModel):
    """Result of batch lifecycle update."""
    updated_count: int
    lifecycle_status: str
    account_id: str
    customer_ids: list[str]


class TimelineEvent(BaseModel):
    """A single event in the customer timeline."""
    type: str
    time: str
    summary: str
    metadata: dict[str, object] = Field(default_factory=dict)


class CustomerTimelineResponse(BaseModel):
    """Merged timeline response."""
    events: list[TimelineEvent]


class AudienceRuleSetCreateRequest(BaseModel):
    rule_key: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    scope_type: str = Field(default="task_template", min_length=1, max_length=64)
    scope_id: str | None = Field(default=None, max_length=128)
    status: str = Field(default="draft", min_length=1, max_length=32)
    description: str | None = None
    rules_json: dict[str, Any] = Field(default_factory=dict)


class AudienceRuleSetUpdateRequest(BaseModel):
    """Partial update for an audience rule set. All fields optional."""
    name: str | None = Field(default=None, max_length=255)
    scope_type: str | None = Field(default=None, min_length=1, max_length=64)
    scope_id: str | None = Field(default=None, max_length=128)
    status: str | None = Field(default=None, min_length=1, max_length=32)
    description: str | None = None
    rules_json: dict[str, Any] | None = None


class AudienceRuleSetResponse(BaseModel):
    id: str
    rule_key: str
    name: str
    scope_type: str
    scope_id: str | None = None
    status: str
    description: str | None = None
    rules_json: dict[str, Any] = Field(default_factory=dict)
    created_by: str | None = None
    updated_by: str | None = None
    created_at: datetime
    updated_at: datetime
