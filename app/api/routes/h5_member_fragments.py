from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import (
    get_current_h5_member_context,
    get_h5_member_fragment_service,
)
from app.schemas.h5_member_fragments import (
    H5FragmentOverviewResponse,
    H5RewardShippingOrderResponse,
    H5ShippingAddressRequest,
)
from app.services.h5_member_auth_service import H5MemberContext
from app.services.h5_member_fragment_service import H5MemberFragmentService

router = APIRouter(prefix="/api/h5", tags=["h5-fragments"])


@router.get(
    "/fragments",
    summary="Get fragments overview",
    description="Get reward fragment collection overview for the authenticated H5 member.",
    tags=["h5-fragments"],
)
async def get_h5_fragments_overview(
    fragment_service: H5MemberFragmentService = Depends(get_h5_member_fragment_service),
    context: H5MemberContext = Depends(get_current_h5_member_context),
) -> H5FragmentOverviewResponse:
    return await fragment_service.get_overview(context=context)


@router.post(
    "/fragments/check-in",
    summary="Check-in fragments",
    description="Perform a daily check-in to earn reward fragments.",
    tags=["h5-fragments"],
)
async def check_in_h5_fragments(
    fragment_service: H5MemberFragmentService = Depends(get_h5_member_fragment_service),
    context: H5MemberContext = Depends(get_current_h5_member_context),
) -> H5FragmentOverviewResponse:
    try:
        return await fragment_service.perform_checkin(context=context)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post(
    "/fragments/exchanges",
    summary="Create fragment exchange",
    description="Exchange completed fragments for a reward with shipping address.",
    tags=["h5-fragments"],
)
async def create_h5_fragment_exchange(
    payload: H5ShippingAddressRequest,
    fragment_service: H5MemberFragmentService = Depends(get_h5_member_fragment_service),
    context: H5MemberContext = Depends(get_current_h5_member_context),
) -> H5FragmentOverviewResponse:
    try:
        return await fragment_service.create_exchange(context=context, payload=payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get(
    "/rewards/shipping",
    summary="List reward shipping orders",
    description="List reward shipping orders for the authenticated H5 member.",
    tags=["h5-fragments"],
)
async def list_h5_reward_shipping_orders(
    fragment_service: H5MemberFragmentService = Depends(get_h5_member_fragment_service),
    context: H5MemberContext = Depends(get_current_h5_member_context),
) -> list[H5RewardShippingOrderResponse]:
    return await fragment_service.list_shipping_orders(context=context)
