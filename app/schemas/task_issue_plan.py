from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import Field

from app.schemas.h5_member_base import H5MemberCamelModel


class TaskIssuePlanDayRuleCreateRequest(H5MemberCamelModel):
    day_no: int = Field(ge=1)
    package_count: int = Field(ge=1)
    day_total_amount: Decimal = Field(gt=Decimal("0"))
    tolerance_amount: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0"))
    amount_allocation_mode: str = Field(default="average", min_length=1, max_length=32)
    package_amounts_json: list[str] = Field(default_factory=list)
    product_pool_id: str | None = Field(default=None, max_length=36)
    product_count_mode: str = Field(default="range", min_length=1, max_length=32)
    product_count_fixed: int | None = Field(default=None, ge=1)
    product_count_min: int | None = Field(default=None, ge=1)
    product_count_max: int | None = Field(default=None, ge=1)
    reward_ratio: Decimal = Field(default=Decimal("0.10"), ge=Decimal("0"))
    issue_time_of_day: str | None = Field(default=None, max_length=16)
    elapsed_delay_hours: int | None = Field(default=None, ge=0)
    status: str = Field(default="active", min_length=1, max_length=32)
    metadata_json: dict[str, Any] | None = None


class TaskIssuePlanCreateRequest(H5MemberCamelModel):
    account_id: str = Field(min_length=1, max_length=128)
    site_id: str | None = Field(default=None, max_length=36)
    name: str = Field(min_length=1, max_length=255)
    plan_type: str = Field(default="official", min_length=1, max_length=32)
    status: str = Field(default="draft", min_length=1, max_length=32)
    claim_gate: str = Field(default="certified_member", min_length=1, max_length=32)
    issue_anchor: str = Field(default="certified_at", min_length=1, max_length=32)
    issue_mode: str = Field(default="calendar_day", min_length=1, max_length=32)
    require_previous_batch_completed: bool = True
    max_unfinished_batches: int = Field(default=1, ge=1)
    after_last_rule_mode: str = Field(default="arithmetic_growth", min_length=1, max_length=32)
    growth_package_count_step: int = Field(default=1, ge=0)
    growth_amount_step: Decimal | None = Field(default=None, ge=Decimal("0"))
    default_product_pool_id: str | None = Field(default=None, max_length=36)
    default_tolerance_amount: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0"))
    default_reward_ratio: Decimal = Field(default=Decimal("0.10"), ge=Decimal("0"))
    metadata_json: dict[str, Any] | None = None
    day_rules: list[TaskIssuePlanDayRuleCreateRequest] = Field(default_factory=list)


class TaskIssuePlanUpdateRequest(H5MemberCamelModel):
    site_id: str | None = Field(default=None, max_length=36)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    plan_type: str | None = Field(default=None, min_length=1, max_length=32)
    status: str | None = Field(default=None, min_length=1, max_length=32)
    claim_gate: str | None = Field(default=None, min_length=1, max_length=32)
    issue_anchor: str | None = Field(default=None, min_length=1, max_length=32)
    issue_mode: str | None = Field(default=None, min_length=1, max_length=32)
    require_previous_batch_completed: bool | None = None
    max_unfinished_batches: int | None = Field(default=None, ge=1)
    after_last_rule_mode: str | None = Field(default=None, min_length=1, max_length=32)
    growth_package_count_step: int | None = Field(default=None, ge=0)
    growth_amount_step: Decimal | None = Field(default=None, ge=Decimal("0"))
    default_product_pool_id: str | None = Field(default=None, max_length=36)
    default_tolerance_amount: Decimal | None = Field(default=None, ge=Decimal("0"))
    default_reward_ratio: Decimal | None = Field(default=None, ge=Decimal("0"))
    metadata_json: dict[str, Any] | None = None
    day_rules: list[TaskIssuePlanDayRuleCreateRequest] | None = None


class TaskIssuePlanGenerateDaysRequest(H5MemberCamelModel):
    start_day_no: int = Field(ge=1)
    end_day_no: int = Field(ge=1)


class TaskIssuePlanDayRuleResponse(H5MemberCamelModel):
    id: str
    account_id: str
    site_id: str | None = None
    plan_id: str
    day_no: int
    package_count: int
    day_total_amount: Decimal
    tolerance_amount: Decimal
    amount_allocation_mode: str
    package_amounts_json: list[str]
    product_pool_id: str | None = None
    product_count_mode: str
    product_count_fixed: int | None = None
    product_count_min: int | None = None
    product_count_max: int | None = None
    reward_ratio: Decimal
    issue_time_of_day: str | None = None
    elapsed_delay_hours: int | None = None
    status: str
    metadata_json: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class TaskIssuePlanDayRulePreviewResponse(H5MemberCamelModel):
    day_no: int
    package_count: int
    day_total_amount: Decimal
    tolerance_amount: Decimal
    amount_allocation_mode: str
    package_amounts_json: list[str]
    product_pool_id: str | None = None
    product_count_mode: str
    product_count_fixed: int | None = None
    product_count_min: int | None = None
    product_count_max: int | None = None
    reward_ratio: Decimal
    issue_time_of_day: str | None = None
    elapsed_delay_hours: int | None = None
    status: str
    metadata_json: dict[str, Any] | None = None


class TaskIssuePlanResponse(H5MemberCamelModel):
    id: str
    account_id: str
    site_id: str | None = None
    name: str
    plan_type: str
    status: str
    claim_gate: str
    issue_anchor: str
    issue_mode: str
    require_previous_batch_completed: bool
    max_unfinished_batches: int
    after_last_rule_mode: str
    growth_package_count_step: int
    growth_amount_step: Decimal | None = None
    default_product_pool_id: str | None = None
    default_tolerance_amount: Decimal
    default_reward_ratio: Decimal
    metadata_json: dict[str, Any] | None = None
    day_rules: list[TaskIssuePlanDayRuleResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class TaskIssuePlanPreviewResponse(H5MemberCamelModel):
    plan_id: str
    day_rules: list[TaskIssuePlanDayRulePreviewResponse] = Field(default_factory=list)
