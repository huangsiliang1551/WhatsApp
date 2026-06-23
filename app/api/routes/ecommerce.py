from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_ecommerce_service, require_permission
from app.core.auth import RequestActor
from app.services.ecommerce_service import EcommerceService

router = APIRouter(prefix="/api/ecommerce", tags=["ecommerce"])

AccountId = Annotated[str, Query(min_length=1)]

LOOKUP_RESPONSES = {
    404: {"description": "Resource was not found under the provided account scope."},
    409: {"description": "Resource lookup was ambiguous within the provided account scope."},
}


@router.get(
    "/orders",
    summary="List orders",
    description="List ecommerce orders for a given account.",
    tags=["ecommerce"],
)
async def list_orders(
    account_id: AccountId,
    ecommerce_service: EcommerceService = Depends(get_ecommerce_service),
    actor: RequestActor = Depends(require_permission("ecommerce.orders")),
) -> list[dict[str, object]]:
    actor.require_account_access(account_id)
    return [
        item.model_dump()
        for item in await ecommerce_service.list_orders(account_id=account_id)
    ]


@router.get(
    "/orders/{order_id}",
    summary="Get order",
    description="Get ecommerce order details by order ID.",
    tags=["ecommerce"],
    responses=LOOKUP_RESPONSES,
)
async def get_order(
    order_id: str,
    account_id: AccountId,
    ecommerce_service: EcommerceService = Depends(get_ecommerce_service),
    actor: RequestActor = Depends(require_permission("ecommerce.orders")),
) -> dict[str, object]:
    actor.require_account_access(account_id)
    try:
        return (
            await ecommerce_service.get_order(account_id=account_id, order_id=order_id)
        ).model_dump()
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get(
    "/shipments/{tracking_number}",
    summary="Get shipment",
    description="Get shipment details by tracking number.",
    tags=["ecommerce"],
    responses=LOOKUP_RESPONSES,
)
async def get_shipment(
    tracking_number: str,
    account_id: AccountId,
    ecommerce_service: EcommerceService = Depends(get_ecommerce_service),
    actor: RequestActor = Depends(require_permission("ecommerce.logistics")),
) -> dict[str, object]:
    actor.require_account_access(account_id)
    try:
        return (
            await ecommerce_service.get_shipment(
                account_id=account_id,
                tracking_number=tracking_number,
            )
        ).model_dump()
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
