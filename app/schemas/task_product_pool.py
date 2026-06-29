from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.h5_member_base import H5MemberCamelModel


class TaskProductPoolItemCreateRequest(H5MemberCamelModel):
    product_id: str = Field(min_length=1, max_length=64)
    product_name: str = Field(min_length=1, max_length=255)
    image_url: str | None = Field(default=None, max_length=512)
    price: Decimal = Field(ge=Decimal("0"))
    currency: str = Field(default="USD", min_length=1, max_length=16)
    product_description: str | None = None
    status: str = Field(default="active", min_length=1, max_length=32)
    sort_order: int = Field(default=1, ge=1)
    weight: int | None = Field(default=None, ge=1)
    metadata_json: dict[str, Any] | None = None


class TaskProductPoolItemUpdateRequest(H5MemberCamelModel):
    product_id: str | None = Field(default=None, min_length=1, max_length=64)
    product_name: str | None = Field(default=None, min_length=1, max_length=255)
    image_url: str | None = Field(default=None, max_length=512)
    price: Decimal | None = Field(default=None, ge=Decimal("0"))
    currency: str | None = Field(default=None, min_length=1, max_length=16)
    product_description: str | None = None
    status: str | None = Field(default=None, min_length=1, max_length=32)
    sort_order: int | None = Field(default=None, ge=1)
    weight: int | None = Field(default=None, ge=1)
    metadata_json: dict[str, Any] | None = None


class TaskProductPoolCreateRequest(H5MemberCamelModel):
    account_id: str = Field(min_length=1, max_length=128)
    site_id: str | None = Field(default=None, max_length=36)
    name: str = Field(min_length=1, max_length=255)
    code: str | None = Field(default=None, max_length=64)
    pool_type: str = Field(default="general", min_length=1, max_length=32)
    price_mode: str = Field(default="task_price_snapshot", min_length=1, max_length=32)
    allow_repeat_in_same_batch: bool = False
    allow_repeat_in_same_package: bool = False
    status: str = Field(default="active", min_length=1, max_length=32)
    currency: str = Field(default="USD", min_length=1, max_length=16)
    metadata_json: dict[str, Any] | None = None
    items: list[TaskProductPoolItemCreateRequest] = Field(default_factory=list)


class TaskProductPoolUpdateRequest(H5MemberCamelModel):
    site_id: str | None = Field(default=None, max_length=36)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    code: str | None = Field(default=None, max_length=64)
    pool_type: str | None = Field(default=None, min_length=1, max_length=32)
    price_mode: str | None = Field(default=None, min_length=1, max_length=32)
    allow_repeat_in_same_batch: bool | None = None
    allow_repeat_in_same_package: bool | None = None
    status: str | None = Field(default=None, min_length=1, max_length=32)
    currency: str | None = Field(default=None, min_length=1, max_length=16)
    metadata_json: dict[str, Any] | None = None


class TaskProductPoolItemsRequest(H5MemberCamelModel):
    items: list[TaskProductPoolItemCreateRequest] = Field(default_factory=list, min_length=1)


class TaskProductPoolImportRequest(H5MemberCamelModel):
    items: list[TaskProductPoolItemCreateRequest] = Field(default_factory=list, min_length=1)
    replace_existing: bool = False


class TaskProductPoolItemResponse(H5MemberCamelModel):
    id: str
    product_id: str
    product_name: str
    image_url: str | None = None
    price: Decimal
    currency: str
    product_description: str | None = None
    status: str
    sort_order: int
    weight: int | None = None
    metadata_json: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class TaskProductPoolResponse(H5MemberCamelModel):
    id: str
    account_id: str
    site_id: str | None = None
    name: str
    code: str | None = None
    pool_type: str
    price_mode: str
    allow_repeat_in_same_batch: bool
    allow_repeat_in_same_package: bool
    status: str
    currency: str
    metadata_json: dict[str, Any] | None = None
    item_count: int = 0
    items: list[TaskProductPoolItemResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
