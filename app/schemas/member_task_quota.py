from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import Field

from app.schemas.h5_member_base import H5MemberCamelModel

class MemberTaskQuotaCreateRequest(H5MemberCamelModel):
    account_id: str = Field(min_length=1, max_length=128)
    user_id: str = Field(min_length=1, max_length=36)
    site_id: str | None = Field(default=None, max_length=36)
    plan_id: str | None = Field(default=None, max_length=36)
    day_no: int = Field(ge=1)
    package_count: int = Field(ge=1)
    day_total_amount: Decimal = Field(gt=Decimal("0"))
    tolerance_amount: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0"))
    amount_allocation_mode: str = Field(min_length=1, max_length=32)
    package_amounts: list[Decimal] = Field(default_factory=list)
    product_pool_id: str = Field(min_length=1, max_length=36)
    product_count_mode: str = Field(default="range", min_length=1, max_length=32)
    product_count_fixed: int | None = Field(default=None, ge=1)
    product_count_min: int | None = Field(default=None, ge=1)
    product_count_max: int | None = Field(default=None, ge=1)
    reward_ratio: Decimal = Field(default=Decimal("0.10"), ge=Decimal("0"))
    created_by: str | None = Field(default=None, max_length=64)
    metadata_json: dict[str, Any] | None = None


class MemberTaskQuotaPreviewRequest(H5MemberCamelModel):
    package_count: int = Field(ge=1)
    day_total_amount: Decimal = Field(gt=Decimal("0"))
    amount_allocation_mode: str = Field(min_length=1, max_length=32)
    package_amounts: list[Decimal] = Field(default_factory=list)


class MemberTaskQuotaPreviewResponse(H5MemberCamelModel):
    package_amounts: list[str]
    computed_total_amount: Decimal


class MemberTaskQuotaPlanIssueRequest(H5MemberCamelModel):
    plan_id: str = Field(min_length=1, max_length=36)
    user_id: str = Field(min_length=1, max_length=36)
    day_no: int = Field(ge=1)
    created_by: str | None = Field(default=None, max_length=64)
    metadata_json: dict[str, Any] | None = None


class MemberTaskQuotaUpdateRequest(H5MemberCamelModel):
    site_id: str | None = Field(default=None, max_length=36)
    package_count: int | None = Field(default=None, ge=1)
    day_total_amount: Decimal | None = Field(default=None, gt=Decimal("0"))
    tolerance_amount: Decimal | None = Field(default=None, ge=Decimal("0"))
    amount_allocation_mode: str | None = Field(default=None, min_length=1, max_length=32)
    package_amounts: list[Decimal] | None = None
    product_pool_id: str | None = Field(default=None, min_length=1, max_length=36)
    product_count_mode: str | None = Field(default=None, min_length=1, max_length=32)
    product_count_fixed: int | None = Field(default=None, ge=1)
    product_count_min: int | None = Field(default=None, ge=1)
    product_count_max: int | None = Field(default=None, ge=1)
    reward_ratio: Decimal | None = Field(default=None, ge=Decimal("0"))
    metadata_json: dict[str, Any] | None = None


class MemberTaskQuotaBatchCreateRequest(H5MemberCamelModel):
    items: list[MemberTaskQuotaCreateRequest] = Field(default_factory=list)
    account_id: str | None = Field(default=None, min_length=1, max_length=128)
    user_ids: list[str] = Field(default_factory=list)
    site_id: str | None = Field(default=None, max_length=36)
    plan_id: str | None = Field(default=None, max_length=36)
    day_no: int | None = Field(default=None, ge=1)
    package_count: int | None = Field(default=None, ge=1)
    day_total_amount: Decimal | None = Field(default=None, gt=Decimal("0"))
    tolerance_amount: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0"))
    amount_allocation_mode: str | None = Field(default=None, min_length=1, max_length=32)
    package_amounts: list[Decimal] = Field(default_factory=list)
    product_pool_id: str | None = Field(default=None, min_length=1, max_length=36)
    product_count_mode: str = Field(default="range", min_length=1, max_length=32)
    product_count_fixed: int | None = Field(default=None, ge=1)
    product_count_min: int | None = Field(default=None, ge=1)
    product_count_max: int | None = Field(default=None, ge=1)
    reward_ratio: Decimal = Field(default=Decimal("0.10"), ge=Decimal("0"))
    created_by: str | None = Field(default=None, max_length=64)
    metadata_json: dict[str, Any] | None = None
    owner_staff_user_id: str | None = Field(default=None, max_length=128)
    certified_status: Literal["certified", "uncertified"] | None = None
    min_total_real_recharge: Decimal | None = Field(default=None, ge=Decimal("0"))
    max_total_real_recharge: Decimal | None = Field(default=None, ge=Decimal("0"))
    tag_ids: list[str] = Field(default_factory=list)
    tag_keys: list[str] = Field(default_factory=list)


class MemberTaskQuotaBatchPreviewResponse(H5MemberCamelModel):
    user_count: int
    total_quota_count: int
    package_amounts: list[str]
    computed_total_amount: Decimal
    total_batch_amount: Decimal
    reward_ratio: Decimal | None = None
    product_pool_id: str | None = None


class MemberTaskQuotaCancelRequest(H5MemberCamelModel):
    reason: str | None = Field(default=None, max_length=128)


class MemberTaskDayQuotaResponse(H5MemberCamelModel):
    id: str
    account_id: str
    site_id: str | None = None
    user_id: str
    plan_id: str | None = None
    day_no: int
    package_count: int
    day_total_amount: Decimal
    tolerance_amount: Decimal
    amount_allocation_mode: str
    package_amounts_json: list[str]
    product_pool_id: str
    product_count_mode: str
    product_count_fixed: int | None = None
    product_count_min: int | None = None
    product_count_max: int | None = None
    reward_ratio: Decimal
    status: str
    issued_batch_id: str | None = None
    generated_at: datetime | None = None
    generated_by: str | None = None
    locked_at: datetime | None = None
    created_by: str | None = None
    metadata_json: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime
