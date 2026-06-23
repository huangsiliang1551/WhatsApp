from app.providers.ecommerce.base import EcommerceProvider
from app.schemas.ecommerce import (
    EcommerceOrderShipmentView,
    OrderItemView,
    OrderSummaryView,
    OrderView,
    ShipmentView,
    TrackingEventView,
)


class MockEcommerceProvider(EcommerceProvider):
    provider_name = "mock"

    def __init__(self) -> None:
        self._orders = _build_mock_orders()
        self._shipments = _build_mock_shipments()

    async def list_orders(self, account_id: str) -> list[OrderSummaryView]:
        return [
            OrderSummaryView(
                account_id=order.account_id,
                order_id=order.order_id,
                customer_name=order.customer_name,
                payment_status=order.payment_status,
                fulfillment_status=order.fulfillment_status,
                currency=order.currency,
                total_amount=order.total_amount,
                created_at=order.created_at,
                tracking_number=(
                    order.shipments[0].tracking_number if order.shipments else None
                ),
            )
            for order in self._orders.get(account_id, [])
        ]

    async def get_order(self, account_id: str, order_id: str) -> OrderView:
        normalized_order_id = order_id.strip().lower()
        for order in self._orders.get(account_id, []):
            if order.order_id.lower() == normalized_order_id:
                return order
        raise LookupError(f"Order '{order_id}' for account '{account_id}' was not found.")

    async def get_shipment(self, account_id: str, tracking_number: str) -> ShipmentView:
        normalized_tracking_number = tracking_number.strip().lower()
        for shipment in self._shipments.get(account_id, []):
            if shipment.tracking_number.lower() == normalized_tracking_number:
                return shipment
        raise LookupError(
            f"Shipment '{tracking_number}' for account '{account_id}' was not found."
        )


def _build_mock_orders() -> dict[str, list[OrderView]]:
    return {
        "demo-account-es": [
            OrderView(
                account_id="demo-account-es",
                order_id="MOCK-1001",
                external_order_id="SHOP-ES-9001",
                customer_id="customer-es-1",
                customer_name="Sofia Alvarez",
                currency="USD",
                payment_status="paid",
                fulfillment_status="shipped",
                total_amount=129.5,
                created_at="2026-06-04T08:30:00Z",
                updated_at="2026-06-05T03:10:00Z",
                shipping_address="Calle Mayor 18, Madrid, ES",
                items=[
                    OrderItemView(
                        sku="SKU-BAG-01",
                        title="Travel Tote",
                        quantity=1,
                        unit_price=79.5,
                        currency="USD",
                    ),
                    OrderItemView(
                        sku="SKU-STRAP-02",
                        title="Canvas Shoulder Strap",
                        quantity=1,
                        unit_price=50,
                        currency="USD",
                    ),
                ],
                shipments=[
                    EcommerceOrderShipmentView(
                        shipment_id="ship-es-1001",
                        tracking_number="YTES123456789",
                        carrier="YunTrack Express",
                        status="in_transit",
                        shipped_at="2026-06-04T14:45:00Z",
                        estimated_delivery_at="2026-06-08T12:00:00Z",
                    )
                ],
            )
        ],
        "demo-account-fr": [
            OrderView(
                account_id="demo-account-fr",
                order_id="MOCK-2001",
                external_order_id="SHOP-FR-4410",
                customer_id="customer-fr-1",
                customer_name="Camille Martin",
                currency="EUR",
                payment_status="paid",
                fulfillment_status="processing",
                total_amount=88,
                created_at="2026-06-03T09:12:00Z",
                updated_at="2026-06-06T01:20:00Z",
                shipping_address="15 Rue de Rivoli, Paris, FR",
                items=[
                    OrderItemView(
                        sku="SKU-LAMP-07",
                        title="Desk Lamp",
                        quantity=1,
                        unit_price=58,
                        currency="EUR",
                    ),
                    OrderItemView(
                        sku="SKU-BULB-02",
                        title="Warm LED Bulb",
                        quantity=2,
                        unit_price=15,
                        currency="EUR",
                    ),
                ],
                shipments=[
                    EcommerceOrderShipmentView(
                        shipment_id="ship-fr-2001",
                        tracking_number="FRPOST987654321",
                        carrier="La Poste",
                        status="processing",
                        shipped_at=None,
                        estimated_delivery_at="2026-06-09T16:00:00Z",
                    )
                ],
            )
        ],
        "demo-account-ar": [
            OrderView(
                account_id="demo-account-ar",
                order_id="MOCK-3001",
                external_order_id="SHOP-AR-7712",
                customer_id="customer-ar-1",
                customer_name="Omar Hassan",
                currency="AED",
                payment_status="paid",
                fulfillment_status="delivered",
                total_amount=245,
                created_at="2026-05-29T11:00:00Z",
                updated_at="2026-06-02T06:30:00Z",
                shipping_address="Sheikh Zayed Road, Dubai, AE",
                items=[
                    OrderItemView(
                        sku="SKU-WATCH-03",
                        title="Sport Watch",
                        quantity=1,
                        unit_price=245,
                        currency="AED",
                    )
                ],
                shipments=[
                    EcommerceOrderShipmentView(
                        shipment_id="ship-ar-3001",
                        tracking_number="ARAMEX556677889",
                        carrier="Aramex",
                        status="delivered",
                        shipped_at="2026-05-30T07:00:00Z",
                        estimated_delivery_at="2026-06-02T18:00:00Z",
                    )
                ],
            )
        ],
    }


def _build_mock_shipments() -> dict[str, list[ShipmentView]]:
    return {
        "demo-account-es": [
            ShipmentView(
                account_id="demo-account-es",
                order_id="MOCK-1001",
                tracking_number="YTES123456789",
                carrier="YunTrack Express",
                status="in_transit",
                estimated_delivery_at="2026-06-08T12:00:00Z",
                recipient_name="Sofia Alvarez",
                destination="Madrid, ES",
                events=[
                    TrackingEventView(
                        status="label_created",
                        location="Shenzhen, CN",
                        description="Shipping label created by warehouse.",
                        occurred_at="2026-06-04T09:20:00Z",
                    ),
                    TrackingEventView(
                        status="departed_origin",
                        location="Shenzhen, CN",
                        description="Parcel departed export facility.",
                        occurred_at="2026-06-04T16:40:00Z",
                    ),
                    TrackingEventView(
                        status="arrived_hub",
                        location="Madrid, ES",
                        description="Parcel arrived at destination hub.",
                        occurred_at="2026-06-05T22:15:00Z",
                    ),
                ],
            )
        ],
        "demo-account-fr": [
            ShipmentView(
                account_id="demo-account-fr",
                order_id="MOCK-2001",
                tracking_number="FRPOST987654321",
                carrier="La Poste",
                status="processing",
                estimated_delivery_at="2026-06-09T16:00:00Z",
                recipient_name="Camille Martin",
                destination="Paris, FR",
                events=[
                    TrackingEventView(
                        status="payment_confirmed",
                        location="Paris, FR",
                        description="Order paid and queued for packing.",
                        occurred_at="2026-06-03T09:20:00Z",
                    ),
                    TrackingEventView(
                        status="packing",
                        location="Lyon, FR",
                        description="Warehouse is packing the order.",
                        occurred_at="2026-06-06T01:20:00Z",
                    ),
                ],
            )
        ],
        "demo-account-ar": [
            ShipmentView(
                account_id="demo-account-ar",
                order_id="MOCK-3001",
                tracking_number="ARAMEX556677889",
                carrier="Aramex",
                status="delivered",
                estimated_delivery_at="2026-06-02T18:00:00Z",
                recipient_name="Omar Hassan",
                destination="Dubai, AE",
                events=[
                    TrackingEventView(
                        status="picked_up",
                        location="Dubai, AE",
                        description="Courier picked up the parcel.",
                        occurred_at="2026-05-30T08:10:00Z",
                    ),
                    TrackingEventView(
                        status="out_for_delivery",
                        location="Dubai, AE",
                        description="Courier is out for delivery.",
                        occurred_at="2026-06-02T09:05:00Z",
                    ),
                    TrackingEventView(
                        status="delivered",
                        location="Dubai, AE",
                        description="Recipient signed for the parcel.",
                        occurred_at="2026-06-02T15:42:00Z",
                    ),
                ],
            )
        ],
    }
