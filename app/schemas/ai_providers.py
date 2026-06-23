"""
AIP-001: Pydantic schemas for AI Provider Configuration CRUD + Test Connection.

API responses NEVER expose the raw api_key — only a boolean has_api_key.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


# ── Request Schemas ──────────────────────────────────────────────────────


class CreateAIProviderConfigRequest(BaseModel):
    """Create a new AI provider config. api_key is plaintext and will be encrypted server-side."""

    name: str = Field(min_length=1, max_length=128, description="Unique display name")
    provider_type: str = Field(min_length=1, max_length=64, description="openai/deepseek/groq/ollama/custom")
    api_base_url: str | None = Field(default=None, max_length=512, description="Base URL (empty = OpenAI default)")
    api_key: str = Field(min_length=1, max_length=4096, description="Plaintext API key (encrypted on storage)")
    model: str = Field(min_length=1, max_length=128)
    priority: int = Field(default=0, ge=0, le=9999)
    is_enabled: bool = Field(default=True)
    timeout_seconds: int = Field(default=30, ge=5, le=120)
    use_responses_api: bool = Field(default=False, description="True=OpenAI responses.create, False=chat.completions")
    metadata_json: dict | None = Field(default=None)


class UpdateAIProviderConfigRequest(BaseModel):
    """Update fields of an existing config. All fields optional.
    If api_key is omitted/empty, the existing encrypted key is preserved.
    """

    name: str | None = Field(default=None, max_length=128)
    provider_type: str | None = Field(default=None, max_length=64)
    api_base_url: str | None = Field(default=None, max_length=512)
    api_key: str | None = Field(default=None, max_length=4096, description="New plaintext key or None to keep existing")
    model: str | None = Field(default=None, max_length=128)
    priority: int | None = Field(default=None, ge=0, le=9999)
    is_enabled: bool | None = Field(default=None)
    timeout_seconds: int | None = Field(default=None, ge=5, le=120)
    use_responses_api: bool | None = Field(default=None)
    metadata_json: dict | None = Field(default=None)


class ReorderRequest(BaseModel):
    """Reorder provider configs by setting priority from ordered_ids list."""

    ordered_ids: list[str] = Field(min_length=1, description="Config IDs in desired priority order (lowest first)")


class SetAccountOverrideRequest(BaseModel):
    """Set or update an account-level AI provider override."""

    provider_config_id: str = Field(min_length=1)


class TestConnectionRequest(BaseModel):
    """Test connection to an AI provider.
    Either config_id (test existing) or inline fields (test temporary config).
    """

    config_id: str | None = Field(default=None)
    api_base_url: str | None = Field(default=None)
    api_key: str | None = Field(default=None)
    model: str | None = Field(default=None)
    timeout_seconds: int = Field(default=15, ge=5, le=120)
    provider_type: str = Field(default="custom", max_length=64)


# ── Response Schemas ─────────────────────────────────────────────────────


class AIProviderConfigResponse(BaseModel):
    """Public view of a provider config — NEVER includes raw api_key."""

    id: str
    name: str
    provider_type: str
    api_base_url: str | None
    has_api_key: bool = False
    model: str
    priority: int
    is_enabled: bool
    timeout_seconds: int
    use_responses_api: bool
    metadata_json: dict | None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class TestConnectionResponse(BaseModel):
    """Result of a test-connection request."""

    status: Literal["ok", "error"]
    latency_ms: int | None = None
    model_echoed: str | None = None
    error_type: Literal["auth_failed", "timeout", "model_not_found", "unknown"] | None = None
    message: str | None = None


class AccountAIProviderOverrideResponse(BaseModel):
    """Account-level override view."""

    account_id: str
    provider_config_id: str
    provider_name: str | None = None
    model: str | None = None
    is_active: bool
