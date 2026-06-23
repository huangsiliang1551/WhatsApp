from pydantic import BaseModel, Field


class OrderItemView(BaseModel):
    sku: str
    title: str
    quantity: int = Field(ge=1)
    unit_price: float = Field(ge=0)
    currency: str


class EcommerceOrderShipmentView(BaseModel):
    shipment_id: str
    tracking_number: str
    carrier: str
    status: str
    shipped_at: str | None = None
    estimated_delivery_at: str | None = None


class TrackingEventView(BaseModel):
    status: str
    location: str
    description: str
    occurred_at: str


class ShipmentView(BaseModel):
    account_id: str
    order_id: str
    tracking_number: str
    carrier: str
    status: str
    estimated_delivery_at: str | None = None
    recipient_name: str
    destination: str
    events: list[TrackingEventView]


class OrderView(BaseModel):
    account_id: str
    order_id: str
    external_order_id: str
    customer_id: str
    customer_name: str
    currency: str
    payment_status: str
    fulfillment_status: str
    total_amount: float = Field(ge=0)
    created_at: str
    updated_at: str
    shipping_address: str
    items: list[OrderItemView]
    shipments: list[EcommerceOrderShipmentView]


class OrderSummaryView(BaseModel):
    account_id: str
    order_id: str
    customer_name: str
    payment_status: str
    fulfillment_status: str
    currency: str
    total_amount: float = Field(ge=0)
    created_at: str
    tracking_number: str | None = None
