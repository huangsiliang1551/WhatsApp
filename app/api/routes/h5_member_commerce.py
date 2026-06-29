from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import (
    get_current_h5_member_context,
    get_h5_member_commerce_service,
    get_runtime_state_service,
)
from app.schemas.h5_member_commerce import (
    H5MemberOrderResponse,
    H5RechargeCreateRequest,
    H5TaskPackagePayload,
    H5TaskPackagePurchaseResponse,
    H5WithdrawalCreateRequest,
    H5WithdrawalResponse,
    H5WithdrawLeaderboardEntryResponse,
    H5WalletSummaryResponse,
    H5WalletTransactionResponse,
    H5WalletTransferRequest,
)
from app.services.h5_member_auth_service import H5MemberContext
from app.services.h5_member_commerce_service import H5MemberCommerceService
from app.services.runtime_state import RuntimeStateStore

router = APIRouter(prefix="/api/h5", tags=["h5-commerce"])


@router.get(
    "/task-packages",
    summary="List H5 task packages",
    description="List available task packages for the authenticated H5 member.",
    tags=["h5-commerce"],
)
async def list_h5_task_packages(
    status: str | None = None,
    commerce_service: H5MemberCommerceService = Depends(get_h5_member_commerce_service),
    context: H5MemberContext = Depends(get_current_h5_member_context),
) -> list[H5TaskPackagePayload]:
    try:
        return await commerce_service.list_task_packages(context=context, status=status)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get(
    "/tasks/packages",
    summary="List H5 task packages (spec alias)",
    description="Compatibility alias for listing task packages for the authenticated H5 member.",
    tags=["h5-commerce"],
)
async def list_h5_task_packages_alias(
    status: str | None = None,
    commerce_service: H5MemberCommerceService = Depends(get_h5_member_commerce_service),
    context: H5MemberContext = Depends(get_current_h5_member_context),
) -> list[H5TaskPackagePayload]:
    return await list_h5_task_packages(
        status=status,
        commerce_service=commerce_service,
        context=context,
    )


@router.get(
    "/task-packages/{package_id}",
    summary="Get task package detail",
    description="Get details of a specific H5 task package.",
    tags=["h5-commerce"],
)
async def get_h5_task_package_detail(
    package_id: str,
    commerce_service: H5MemberCommerceService = Depends(get_h5_member_commerce_service),
    context: H5MemberContext = Depends(get_current_h5_member_context),
) -> H5TaskPackagePayload:
    try:
        return await commerce_service.get_task_package(context=context, package_id=package_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get(
    "/tasks/packages/{package_id}",
    summary="Get task package detail (spec alias)",
    description="Compatibility alias for getting a specific H5 task package.",
    tags=["h5-commerce"],
)
async def get_h5_task_package_detail_alias(
    package_id: str,
    commerce_service: H5MemberCommerceService = Depends(get_h5_member_commerce_service),
    context: H5MemberContext = Depends(get_current_h5_member_context),
) -> H5TaskPackagePayload:
    return await get_h5_task_package_detail(
        package_id=package_id,
        commerce_service=commerce_service,
        context=context,
    )


@router.post(
    "/task-packages/{package_id}/claim",
    summary="Claim task package",
    description="Claim a pending task package for the authenticated H5 member.",
    tags=["h5-commerce"],
)
async def claim_h5_task_package(
    package_id: str,
    commerce_service: H5MemberCommerceService = Depends(get_h5_member_commerce_service),
    context: H5MemberContext = Depends(get_current_h5_member_context),
) -> H5TaskPackagePayload:
    try:
        return await commerce_service.claim_task_package(context=context, package_id=package_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post(
    "/tasks/packages/{package_id}/claim",
    summary="Claim task package (spec alias)",
    description="Compatibility alias for claiming a pending H5 task package.",
    tags=["h5-commerce"],
)
async def claim_h5_task_package_alias(
    package_id: str,
    commerce_service: H5MemberCommerceService = Depends(get_h5_member_commerce_service),
    context: H5MemberContext = Depends(get_current_h5_member_context),
) -> H5TaskPackagePayload:
    return await claim_h5_task_package(
        package_id=package_id,
        commerce_service=commerce_service,
        context=context,
    )


@router.post(
    "/task-packages/{package_id}/items/{item_id}/purchase",
    summary="Purchase task package item",
    description="Purchase a specific item from a task package.",
    tags=["h5-commerce"],
)
async def purchase_h5_task_package_item(
    package_id: str,
    item_id: str,
    commerce_service: H5MemberCommerceService = Depends(get_h5_member_commerce_service),
    context: H5MemberContext = Depends(get_current_h5_member_context),
) -> H5TaskPackagePurchaseResponse:
    try:
        return await commerce_service.purchase_task_package_item(
            context=context,
            package_id=package_id,
            item_id=item_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post(
    "/tasks/packages/{package_id}/current-product/start",
    summary="Start current task package product (spec alias)",
    description="Compatibility alias that returns the current active task package detail.",
    tags=["h5-commerce"],
)
async def start_h5_task_package_current_product(
    package_id: str,
    commerce_service: H5MemberCommerceService = Depends(get_h5_member_commerce_service),
    context: H5MemberContext = Depends(get_current_h5_member_context),
) -> H5TaskPackagePayload:
    try:
        return await commerce_service.start_current_task_package_item(
            context=context,
            package_id=package_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post(
    "/tasks/packages/{package_id}/current-product/complete",
    summary="Complete current task package product (spec alias)",
    description="Compatibility alias that completes the current visible task package product.",
    tags=["h5-commerce"],
)
async def complete_h5_task_package_current_product(
    package_id: str,
    commerce_service: H5MemberCommerceService = Depends(get_h5_member_commerce_service),
    context: H5MemberContext = Depends(get_current_h5_member_context),
) -> H5TaskPackagePurchaseResponse:
    task_package = await get_h5_task_package_detail(
        package_id=package_id,
        commerce_service=commerce_service,
        context=context,
    )
    current_item = task_package.current_item
    if current_item is None:
        wallet = await commerce_service.get_wallet_summary(context=context, create_if_missing=True)
        assert wallet is not None
        return H5TaskPackagePurchaseResponse(
            success=False,
            task_package=task_package,
            wallet=wallet,
            reason="No current product is available for completion.",
        )
    return await purchase_h5_task_package_item(
        package_id=package_id,
        item_id=current_item.id,
        commerce_service=commerce_service,
        context=context,
    )


@router.get(
    "/orders",
    summary="List H5 orders",
    description="List orders for the authenticated H5 member.",
    tags=["h5-commerce"],
)
async def list_h5_orders(
    commerce_service: H5MemberCommerceService = Depends(get_h5_member_commerce_service),
    context: H5MemberContext = Depends(get_current_h5_member_context),
) -> list[H5MemberOrderResponse]:
    return await commerce_service.list_orders(context=context)


@router.get(
    "/wallet",
    summary="Get wallet summary",
    description="Get wallet summary with system and task balances.",
    tags=["h5-commerce"],
)
async def get_h5_wallet_summary(
    commerce_service: H5MemberCommerceService = Depends(get_h5_member_commerce_service),
    context: H5MemberContext = Depends(get_current_h5_member_context),
) -> H5WalletSummaryResponse:
    wallet = await commerce_service.get_wallet_summary(context=context, create_if_missing=True)
    assert wallet is not None
    return wallet


@router.get(
    "/wallet/transactions",
    summary="List wallet transactions",
    description="List wallet transaction history for the authenticated H5 member.",
    tags=["h5-commerce"],
)
async def list_h5_wallet_transactions(
    commerce_service: H5MemberCommerceService = Depends(get_h5_member_commerce_service),
    context: H5MemberContext = Depends(get_current_h5_member_context),
) -> list[H5WalletTransactionResponse]:
    return await commerce_service.list_wallet_transactions(context=context)


@router.post(
    "/wallet/recharges",
    summary="Create wallet recharge",
    description="Create a wallet recharge request for the authenticated H5 member.",
    tags=["h5-commerce"],
)
async def create_h5_wallet_recharge(
    payload: H5RechargeCreateRequest,
    commerce_service: H5MemberCommerceService = Depends(get_h5_member_commerce_service),
    context: H5MemberContext = Depends(get_current_h5_member_context),
) -> H5WalletSummaryResponse:
    return await commerce_service.create_recharge(context=context, amount=Decimal(str(payload.amount)))


@router.post(
    "/wallet/transfers",
    summary="Create wallet transfer",
    description="Transfer funds from task balance to system balance.",
    tags=["h5-commerce"],
)
async def create_h5_wallet_transfer(
    payload: H5WalletTransferRequest,
    commerce_service: H5MemberCommerceService = Depends(get_h5_member_commerce_service),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    context: H5MemberContext = Depends(get_current_h5_member_context),
) -> H5WalletSummaryResponse:
    try:
        wallet = await commerce_service.transfer_task_balance(
            context=context,
            amount=Decimal(str(payload.amount)),
        )
        runtime_state.add_audit_log(
            account_id=context.account_id,
            actor_type="member",
            actor_id=context.user.id,
            action="h5_task_balance_transferred",
            target_type="member_profile",
            target_id=context.member_profile.id,
            payload={
                "user_id": context.user.id,
                "site_id": context.site.id,
                "amount": float(Decimal(str(payload.amount))),
                "currency": wallet.currency,
                "transaction_type": "task_to_system_transfer",
            },
        )
        runtime_state.commit()
        return wallet
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post(
    "/wallet/task-balance/transfer",
    summary="Create task balance transfer (spec alias)",
    description="Compatibility alias for transferring task balance to system balance.",
    tags=["h5-commerce"],
)
async def create_h5_wallet_transfer_alias(
    payload: H5WalletTransferRequest,
    commerce_service: H5MemberCommerceService = Depends(get_h5_member_commerce_service),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    context: H5MemberContext = Depends(get_current_h5_member_context),
) -> H5WalletSummaryResponse:
    return await create_h5_wallet_transfer(
        payload=payload,
        commerce_service=commerce_service,
        runtime_state=runtime_state,
        context=context,
    )


@router.post(
    "/withdrawals",
    summary="Create withdrawal",
    description="Create a withdrawal request for the authenticated H5 member.",
    tags=["h5-commerce"],
)
async def create_h5_withdrawal(
    payload: H5WithdrawalCreateRequest,
    commerce_service: H5MemberCommerceService = Depends(get_h5_member_commerce_service),
    context: H5MemberContext = Depends(get_current_h5_member_context),
) -> H5WithdrawalResponse:
    try:
        return await commerce_service.create_withdrawal(
            context=context,
            amount=Decimal(str(payload.amount)),
            withdraw_account_type=payload.withdraw_account_type,
            bank_name=payload.bank_name,
            account_no=payload.account_no,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get(
    "/withdrawals",
    summary="List withdrawals",
    description="List withdrawal requests for the authenticated H5 member.",
    tags=["h5-commerce"],
)
async def list_h5_withdrawals(
    commerce_service: H5MemberCommerceService = Depends(get_h5_member_commerce_service),
    context: H5MemberContext = Depends(get_current_h5_member_context),
) -> list[H5WithdrawalResponse]:
    return await commerce_service.list_withdrawals(context=context)


@router.get(
    "/withdraw-leaderboard",
    summary="Get withdrawal leaderboard",
    description="Get the top withdrawal leaderboard entries.",
    tags=["h5-commerce"],
)
async def get_h5_withdraw_leaderboard(
    commerce_service: H5MemberCommerceService = Depends(get_h5_member_commerce_service),
    context: H5MemberContext = Depends(get_current_h5_member_context),
) -> list[H5WithdrawLeaderboardEntryResponse]:
    return await commerce_service.get_withdraw_leaderboard(context=context)
