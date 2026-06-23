from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.h5_member_base import H5MemberCamelModel


class H5ShippingAddressRequest(H5MemberCamelModel):
    receiver: str = Field(min_length=1, max_length=255)
    phone: str = Field(min_length=1, max_length=32)
    country: str = Field(min_length=1, max_length=128)
    province: str = Field(min_length=1, max_length=128)
    city: str = Field(min_length=1, max_length=128)
    address_line: str = Field(min_length=1, max_length=2000)


class H5RewardShippingAddressResponse(H5MemberCamelModel):
    receiver: str
    phone: str
    country: str
    province: str
    city: str
    address_line: str


class H5RewardShippingOrderResponse(H5MemberCamelModel):
    id: str
    reward_name: str
    status: str
    created_at: datetime
    address: H5RewardShippingAddressResponse | None = None


class H5FragmentInventoryItemResponse(H5MemberCamelModel):
    id: str
    fragment_key: str
    name: str
    rarity: str
    color: str
    owned: int
    required: int


class H5FragmentDropLogResponse(H5MemberCamelModel):
    id: str
    fragment_id: str
    fragment_key: str
    fragment_name: str
    source: str
    created_at: datetime


class H5FragmentOverviewResponse(H5MemberCamelModel):
    inventory: list[H5FragmentInventoryItemResponse]
    drop_logs: list[H5FragmentDropLogResponse]
    reward_name: str
    shipping_orders: list[H5RewardShippingOrderResponse]
