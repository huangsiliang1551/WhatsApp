from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.api.deps import (
    get_current_h5_member_context,
    get_h5_member_auth_service,
    get_h5_member_commerce_service,
    get_h5_member_fragment_service,
    get_h5_member_notification_service,
    get_h5_member_verification_service,
    get_task_service,
    get_ticket_service,
)
from app.core.settings import Settings, get_settings
from app.schemas.h5_member_auth import H5MemberAuthResponse, H5MemberLoginRequest, H5MemberRegisterRequest
from app.services.h5_member_auth_service import H5AuthTokens, H5MemberAuthService, H5MemberContext
from app.services.h5_member_commerce_service import H5MemberCommerceService
from app.services.h5_member_fragment_service import H5MemberFragmentService
from app.services.h5_member_notification_service import H5MemberNotificationService
from app.services.h5_member_verification_service import H5MemberVerificationService
from app.services.task_service import TaskService
from app.services.ticket_service import TicketService

router = APIRouter(prefix="/api/h5", tags=["h5-auth"])


@router.post(
    "/auth/register",
    summary="Register H5 member",
    description="Register a new H5 member account.",
    tags=["h5-auth"],
)
async def register_h5_member(
    payload: H5MemberRegisterRequest,
    response: Response,
    request: Request,
    auth_service: H5MemberAuthService = Depends(get_h5_member_auth_service),
    settings: Settings = Depends(get_settings),
) -> H5MemberAuthResponse:
    try:
        context, tokens = await auth_service.register(
            payload,
            client_ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    _set_auth_cookies(response=response, tokens=tokens, settings=settings)
    return auth_service.build_auth_response(context)


@router.post(
    "/auth/login",
    summary="Login H5 member",
    description="Authenticate H5 member and return session tokens.",
    tags=["h5-auth"],
)
async def login_h5_member(
    payload: H5MemberLoginRequest,
    response: Response,
    request: Request,
    auth_service: H5MemberAuthService = Depends(get_h5_member_auth_service),
    settings: Settings = Depends(get_settings),
) -> H5MemberAuthResponse:
    try:
        context, tokens = await auth_service.login(
            payload,
            client_ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    except LookupError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    _set_auth_cookies(response=response, tokens=tokens, settings=settings)
    return auth_service.build_auth_response(context)


@router.post(
    "/auth/logout",
    summary="Logout H5 member",
    description="Logout H5 member and clear session cookies.",
    tags=["h5-auth"],
)
async def logout_h5_member(
    response: Response,
    request: Request,
    auth_service: H5MemberAuthService = Depends(get_h5_member_auth_service),
    settings: Settings = Depends(get_settings),
) -> dict[str, bool]:
    await auth_service.logout(
        session_token=request.cookies.get(settings.h5_member_session_cookie_name),
        refresh_token=request.cookies.get(settings.h5_member_refresh_cookie_name),
    )
    _clear_auth_cookies(response=response, settings=settings)
    return {"ok": True}


@router.post(
    "/auth/refresh",
    summary="Refresh H5 session",
    description="Refresh H5 member session using refresh token cookie.",
    tags=["h5-auth"],
)
async def refresh_h5_member_session(
    response: Response,
    request: Request,
    auth_service: H5MemberAuthService = Depends(get_h5_member_auth_service),
    settings: Settings = Depends(get_settings),
) -> H5MemberAuthResponse:
    try:
        context, tokens = await auth_service.refresh(
            refresh_token=request.cookies.get(settings.h5_member_refresh_cookie_name),
            client_ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    except LookupError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    if not tokens.session_token:
        tokens.session_token = request.cookies.get(settings.h5_member_session_cookie_name) or ""
    if not tokens.refresh_token:
        tokens.refresh_token = request.cookies.get(settings.h5_member_refresh_cookie_name) or ""
    _set_auth_cookies(response=response, tokens=tokens, settings=settings)
    return auth_service.build_auth_response(context)


@router.get(
    "/auth/me",
    summary="Get H5 member profile",
    description="Returns the authenticated H5 member profile.",
    tags=["h5-auth"],
)
async def get_h5_member_me(
    auth_service: H5MemberAuthService = Depends(get_h5_member_auth_service),
    context: H5MemberContext = Depends(get_current_h5_member_context),
) -> H5MemberAuthResponse:
    return auth_service.build_auth_response(context)


@router.get(
    "/member/home",
    summary="Get H5 member home",
    description="Returns aggregated home data for the authenticated H5 member.",
    tags=["h5-auth"],
)
async def get_h5_member_home(
    auth_service: H5MemberAuthService = Depends(get_h5_member_auth_service),
    commerce_service: H5MemberCommerceService = Depends(get_h5_member_commerce_service),
    fragment_service: H5MemberFragmentService = Depends(get_h5_member_fragment_service),
    notification_service: H5MemberNotificationService = Depends(get_h5_member_notification_service),
    verification_service: H5MemberVerificationService = Depends(get_h5_member_verification_service),
    task_service: TaskService = Depends(get_task_service),
    ticket_service: TicketService = Depends(get_ticket_service),
    context: H5MemberContext = Depends(get_current_h5_member_context),
) -> dict[str, object]:
    home = await auth_service.build_home_response(
        context=context,
        task_service=task_service,
        ticket_service=ticket_service,
    )
    task_packages = await commerce_service.list_task_packages(context=context)
    wallet_summary = await commerce_service.get_wallet_summary(
        context=context,
        create_if_missing=False,
    )
    home.pending_claim_count = sum(1 for item in task_packages if item.status == "pending_claim")
    home.active_count = sum(1 for item in task_packages if item.status == "active")
    home.expiring_count = sum(
        1 for item in task_packages if item.status == "active" and item.countdown_seconds <= 6 * 3600
    )
    home.unread_message_count = await notification_service.count_unread_notifications(context=context)
    if wallet_summary is not None:
        home.wallet.system_balance = wallet_summary.system_balance
        home.wallet.task_balance = wallet_summary.task_balance
        home.wallet.currency = wallet_summary.currency
    verification_summary = await verification_service.get_summary(context=context)
    home.verification.current_status = verification_summary.current_status
    home.verification.has_active_request = verification_summary.has_active_request
    fragment_overview = await fragment_service.get_overview(context=context)
    home.fragments.reward_name = fragment_overview.reward_name
    home.fragments.completed_count = sum(
        1 for item in fragment_overview.inventory if item.owned >= item.required
    )
    home.fragments.total_count = len(fragment_overview.inventory)
    home.fragments.missing_count = sum(
        max(0, item.required - item.owned) for item in fragment_overview.inventory
    )
    home.fragments.can_exchange = (
        bool(fragment_overview.inventory)
        and home.fragments.completed_count == home.fragments.total_count
    )
    home.fragments.shipping_order_count = len(fragment_overview.shipping_orders)
    home.fragments.latest_shipping_status = (
        fragment_overview.shipping_orders[0].status if fragment_overview.shipping_orders else None
    )
    home.recent_messages = (await notification_service.list_notifications(context=context))[:5]
    home.leaderboard = (await commerce_service.get_withdraw_leaderboard(context=context))[:5]
    return home.model_dump(mode="json", by_alias=True)


def _set_auth_cookies(*, response: Response, tokens: H5AuthTokens, settings: Settings) -> None:
    cookie_domain = settings.h5_member_cookie_domain or None
    response.set_cookie(
        key=settings.h5_member_session_cookie_name,
        value=tokens.session_token,
        httponly=True,
        secure=settings.h5_member_cookie_secure,
        samesite=settings.h5_member_cookie_samesite,
        domain=cookie_domain,
        path="/",
        max_age=settings.h5_member_session_ttl_hours * 3600,
    )
    response.set_cookie(
        key=settings.h5_member_refresh_cookie_name,
        value=tokens.refresh_token,
        httponly=True,
        secure=settings.h5_member_cookie_secure,
        samesite=settings.h5_member_cookie_samesite,
        domain=cookie_domain,
        path="/",
        max_age=settings.h5_member_refresh_ttl_days * 86400,
    )


def _clear_auth_cookies(*, response: Response, settings: Settings) -> None:
    cookie_domain = settings.h5_member_cookie_domain or None
    response.delete_cookie(
        key=settings.h5_member_session_cookie_name,
        domain=cookie_domain,
        path="/",
    )
    response.delete_cookie(
        key=settings.h5_member_refresh_cookie_name,
        domain=cookie_domain,
        path="/",
    )
