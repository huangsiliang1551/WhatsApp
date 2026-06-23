from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

import structlog

from app.api.deps import get_meta_account_registry, require_permission
from app.core.auth import RequestActor
from app.schemas.meta_accounts import (
    CompleteEmbeddedSignupSessionRequest,
    EmbeddedSignupCallbackRequest,
    EmbeddedSignupCompletionStage,
    EmbeddedSignupSessionRequest,
    EmbeddedSignupSessionStatus,
    FailEmbeddedSignupSessionRequest,
    ManualMetaAccountRequest,
    MetaScopeStatusUpdateRequest,
    MetaAccountUpdateRequest,
    MetaPhoneNumberSyncResponse,
    MetaPhoneNumberScopeView,
    WebhookRuntimeStatus,
    WebhookSubscriptionStatus,
    WebhookSubscriptionView,
    WebhookVerificationStatus,
    WebhookSubscriptionRequest,
)
from app.providers.meta_management.base import MetaManagementProviderError
from app.core.settings import get_settings
from app.services.meta_account_registry import MetaAccountRegistry
from app.services.meta_account_registry import MetaAccountConflictError

router = APIRouter(prefix="/api/meta/accounts", tags=["meta-accounts"])


def _raise_meta_provider_http_error(exc: MetaManagementProviderError) -> None:
    status_code = 502
    if exc.remote_status_code is not None and 400 <= exc.remote_status_code < 500:
        status_code = 400
    raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.get(
    "",
    summary="List Meta accounts",
    description="List Meta WABA accounts with optional filters.",
    tags=["meta-accounts"],
)
async def list_meta_accounts(
    account_id: str | None = None,
    waba_id: str | None = None,
    is_active: bool | None = None,
    account_is_active: bool | None = None,
    ready_for_webhook_delivery: bool | None = None,
    ready_for_outbound_messages: bool | None = None,
    ready_for_meta_activation: bool | None = None,
    webhook_verification_status: WebhookVerificationStatus | None = None,
    webhook_runtime_status: WebhookRuntimeStatus | None = None,
    meta_account_registry: MetaAccountRegistry = Depends(get_meta_account_registry),
    actor: RequestActor = Depends(require_permission("meta.view")),
) -> list[dict[str, object]]:
    if account_id is not None:
        actor.require_account_access(account_id)
    allowed_account_ids = None if actor.is_super_admin else set(actor.account_ids)
    try:
        accounts = await meta_account_registry.list_accounts(
            account_id=account_id,
            waba_id=waba_id,
            allowed_account_ids=allowed_account_ids,
            is_active=is_active,
            account_is_active=account_is_active,
            ready_for_webhook_delivery=ready_for_webhook_delivery,
            ready_for_outbound_messages=ready_for_outbound_messages,
            ready_for_meta_activation=ready_for_meta_activation,
            webhook_verification_status=webhook_verification_status,
            webhook_runtime_status=webhook_runtime_status,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        # DB unreachable (PostgreSQL unavailable), return empty list
        return []
    if not actor.is_super_admin:
        accounts = [account for account in accounts if actor.can_access_account(account.account_id)]
    return [account.model_dump() for account in accounts]


class DiscoverAccountRequest(BaseModel):
    waba_id: str = Field(min_length=1)
    access_token: str = ""
    account_id: str | None = None


class DiscoverFieldResult(BaseModel):
    status: str = "ok"
    value: object = None
    error: str | None = None
    error_code: int | None = None
    warnings: list[str] = Field(default_factory=list)


class DiscoverResponse(BaseModel):
    ok: bool = True
    fields: dict[str, DiscoverFieldResult] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


META_ERROR_MAP: dict[int, str] = {
    190: "Access Token 无效或已过期，请重新生成",
    200: "权限不足，Token 需具有 whatsapp_business_management 权限",
    100: "参数错误，请检查 WABA ID 格式",
    80007: "速率限制，请稍后重试",
    4: "请求过于频繁，请稍后重试",
    10: "API 暂时不可用，请稍后重试",
}


@router.post(
    "/discover",
    summary="Discover Meta account info",
    description="Given a WABA ID and Access Token, discover WABA metadata, phone numbers, and app ID from Meta Graph API.",
    tags=["meta-accounts"],
)
async def discover_meta_account(
    payload: DiscoverAccountRequest,
    meta_account_registry: MetaAccountRegistry = Depends(get_meta_account_registry),
    actor: RequestActor = Depends(require_permission("meta.edit")),
) -> DiscoverResponse:
    logger = structlog.get_logger()
    provider = meta_account_registry._meta_management_provider
    fields: dict[str, DiscoverFieldResult] = {}
    all_warnings: list[str] = []
    all_errors: list[str] = []

    # Resolve access_token: use provided token, or look up from DB when editing
    resolved_token = payload.access_token
    if not resolved_token and payload.account_id:
        waba = meta_account_registry._get_waba_by_waba_id(payload.waba_id)
        if waba is not None and waba.account_id == payload.account_id and waba.access_token:
            resolved_token = waba.access_token
            logger.info("discover_using_stored_token", account_id=payload.account_id, waba_id=payload.waba_id)
        else:
            return DiscoverResponse(
                ok=False,
                fields={},
                errors=["未找到该账户的 Access Token，请手动填写"],
                warnings=[],
            )
    if not resolved_token:
        return DiscoverResponse(
            ok=False,
            fields={},
            errors=["请提供 Access Token"],
            warnings=[],
        )

    # 1. WABA info
    try:
        waba_result = await provider.health_check(waba_id=payload.waba_id, access_token=resolved_token)
        logger.info("discover_health_check_result", waba_result_keys=list(waba_result.keys()), ok=waba_result.get("ok"), name=waba_result.get("name"), owner_business=waba_result.get("owner_business"))
        if waba_result.get("ok"):
            fields["waba_name"] = DiscoverFieldResult(
                status="ok", value=waba_result.get("name", ""),
            )
            fields["waba_id"] = DiscoverFieldResult(status="ok", value=payload.waba_id)
        else:
            error_kind = waba_result.get("error_kind", "")
            if error_kind == "network_unreachable":
                err_msg = "无法连接 Meta 服务器（graph.facebook.com），当前网络环境可能无法直接访问，建议使用代理或 VPN"
            elif error_kind == "network_timeout":
                err_msg = "连接 Meta 服务器超时，当前网络可能不稳定，请稍后重试"
            else:
                err_detail = waba_result.get("error", {})
                err_code = err_detail.get("code", 0) if isinstance(err_detail, dict) else 0
                err_msg = META_ERROR_MAP.get(err_code, str(err_detail) if isinstance(err_detail, str) else str(err_detail))
            fields["waba_name"] = DiscoverFieldResult(status="error", error=err_msg)
            all_errors.append(f"WABA 查询失败: {err_msg}")
            return DiscoverResponse(ok=False, fields=fields, errors=all_errors, warnings=all_warnings)
    except Exception as exc:
        fields["waba_name"] = DiscoverFieldResult(status="error", error=str(exc))
        all_errors.append(f"WABA 查询异常: {exc}")
        return DiscoverResponse(ok=False, fields=fields, errors=all_errors, warnings=all_warnings)

    # 2. Phone numbers
    try:
        from app.providers.meta_management.base import MetaPhoneNumberSyncCommand
        sync_cmd = MetaPhoneNumberSyncCommand(
            account_id="_discover_",
            waba_id=payload.waba_id,
            access_token=resolved_token,
            existing_phone_numbers=[],
        )
        sync_result = await provider.sync_phone_numbers(sync_cmd)
        phone_list = [
            {
                "phone_number_id": pn.phone_number_id,
                "display_phone_number": pn.display_phone_number,
                "verified_name": pn.verified_name,
                "quality_rating": pn.quality_rating,
                "is_registered": pn.is_registered,
                "is_active": pn.is_active,
            }
            for pn in sync_result.phone_numbers
        ]
        warnings = []
        unregistered = [p for p in phone_list if not p["is_registered"]]
        if unregistered:
            warnings.append(f"{len(unregistered)} 个号码未完成注册")
        fields["phone_numbers"] = DiscoverFieldResult(
            status="partial" if warnings else "ok",
            value=phone_list,
            warnings=warnings,
        )
        all_warnings.extend(warnings)
    except Exception as exc:
        fields["phone_numbers"] = DiscoverFieldResult(status="error", error=str(exc))
        all_errors.append(f"号码查询失败: {exc}")

    # 3. App ID from subscribed_apps
    try:
        from app.providers.meta_management.whatsapp_provider import WhatsAppMetaManagementProvider
        if isinstance(provider, WhatsAppMetaManagementProvider):
            result = await provider._request_json(
                method="GET",
                endpoint=f"{provider._api_base}/{provider._api_version}/{payload.waba_id}/subscribed_apps",
                access_token=resolved_token,
                params=None,
                body=None,
            )
            apps = result.get("data", [])
            if apps:
                app_id = apps[0].get("whatsapp_business_api_data", {}).get("id") or apps[0].get("id", "")
                fields["app_id"] = DiscoverFieldResult(status="ok", value=str(app_id))
            else:
                fields["app_id"] = DiscoverFieldResult(status="not_found", value=None, warnings=["未找到已订阅应用"])
        else:
            fields["app_id"] = DiscoverFieldResult(status="skipped")
    except Exception as exc:
        fields["app_id"] = DiscoverFieldResult(status="error", error=str(exc))

    # 4. Business Portfolio - from WABA response
    pf_id = waba_result.get("owner_business", "")
    fields["business_portfolio_id"] = DiscoverFieldResult(
        status="ok" if pf_id else "not_found",
        value=pf_id,
    )

    ok = len(all_errors) == 0
    return DiscoverResponse(ok=ok, fields=fields, errors=all_errors, warnings=all_warnings)


@router.post(
    "/manual",
    summary="Create manual Meta account",
    description="Manually create a Meta WABA account entry.",
    tags=["meta-accounts"],
)
async def create_manual_meta_account(
    payload: ManualMetaAccountRequest,
    meta_account_registry: MetaAccountRegistry = Depends(get_meta_account_registry),
    actor: RequestActor = Depends(require_permission("meta.create")),
) -> dict[str, object]:
    if payload.account_id:
        actor.require_account_access(payload.account_id)
    try:
        return (
            await meta_account_registry.create_manual_account(
                payload,
                actor_type=actor.actor_type,
                actor_id=actor.actor_id,
            )
        ).model_dump()
    except MetaAccountConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.patch(
    "/{account_id}/wabas/{waba_id}",
    summary="Update Meta account",
    description="Update a Meta WABA account configuration.",
    tags=["meta-accounts"],
)
async def update_meta_account(
    account_id: str,
    waba_id: str,
    payload: MetaAccountUpdateRequest,
    meta_account_registry: MetaAccountRegistry = Depends(get_meta_account_registry),
    actor: RequestActor = Depends(require_permission("meta.edit")),
) -> dict[str, object]:
    actor.require_account_access(account_id)
    try:
        return (
            await meta_account_registry.update_account(
                account_id=account_id,
                waba_id=waba_id,
                payload=payload,
                actor_type=actor.actor_type,
                actor_id=actor.actor_id,
            )
        ).model_dump()
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except MetaAccountConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post(
    "/embedded-signup/session",
    summary="Create embedded signup session",
    description="Create an embedded signup session for Meta WABA onboarding.",
    tags=["meta-accounts"],
)
async def create_embedded_signup_session(
    payload: EmbeddedSignupSessionRequest,
    meta_account_registry: MetaAccountRegistry = Depends(get_meta_account_registry),
    actor: RequestActor = Depends(require_permission("meta.create")),
) -> dict[str, object]:
    actor.require_account_access(payload.account_id)
    return (
        await meta_account_registry.create_embedded_signup_session(
            payload,
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
        )
    ).model_dump()


@router.get(
    "/embedded-signup/sessions",
    summary="List embedded signup sessions",
    description="List embedded signup sessions with optional filters.",
    tags=["meta-accounts"],
)
async def list_embedded_signup_sessions(
    account_id: str | None = None,
    status: EmbeddedSignupSessionStatus | None = None,
    completion_stage: EmbeddedSignupCompletionStage | None = None,
    remote_confirmed: bool | None = None,
    waba_id: str | None = None,
    webhook_subscription_status: WebhookSubscriptionStatus | None = None,
    webhook_verification_status: WebhookVerificationStatus | None = None,
    webhook_runtime_status: WebhookRuntimeStatus | None = None,
    ready_for_webhook_delivery: bool | None = None,
    ready_for_outbound_messages: bool | None = None,
    ready_for_meta_activation: bool | None = None,
    meta_account_registry: MetaAccountRegistry = Depends(get_meta_account_registry),
    actor: RequestActor = Depends(require_permission("meta.view")),
) -> list[dict[str, object]]:
    if account_id is not None:
        actor.require_account_access(account_id)
    allowed_account_ids = None if actor.is_super_admin else set(actor.account_ids)
    try:
        sessions = await meta_account_registry.list_embedded_signup_sessions(
            account_id=account_id,
            status=status,
            completion_stage=completion_stage,
            remote_confirmed=remote_confirmed,
            waba_id=waba_id,
            allowed_account_ids=allowed_account_ids,
            webhook_subscription_status=webhook_subscription_status,
            webhook_verification_status=webhook_verification_status,
            webhook_runtime_status=webhook_runtime_status,
            ready_for_webhook_delivery=ready_for_webhook_delivery,
            ready_for_outbound_messages=ready_for_outbound_messages,
            ready_for_meta_activation=ready_for_meta_activation,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        # DB unreachable (PostgreSQL unavailable), return empty list
        return []
    if not actor.is_super_admin:
        sessions = [session for session in sessions if actor.can_access_account(session.account_id)]
    return [
        session.model_dump()
        for session in sessions
    ]


@router.get(
    "/embedded-signup/session/{session_id}/status",
    summary="Get signup session status",
    description="Get the current status of an embedded signup session.",
    tags=["meta-accounts"],
)
async def get_embedded_signup_session_status(
    session_id: str,
    meta_account_registry: MetaAccountRegistry = Depends(get_meta_account_registry),
    actor: RequestActor = Depends(require_permission("meta.view")),
) -> dict[str, object]:
    try:
        session = await meta_account_registry.get_embedded_signup_session(
            session_id=session_id,
            allowed_account_ids=None if actor.is_super_admin else set(actor.account_ids),
        )
        return session.model_dump()
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.get(
    "/phone-numbers",
    summary="List all phone numbers",
    description="List all registered phone numbers across accounts with optional filters.",
    tags=["meta-accounts"],
)
async def list_all_phone_numbers(
    account_id: str | None = None,
    waba_id: str | None = None,
    is_registered: bool | None = None,
    is_active: bool | None = None,
    quality_rating: str | None = None,
    ready_for_webhook_delivery: bool | None = None,
    ready_for_outbound_messages: bool | None = None,
    ready_for_meta_activation: bool | None = None,
    meta_account_registry: MetaAccountRegistry = Depends(get_meta_account_registry),
    actor: RequestActor = Depends(require_permission("meta.view")),
) -> list[MetaPhoneNumberScopeView]:
    if account_id is not None:
        actor.require_account_access(account_id)
    allowed_account_ids = None if actor.is_super_admin else set(actor.account_ids)
    try:
        phone_numbers = await meta_account_registry.list_phone_numbers(
            account_id=account_id,
            waba_id=waba_id,
            allowed_account_ids=allowed_account_ids,
            is_registered=is_registered,
            is_active=is_active,
            quality_rating=quality_rating,
            ready_for_webhook_delivery=ready_for_webhook_delivery,
            ready_for_outbound_messages=ready_for_outbound_messages,
            ready_for_meta_activation=ready_for_meta_activation,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not actor.is_super_admin:
        phone_numbers = [
            phone_number
            for phone_number in phone_numbers
            if actor.can_access_account(phone_number.account_id)
        ]
    return phone_numbers


@router.get(
    "/webhook-subscriptions",
    summary="List webhook subscriptions",
    description="List webhook subscriptions with optional status filters.",
    tags=["meta-accounts"],
)
async def list_webhook_subscriptions(
    account_id: str | None = None,
    waba_id: str | None = None,
    status: WebhookSubscriptionStatus | None = None,
    webhook_verification_status: WebhookVerificationStatus | None = None,
    webhook_runtime_status: WebhookRuntimeStatus | None = None,
    meta_account_registry: MetaAccountRegistry = Depends(get_meta_account_registry),
    actor: RequestActor = Depends(require_permission("meta.view")),
) -> list[WebhookSubscriptionView]:
    if account_id is not None:
        actor.require_account_access(account_id)
    allowed_account_ids = None if actor.is_super_admin else set(actor.account_ids)
    try:
        subscriptions = await meta_account_registry.list_webhook_subscriptions(
            account_id=account_id,
            waba_id=waba_id,
            allowed_account_ids=allowed_account_ids,
            status=status,
            webhook_verification_status=webhook_verification_status,
            webhook_runtime_status=webhook_runtime_status,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        # DB unreachable (PostgreSQL unavailable), return empty list
        return []
    if not actor.is_super_admin:
        subscriptions = [
            subscription
            for subscription in subscriptions
            if actor.can_access_account(subscription.account_id)
        ]
    return subscriptions


@router.post(
    "/embedded-signup/session/{session_id}/complete",
    summary="Complete signup session",
    description="Complete an embedded signup session with final configuration.",
    tags=["meta-accounts"],
)
async def complete_embedded_signup_session(
    session_id: str,
    payload: CompleteEmbeddedSignupSessionRequest,
    meta_account_registry: MetaAccountRegistry = Depends(get_meta_account_registry),
    actor: RequestActor = Depends(require_permission("meta.edit")),
) -> dict[str, object]:
    try:
        return (
            await meta_account_registry.complete_embedded_signup_session(
                session_id=session_id,
                payload=payload,
                allowed_account_ids=None if actor.is_super_admin else set(actor.account_ids),
                actor_type=actor.actor_type,
                actor_id=actor.actor_id,
            )
        ).model_dump()
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except MetaAccountConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except MetaManagementProviderError as exc:
        _raise_meta_provider_http_error(exc)


@router.post(
    "/embedded-signup/session/{session_id}/callback",
    summary="Ingest signup callback",
    description="Ingest an embedded signup callback from Meta.",
    tags=["meta-accounts"],
)
async def ingest_embedded_signup_callback(
    session_id: str,
    payload: EmbeddedSignupCallbackRequest,
    meta_account_registry: MetaAccountRegistry = Depends(get_meta_account_registry),
    actor: RequestActor = Depends(require_permission("meta.edit")),
) -> dict[str, object]:
    try:
        return (
            await meta_account_registry.ingest_embedded_signup_callback(
                session_id=session_id,
                payload=payload,
                allowed_account_ids=None if actor.is_super_admin else set(actor.account_ids),
                actor_type=actor.actor_type,
                actor_id=actor.actor_id,
            )
        ).model_dump()
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except MetaAccountConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except MetaManagementProviderError as exc:
        _raise_meta_provider_http_error(exc)


@router.post(
    "/embedded-signup/session/{session_id}/fail",
    summary="Fail signup session",
    description="Mark an embedded signup session as failed.",
    tags=["meta-accounts"],
)
async def fail_embedded_signup_session(
    session_id: str,
    payload: FailEmbeddedSignupSessionRequest,
    meta_account_registry: MetaAccountRegistry = Depends(get_meta_account_registry),
    actor: RequestActor = Depends(require_permission("meta.edit")),
) -> dict[str, object]:
    try:
        return (
            await meta_account_registry.fail_embedded_signup_session(
                session_id=session_id,
                payload=payload,
                allowed_account_ids=None if actor.is_super_admin else set(actor.account_ids),
                actor_type=actor.actor_type,
                actor_id=actor.actor_id,
            )
        ).model_dump()
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except MetaAccountConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except MetaManagementProviderError as exc:
        _raise_meta_provider_http_error(exc)


@router.get(
    "/{account_id}/phone-numbers",
    summary="List phone numbers for account",
    description="List phone numbers for a specific account.",
    tags=["meta-accounts"],
)
async def list_phone_numbers(
    account_id: str,
    meta_account_registry: MetaAccountRegistry = Depends(get_meta_account_registry),
    actor: RequestActor = Depends(require_permission("meta.view")),
) -> list[MetaPhoneNumberScopeView]:
    actor.require_account_access(account_id)
    return await meta_account_registry.list_phone_numbers(account_id=account_id)


@router.patch(
    "/{account_id}/status",
    summary="Update account status",
    description="Activate or deactivate a Meta account.",
    tags=["meta-accounts"],
)
async def update_account_status(
    account_id: str,
    payload: MetaScopeStatusUpdateRequest,
    meta_account_registry: MetaAccountRegistry = Depends(get_meta_account_registry),
    actor: RequestActor = Depends(require_permission("meta.edit")),
) -> dict[str, object]:
    actor.require_account_access(account_id)
    try:
        await meta_account_registry.set_account_active(
            account_id=account_id,
            is_active=payload.is_active,
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
        )
        accounts = await meta_account_registry.list_accounts(account_id=account_id)
        return {
            "account_id": account_id,
            "is_active": payload.is_active,
            "wabas": [item.model_dump() for item in accounts],
        }
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/{account_id}/wabas/{waba_id}/phone-numbers",
    summary="List phone numbers for WABA",
    description="List phone numbers registered under a specific WABA.",
    tags=["meta-accounts"],
)
async def list_phone_numbers_for_waba(
    account_id: str,
    waba_id: str,
    is_active: bool | None = None,
    meta_account_registry: MetaAccountRegistry = Depends(get_meta_account_registry),
    actor: RequestActor = Depends(require_permission("meta.view")),
) -> list[MetaPhoneNumberScopeView]:
    actor.require_account_access(account_id)
    try:
        return await meta_account_registry.list_phone_numbers(
            account_id=account_id,
            waba_id=waba_id,
            is_active=is_active,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch(
    "/{account_id}/wabas/{waba_id}/status",
    summary="Update WABA status",
    description="Activate or deactivate a WABA.",
    tags=["meta-accounts"],
)
async def update_waba_status(
    account_id: str,
    waba_id: str,
    payload: MetaScopeStatusUpdateRequest,
    meta_account_registry: MetaAccountRegistry = Depends(get_meta_account_registry),
    actor: RequestActor = Depends(require_permission("meta.edit")),
) -> dict[str, object]:
    actor.require_account_access(account_id)
    try:
        return (
            await meta_account_registry.set_waba_active(
                account_id=account_id,
                waba_id=waba_id,
                is_active=payload.is_active,
                actor_type=actor.actor_type,
                actor_id=actor.actor_id,
            )
        ).model_dump()
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch(
    "/{account_id}/wabas/{waba_id}/phone-numbers/{phone_number_id}/status",
    summary="Update phone number status",
    description="Activate or deactivate a specific phone number.",
    tags=["meta-accounts"],
)
async def update_phone_number_status(
    account_id: str,
    waba_id: str,
    phone_number_id: str,
    payload: MetaScopeStatusUpdateRequest,
    meta_account_registry: MetaAccountRegistry = Depends(get_meta_account_registry),
    actor: RequestActor = Depends(require_permission("meta.edit")),
) -> MetaPhoneNumberScopeView:
    actor.require_account_access(account_id)
    try:
        return await meta_account_registry.set_phone_number_active(
            account_id=account_id,
            waba_id=waba_id,
            phone_number_id=phone_number_id,
            is_active=payload.is_active,
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/{account_id}/wabas/{waba_id}/phone-numbers/sync",
    summary="Sync phone numbers for WABA",
    description="Sync phone numbers from Meta for a specific WABA.",
    tags=["meta-accounts"],
)
async def sync_phone_numbers_for_waba(
    account_id: str,
    waba_id: str,
    meta_account_registry: MetaAccountRegistry = Depends(get_meta_account_registry),
    actor: RequestActor = Depends(require_permission("meta.edit")),
) -> MetaPhoneNumberSyncResponse:
    actor.require_account_access(account_id)
    try:
        return await meta_account_registry.sync_phone_numbers(
            account_id=account_id,
            waba_id=waba_id,
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except MetaAccountConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except MetaManagementProviderError as exc:
        _raise_meta_provider_http_error(exc)


@router.post(
    "/{account_id}/wabas/{waba_id}/webhook-subscription",
    summary="Subscribe webhook",
    description="Subscribe to WhatsApp webhook events for a WABA.",
    tags=["meta-accounts"],
)
async def subscribe_webhook(
    account_id: str,
    waba_id: str,
    payload: WebhookSubscriptionRequest,
    meta_account_registry: MetaAccountRegistry = Depends(get_meta_account_registry),
    actor: RequestActor = Depends(require_permission("meta.sync_phones")),
) -> dict[str, object]:
    actor.require_account_access(account_id)
    try:
        return (
            await meta_account_registry.subscribe_webhook(
                account_id=account_id,
                waba_id=waba_id,
                payload=payload,
                actor_type=actor.actor_type,
                actor_id=actor.actor_id,
            )
        ).model_dump()
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except MetaAccountConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except MetaManagementProviderError as exc:
        _raise_meta_provider_http_error(exc)


class GlobalWebhookConfigResponse(BaseModel):
    callback_url: str = ""
    verify_token: str = ""


class GlobalWebhookConfigUpdateRequest(BaseModel):
    callback_url: str = Field(min_length=1)
    verify_token: str | None = None


@router.delete(
    "/{account_id}/wabas/{waba_id}",
    summary="Delete Meta account",
    description="Delete a Meta WABA account and all associated phone numbers and webhook subscriptions.",
    tags=["meta-accounts"],
)
async def delete_meta_account(
    account_id: str,
    waba_id: str,
    meta_account_registry: MetaAccountRegistry = Depends(get_meta_account_registry),
    actor: RequestActor = Depends(require_permission("meta.webhook")),
) -> dict[str, object]:
    actor.require_account_access(account_id)
    try:
        return await meta_account_registry.delete_account(
            account_id=account_id,
            waba_id=waba_id,
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/{account_id}/wabas/{waba_id}/health-check",
    summary="Health check account",
    description="Test the Meta account connection by verifying credentials.",
    tags=["meta-accounts"],
)
async def health_check_meta_account(
    account_id: str,
    waba_id: str,
    meta_account_registry: MetaAccountRegistry = Depends(get_meta_account_registry),
    actor: RequestActor = Depends(require_permission("meta.delete")),
) -> dict[str, object]:
    actor.require_account_access(account_id)
    try:
        return await meta_account_registry.health_check_account(
            account_id=account_id,
            waba_id=waba_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


class SendTestMessageRequest(BaseModel):
    phone_id: str = Field(min_length=1, description="发送方 Phone Number ID（不是 WABA ID）")
    to: str = Field(min_length=1, description="目标号码（国际格式，不要带+号，如 8613800138000）")
    text: str = Field(min_length=1, max_length=4096, description="消息内容")


class QueryPhoneDetailRequest(BaseModel):
    phone_id: str = Field(min_length=1)


@router.post(
    "/{account_id}/wabas/{waba_id}/send-message",
    summary="Send test message",
    description="Send a test WhatsApp text message via the configured access token.",
    tags=["meta-accounts"],
)
async def send_test_message(
    account_id: str,
    waba_id: str,
    payload: SendTestMessageRequest,
    meta_account_registry: MetaAccountRegistry = Depends(get_meta_account_registry),
    actor: RequestActor = Depends(require_permission("meta.edit")),
) -> dict[str, object]:
    actor.require_account_access(account_id)
    try:
        return await meta_account_registry.send_test_message(
            account_id=account_id,
            waba_id=waba_id,
            phone_id=payload.phone_id,
            to=payload.to,
            text=payload.text,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/{account_id}/wabas/{waba_id}/query-phone-detail",
    summary="Query phone number detail",
    description="Query phone number details from Meta Graph API.",
    tags=["meta-accounts"],
)
async def query_phone_detail(
    account_id: str,
    waba_id: str,
    payload: QueryPhoneDetailRequest,
    meta_account_registry: MetaAccountRegistry = Depends(get_meta_account_registry),
    actor: RequestActor = Depends(require_permission("meta.edit")),
) -> dict[str, object]:
    actor.require_account_access(account_id)
    try:
        return await meta_account_registry.query_phone_detail(
            account_id=account_id,
            waba_id=waba_id,
            phone_id=payload.phone_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/{account_id}/wabas/{waba_id}/query-business-profile",
    summary="Query business profile",
    description="Query WhatsApp business profile from Meta Graph API.",
    tags=["meta-accounts"],
)
async def query_business_profile(
    account_id: str,
    waba_id: str,
    payload: QueryPhoneDetailRequest,
    meta_account_registry: MetaAccountRegistry = Depends(get_meta_account_registry),
    actor: RequestActor = Depends(require_permission("meta.edit")),
) -> dict[str, object]:
    actor.require_account_access(account_id)
    try:
        return await meta_account_registry.query_business_profile(
            account_id=account_id,
            waba_id=waba_id,
            phone_id=payload.phone_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/global-webhook-config",
    summary="Get global webhook config",
    description="Get the global default webhook callback URL and verify token.",
    tags=["meta-accounts"],
)
async def get_global_webhook_config(
    actor: RequestActor = Depends(require_permission("meta.view")),
) -> GlobalWebhookConfigResponse:
    settings = get_settings()
    return GlobalWebhookConfigResponse(
        callback_url=settings.meta_global_webhook_callback_url,
        verify_token=settings.meta_global_webhook_verify_token,
    )


@router.put(
    "/global-webhook-config",
    summary="Update global webhook config",
    description="Update the global default webhook callback URL and verify token.",
    tags=["meta-accounts"],
)
async def update_global_webhook_config(
    payload: GlobalWebhookConfigUpdateRequest,
    actor: RequestActor = Depends(require_permission("meta.webhook")),
) -> GlobalWebhookConfigResponse:
    settings = get_settings()
    settings.meta_global_webhook_callback_url = payload.callback_url
    if payload.verify_token is not None:
        settings.meta_global_webhook_verify_token = payload.verify_token
    return GlobalWebhookConfigResponse(
        callback_url=settings.meta_global_webhook_callback_url,
        verify_token=settings.meta_global_webhook_verify_token,
    )
