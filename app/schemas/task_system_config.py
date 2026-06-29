from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import Field

from app.schemas.h5_member_base import H5MemberCamelModel


class TaskSystemConfigUpsertRequest(H5MemberCamelModel):
    account_id: str = Field(min_length=1, max_length=128)
    site_id: str | None = Field(default=None, max_length=36)
    status: str = Field(default="active", min_length=1, max_length=32)
    whatsapp_binding_reward_enabled: bool = True
    whatsapp_binding_reward_amount: Decimal = Field(default=Decimal("20.00"), ge=Decimal("0"))
    whatsapp_binding_reward_wallet_type: str = Field(default="task_balance", min_length=1, max_length=32)
    whatsapp_binding_reward_currency: str = Field(default="USD", min_length=1, max_length=16)
    certified_member_enabled: bool = True
    certified_recharge_threshold: Decimal = Field(default=Decimal("50.00"), ge=Decimal("0"))
    certified_recharge_scope: str = Field(default="real_recharge", min_length=1, max_length=32)
    auto_certify_on_recharge: bool = True
    newbie_task_enabled: bool = True
    newbie_plan_id: str | None = Field(default=None, max_length=36)
    newbie_auto_popup: bool = True
    official_plan_id: str | None = Field(default=None, max_length=36)
    show_task_balance_transfer_prompt: bool = True
    min_task_balance_transfer_prompt_amount: Decimal = Field(default=Decimal("0.01"), ge=Decimal("0"))
    max_active_batches_per_user: int = Field(default=1, ge=1)
    max_active_packages_per_user: int = Field(default=1, ge=1)
    metadata_json: dict[str, Any] | None = None


class TaskSystemConfigResponse(H5MemberCamelModel):
    account_id: str
    site_id: str | None = None
    status: str = "active"
    whatsapp_binding_reward_enabled: bool = True
    whatsapp_binding_reward_amount: Decimal = Decimal("20.00")
    whatsapp_binding_reward_wallet_type: str = "task_balance"
    whatsapp_binding_reward_currency: str = "USD"
    certified_member_enabled: bool = True
    certified_recharge_threshold: Decimal = Decimal("50.00")
    certified_recharge_scope: str = "real_recharge"
    auto_certify_on_recharge: bool = True
    newbie_task_enabled: bool = True
    newbie_plan_id: str | None = None
    newbie_auto_popup: bool = True
    official_plan_id: str | None = None
    show_task_balance_transfer_prompt: bool = True
    min_task_balance_transfer_prompt_amount: Decimal = Decimal("0.01")
    max_active_batches_per_user: int = 1
    max_active_packages_per_user: int = 1
    metadata_json: dict[str, Any] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
