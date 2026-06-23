from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


# ─── Product ────────────────────────────────────────────────────────────────

class ProductCreateRequest(BaseModel):
    account_id: str = Field(..., min_length=1)
    name: str = Field(..., max_length=200)
    image_asset_id: str | None = None
    price: Decimal = Field(..., ge=0)
    tags: list[str] | None = None


class ProductUpdateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    image_asset_id: str | None = None
    price: Decimal | None = Field(default=None, ge=0)
    tags: list[str] | None = None


class ProductResponse(BaseModel):
    id: str
    account_id: str
    name: str
    image_asset_id: str | None = None
    price: Decimal
    tags: list[str] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ProductListResponse(BaseModel):
    items: list[ProductResponse]
    total: int


# ─── Product Package ────────────────────────────────────────────────────────

class AssemblePreviewRequest(BaseModel):
    target_amount: Decimal = Field(..., gt=0)
    tolerance_pct: int = Field(default=10, ge=0, le=100)
    product_count: int = Field(..., ge=1, le=100)


class AssemblePreviewItem(BaseModel):
    id: str
    name: str
    price: Decimal


class AssemblePreviewResponse(BaseModel):
    items: list[AssemblePreviewItem]
    total_value: Decimal
    target_amount: Decimal
    deviation_pct: float
    within_range: bool
    tolerance_pct: int


class PackageCreateRequest(BaseModel):
    account_id: str = Field(..., min_length=1)
    name: str = Field(..., max_length=200)
    target_amount: Decimal = Field(..., gt=0)
    amount_tolerance_pct: int = Field(default=10, ge=0, le=100)
    product_count: int = Field(..., ge=1, le=100)
    completion_reward: Decimal = Field(default=Decimal("0"), ge=0)


class PackageUpdateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    completion_reward: Decimal | None = Field(default=None, ge=0)


class PackageResponse(BaseModel):
    id: str
    account_id: str
    name: str
    target_amount: Decimal
    amount_tolerance_pct: int
    product_count: int
    product_ids: list[str] | None = None
    product_snapshot: list[dict] | None = None
    total_value: Decimal
    completion_reward: Decimal
    created_at: datetime | None = None
    claim_count: int = 0
    completion_rate: float = 0.0


class PackageListResponse(BaseModel):
    items: list[PackageResponse]
    total: int


# ─── Task Rule ──────────────────────────────────────────────────────────────

class TaskRuleCreateRequest(BaseModel):
    account_id: str = Field(..., min_length=1)
    name: str = Field(..., max_length=200)
    rule_type: str = Field(..., pattern=r"^(package_push|signin|invite)$")
    trigger_type: str = Field(..., pattern=r"^(register|recharge|schedule|follow_up|manual)$")
    trigger_config: dict[str, Any] = Field(default_factory=dict)
    package_id: str | None = None
    follow_up_chain: list[dict[str, Any]] | None = None
    expiry_config: dict[str, Any] | None = None
    is_enabled: bool = True


class TaskRuleUpdateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    trigger_config: dict[str, Any] | None = None
    package_id: str | None = None
    follow_up_chain: list[dict[str, Any]] | None = None
    expiry_config: dict[str, Any] | None = None
    is_enabled: bool | None = None


class TaskRuleToggleRequest(BaseModel):
    is_enabled: bool


class TaskRuleResponse(BaseModel):
    id: str
    account_id: str
    name: str
    rule_type: str
    trigger_type: str
    trigger_config: dict[str, Any] | None = None
    package_id: str | None = None
    follow_up_chain: list[dict[str, Any]] | None = None
    expiry_config: dict[str, Any] | None = None
    is_enabled: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


# ─── Task Instance ──────────────────────────────────────────────────────────

class ManualPushRequest(BaseModel):
    account_id: str = Field(..., min_length=1)
    user_ids: list[str] = Field(..., min_length=1)
    rule_id: str = Field(..., min_length=1)


class StartProductRequest(BaseModel):
    product_id: str = Field(..., min_length=1)


class TaskInstanceResponse(BaseModel):
    id: str
    account_id: str
    user_id: str
    rule_id: str
    package_id: str | None = None
    task_type: str
    status: str
    product_progress: list[dict[str, Any]] | None = None
    total_paid: Decimal
    reward_amount: Decimal
    created_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    expires_at: datetime | None = None


class TaskInstanceListResponse(BaseModel):
    items: list[TaskInstanceResponse]
    total: int


# ─── Sign-In ────────────────────────────────────────────────────────────────

class SignInResultResponse(BaseModel):
    consecutive_days: int
    rewarded: bool
    reward_amount: Decimal = Decimal("0")


class SignInStatusResponse(BaseModel):
    signed_in_today: bool
    consecutive_days: int
    days_until_reward: int
    reward_amount: Decimal = Decimal("0")


class SignInConfigResponse(BaseModel):
    consecutive_days: int
    reward_amount: Decimal


class SignInConfigUpdateRequest(BaseModel):
    consecutive_days: int | None = Field(default=None, ge=1)
    reward_amount: Decimal | None = Field(default=None, ge=0)


# ─── Invite ─────────────────────────────────────────────────────────────────

class InviteLinkResponse(BaseModel):
    id: str
    account_id: str
    user_id: str
    invite_code: str
    invite_url: str | None = None
    created_at: datetime | None = None


class InviteRecordResponse(BaseModel):
    id: str
    inviter_user_id: str
    invitee_user_id: str
    invite_type: str
    reward_amount: Decimal
    is_rewarded: bool
    created_at: datetime | None = None


class InviteRecordsResponse(BaseModel):
    items: list[InviteRecordResponse]
    total: int


class RegisterCallbackRequest(BaseModel):
    inviter_code: str = Field(..., min_length=1)
    invitee_user_id: str = Field(..., min_length=1)
    invitee_ip: str | None = None
    invitee_device_id: str | None = None


class RechargeCallbackRequest(BaseModel):
    inviter_user_id: str = Field(..., min_length=1)
    invitee_user_id: str = Field(..., min_length=1)
    amount: Decimal = Field(..., gt=0)
    invitee_ip: str | None = None
    invitee_device_id: str | None = None


class InviteConfigResponse(BaseModel):
    register_reward: Decimal
    recharge_threshold: Decimal
    recharge_reward: Decimal
    max_count: int
    anti_fraud_same_ip_limit: int
    anti_fraud_same_device_limit: int


class InviteConfigUpdateRequest(BaseModel):
    register_reward: Decimal | None = Field(default=None, ge=0)
    recharge_threshold: Decimal | None = Field(default=None, ge=0)
    recharge_reward: Decimal | None = Field(default=None, ge=0)
    max_count: int | None = Field(default=None, ge=1)
    anti_fraud_same_ip_limit: int | None = Field(default=None, ge=0)
    anti_fraud_same_device_limit: int | None = Field(default=None, ge=0)


# ─── Marketing Stats ────────────────────────────────────────────────────────

class PackageStatsItem(BaseModel):
    package_id: str
    package_name: str
    total_created: int
    total_claimed: int
    completion_count: int
    completion_rate: float


class PackageStatsResponse(BaseModel):
    items: list[PackageStatsItem]


class TaskStatsItem(BaseModel):
    task_type: str
    trigger_count: int
    completed_count: int
    total_reward: Decimal
    completion_rate: float


class TaskStatsResponse(BaseModel):
    items: list[TaskStatsItem]


class OverviewStatsResponse(BaseModel):
    today_sign_ins: int = 0
    today_invites: int = 0
    today_push_count: int = 0
    total_products: int = 0
    total_packages: int = 0
