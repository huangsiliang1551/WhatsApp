import structlog

from app.providers.ecommerce.base import EcommerceProvider
from app.schemas.ecommerce import OrderSummaryView, OrderView, ShipmentView
from app.services.runtime_state import RuntimeStateStore

logger = structlog.get_logger()


class EcommerceService:
    def __init__(
        self,
        provider: EcommerceProvider,
        runtime_state: RuntimeStateStore,
    ) -> None:
        self._provider = provider
        self._runtime_state = runtime_state

    async def list_orders(self, account_id: str) -> list[OrderSummaryView]:
        orders = await self._provider.list_orders(account_id=account_id)
        try:
            self._runtime_state.add_audit_log(
                account_id=account_id,
                actor_type="system",
                actor_id=None,
                action="ecommerce_orders_listed",
                target_type="ecommerce_account",
                target_id=account_id,
                payload={"count": len(orders), "provider": self._provider.provider_name},
            )
            self._runtime_state.commit()
        except Exception as exc:
            logger.warning("audit_log_failed", action="ecommerce_orders_listed", error=str(exc))
        return orders

    async def get_order(self, account_id: str, order_id: str) -> OrderView:
        order = await self._provider.get_order(account_id=account_id, order_id=order_id)
        try:
            self._runtime_state.add_audit_log(
                account_id=account_id,
                actor_type="system",
                actor_id=None,
                action="ecommerce_order_queried",
                target_type="order",
                target_id=order_id,
                payload={"provider": self._provider.provider_name},
            )
            self._runtime_state.commit()
        except Exception as exc:
            logger.warning("audit_log_failed", action="ecommerce_order_queried", error=str(exc))
        return order

    async def get_shipment(self, account_id: str, tracking_number: str) -> ShipmentView:
        shipment = await self._provider.get_shipment(
            account_id=account_id,
            tracking_number=tracking_number,
        )
        try:
            self._runtime_state.add_audit_log(
                account_id=account_id,
                actor_type="system",
                actor_id=None,
                action="ecommerce_shipment_queried",
                target_type="shipment",
                target_id=tracking_number,
                payload={"provider": self._provider.provider_name},
            )
            self._runtime_state.commit()
        except Exception as exc:
            logger.warning("audit_log_failed", action="ecommerce_shipment_queried", error=str(exc))
        return shipment
