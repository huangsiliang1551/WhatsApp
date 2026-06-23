from abc import ABC, abstractmethod

from app.schemas.ecommerce import OrderSummaryView, OrderView, ShipmentView


class EcommerceProvider(ABC):
    provider_name: str

    @abstractmethod
    async def list_orders(self, account_id: str) -> list[OrderSummaryView]:
        raise NotImplementedError

    @abstractmethod
    async def get_order(self, account_id: str, order_id: str) -> OrderView:
        raise NotImplementedError

    @abstractmethod
    async def get_shipment(self, account_id: str, tracking_number: str) -> ShipmentView:
        raise NotImplementedError
