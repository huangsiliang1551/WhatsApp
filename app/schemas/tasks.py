from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class TaskTemplateCreateRequest(BaseModel):
    account_id: str | None = Field(default=None, max_length=128)
    task_key: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    task_type: str = Field(min_length=1, max_length=32)
    status: str = Field(default="draft", min_length=1, max_length=32)
    audience_rule_set_id: str | None = Field(default=None, max_length=36)
    reward_amount: Decimal | None = None
    reward_points: int = 0
    claim_timeout_seconds: int = Field(default=86400, ge=60)
    auto_review_enabled: bool = True
    metadata_json: dict[str, Any] | None = None


class TaskTemplateResponse(BaseModel):
    id: str
    account_id: str | None = None
    task_key: str
    name: str
    title: str
    description: str | None = None
    task_type: str
    status: str
    audience_rule_set_id: str | None = None
    reward_amount: Decimal | None = None
    reward_points: int
    claim_timeout_seconds: int
    auto_review_enabled: bool
    metadata_json: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class TaskInstanceCreateRequest(BaseModel):
    template_id: str = Field(min_length=1, max_length=36)
    user_id: str = Field(min_length=1, max_length=36)
    site_id: str | None = Field(default=None, max_length=36)
    account_id: str | None = Field(default=None, max_length=128)
    review_required: bool = False
    metadata_json: dict[str, Any] | None = None


class TaskInstanceClaimRequest(BaseModel):
    claimed_by: str | None = Field(default=None, max_length=128)


class TaskInstanceResponse(BaseModel):
    id: str
    template_id: str
    template_task_key: str
    template_name: str
    template_title: str
    template_description: str | None = None
    task_type: str
    reward_points: int
    account_id: str | None = None
    user_id: str
    public_user_id: str
    site_id: str | None = None
    site_key: str | None = None
    status: str
    claim_timeout_seconds_snapshot: int
    review_required: bool
    latest_submission_id: str | None = None
    active_ticket_count: int = 0
    review_status_summary: str | None = None
    available_at: datetime
    claimed_at: datetime | None = None
    claim_deadline_at: datetime | None = None
    submitted_at: datetime | None = None
    reviewed_at: datetime | None = None
    completed_at: datetime | None = None
    expired_at: datetime | None = None
    metadata_json: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime
