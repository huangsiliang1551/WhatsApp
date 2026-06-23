"""Pydantic schemas for Translation Provider Configuration CRUD + Test Connection.

API responses NEVER expose the raw secret_id/secret_key — only has_secret boolean.
"""

from datetime import datetime

from pydantic import BaseModel, Field


# ── TMT Region Ping Schemas ──


class TMTRegionInfo(BaseModel):
    """TMT supported region info."""

    region: str
    label: str
    endpoint: str


class RegionPingRequest(BaseModel):
    """Request to ping all TMT regions."""

    config_id: str | None = Field(default=None)
    secret_id: str | None = Field(default=None)
    secret_key: str | None = Field(default=None)
    timeout_seconds: int = Field(default=10, ge=3, le=30)


class RegionPingResult(BaseModel):
    """Ping result for a single TMT region."""

    region: str
    label: str
    latency_ms: int | None = None
    status: str = "pending"  # "ok" | "error" | "timeout"
    error: str | None = None


class RegionPingResponse(BaseModel):
    """Response for region ping request."""

    results: list[RegionPingResult]


# ── Request Schemas ──

class CreateTranslationProviderConfigRequest(BaseModel):
    """Create a new translation provider config. Secrets will be encrypted server-side."""

    name: str = Field(min_length=1, max_length=128, description="Unique display name")
    provider_type: str = Field(min_length=1, max_length=64, description="tencent_cloud")
    secret_id: str = Field(min_length=1, max_length=1024, description="Tencent Cloud SecretId")
    secret_key: str = Field(min_length=1, max_length=2048, description="Tencent Cloud SecretKey")
    region: str = Field(default="ap-guangzhou", max_length=64, description="Tencent Cloud region")
    priority: int = Field(default=0, ge=0, le=9999)
    is_enabled: bool = Field(default=True)
    timeout_seconds: int = Field(default=15, ge=5, le=120)
    metadata_json: dict | None = Field(default=None)


class UpdateTranslationProviderConfigRequest(BaseModel):
    """Update fields of an existing config. All fields optional."""

    name: str | None = Field(default=None, max_length=128)
    provider_type: str | None = Field(default=None, max_length=64)
    secret_id: str | None = Field(default=None, max_length=1024, description="New SecretId or None to keep existing")
    secret_key: str | None = Field(default=None, max_length=2048, description="New SecretKey or None to keep existing")
    region: str | None = Field(default=None, max_length=64)
    priority: int | None = Field(default=None, ge=0, le=9999)
    is_enabled: bool | None = Field(default=None)
    timeout_seconds: int | None = Field(default=None, ge=5, le=120)
    metadata_json: dict | None = Field(default=None)


# ── Response Schemas ──

class TranslationProviderConfigResponse(BaseModel):
    """Public view of a translation provider config — NEVER includes raw secrets."""

    id: str
    name: str
    provider_type: str
    region: str | None
    has_secret: bool = False
    priority: int
    is_enabled: bool
    timeout_seconds: int
    metadata_json: dict | None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class TestConnectionRequest(BaseModel):
    """Test connection to a translation provider."""

    config_id: str | None = Field(default=None)
    secret_id: str | None = Field(default=None)
    secret_key: str | None = Field(default=None)
    region: str | None = Field(default=None)
    timeout_seconds: int = Field(default=15, ge=5, le=120)


class TestConnectionResponse(BaseModel):
    """Result of a test-connection request."""

    status: str  # "ok" | "error"
    latency_ms: int | None = None
    source_text: str | None = None
    translated_text: str | None = None
    error_type: str | None = None
    message: str | None = None
    error_friendly_message: str | None = None
    error_code: str | None = None
