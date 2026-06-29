from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from app.schemas.h5_member_base import H5MemberCamelModel


class TaskMonitorSavedViewCreateRequest(H5MemberCamelModel):
    account_id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=128)
    filter_json: dict[str, Any] = Field(default_factory=dict)
    sort_json: list[dict[str, Any]] | None = None
    columns_json: list[str] | None = None
    refresh_seconds: int = Field(default=10, ge=1, le=3600)
    sound_enabled: bool = False
    is_default: bool = False


class TaskMonitorSavedViewUpdateRequest(H5MemberCamelModel):
    name: str = Field(min_length=1, max_length=128)
    filter_json: dict[str, Any] = Field(default_factory=dict)
    sort_json: list[dict[str, Any]] | None = None
    columns_json: list[str] | None = None
    refresh_seconds: int = Field(default=10, ge=1, le=3600)
    sound_enabled: bool = False
    is_default: bool = False


class TaskMonitorSavedViewResponse(H5MemberCamelModel):
    id: str
    account_id: str
    owner_staff_id: str
    name: str
    filter_json: dict[str, Any]
    sort_json: list[dict[str, Any]] | None = None
    columns_json: list[str] | None = None
    refresh_seconds: int
    sound_enabled: bool
    is_default: bool
    created_at: datetime
    updated_at: datetime


class TaskAlertRuleCreateRequest(H5MemberCamelModel):
    account_id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=128)
    status: str = Field(default="active", min_length=1, max_length=32)
    condition_json: dict[str, Any] = Field(default_factory=dict)
    action_json: dict[str, Any] = Field(default_factory=dict)
    sound_enabled: bool = False
    priority: str = Field(default="normal", min_length=1, max_length=32)
    metadata_json: dict[str, Any] | None = None


class TaskAlertRuleUpdateRequest(H5MemberCamelModel):
    name: str = Field(min_length=1, max_length=128)
    status: str = Field(default="active", min_length=1, max_length=32)
    condition_json: dict[str, Any] = Field(default_factory=dict)
    action_json: dict[str, Any] = Field(default_factory=dict)
    sound_enabled: bool = False
    priority: str = Field(default="normal", min_length=1, max_length=32)
    metadata_json: dict[str, Any] | None = None


class TaskAlertRuleResponse(H5MemberCamelModel):
    id: str
    account_id: str
    name: str
    status: str
    condition_json: dict[str, Any]
    action_json: dict[str, Any]
    sound_enabled: bool
    priority: str
    created_by: str | None = None
    metadata_json: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class TaskMonitorQueryRowResponse(H5MemberCamelModel):
    package_id: str
    account_id: str
    user_id: str
    public_user_id: str
    site_id: str | None = None
    site_key: str | None = None
    batch_id: str | None = None
    day_no: int | None = None
    progress_label: str
    status: str
    current_item_index: int | None = None
    day_planned_amount: float = 0
    day_system_generated_amount: float = 0
    day_manual_added_amount: float = 0
    day_effective_amount: float = 0
    planned_amount: float
    system_generated_amount: float
    manual_added_amount: float
    effective_amount: float
    has_manual_add: bool = False
    manual_added_item_count: int = 0
    latest_manual_add_operator_id: str | None = None
    latest_manual_add_at: datetime | None = None
    current_product_id: str | None = None
    current_product_name: str | None = None
    current_product_amount: float = 0
    current_product_origin: str | None = None
    total_real_recharge_amount: float = 0
    total_withdraw_amount: float = 0
    estimated_reward_amount: float = 0
    claimed_at: datetime | None = None
    completed_at: datetime | None = None


class TaskMonitorSummaryResponse(H5MemberCamelModel):
    total_count: int
    manual_add_count: int
    total_planned_amount: float
    total_manual_added_amount: float
    total_effective_amount: float
    total_real_recharge_amount: float
    total_withdraw_amount: float


class TaskMonitorAlertEventResponse(H5MemberCamelModel):
    id: str
    account_id: str
    alert_rule_id: str
    package_id: str
    user_id: str
    public_user_id: str
    status: str
    priority: str
    rule_name: str
    current_value: float
    threshold_value: float | None = None
    sound_enabled: bool = False
    triggered_at: datetime
    acknowledged_at: datetime | None = None
    acknowledged_by: str | None = None
    resolved_at: datetime | None = None
    resolved_by: str | None = None
