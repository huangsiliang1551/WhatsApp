from fastapi import APIRouter, Depends, HTTPException

import structlog

from app.api.deps import (
    get_runtime_state_service,
    get_whatsapp_analytics_service,
    require_permission,
)
from app.core.auth import RequestActor
from app.schemas.whatsapp_analytics import (
    WhatsAppStatsDailyRow,
    WhatsAppStatsDetailResponse,
    WhatsAppStatsRebuildResponse,
    WhatsAppStatsSummary,
)
from app.services.runtime_state import RuntimeStateStore
from app.services.whatsapp_analytics_service import WhatsAppAnalyticsService

router = APIRouter(prefix="/api/whatsapp/stats", tags=["whatsapp-analytics"])


def _require_existing_account(
    *,
    account_id: str | None,
    actor: RequestActor,
    runtime_state: RuntimeStateStore,
) -> None:
    if account_id is None:
        return
    actor.require_account_access(account_id)
    if runtime_state.get_account_model(account_id) is None:
        raise HTTPException(status_code=404, detail=f"Account '{account_id}' was not found.")


def _resolve_rebuild_audit_scope(
    *,
    account_id: str | None,
    waba_id: str | None,
    phone_number_id: str | None,
) -> tuple[str, str]:
    if phone_number_id:
        return phone_number_id, "phone_number"
    if waba_id:
        return waba_id, "waba"
    if account_id:
        return account_id, "account"
    return "all_accounts", "all_accounts"


@router.post(
    "/rebuild",
    summary="Rebuild WhatsApp stats",
    description="Rebuild WhatsApp analytics statistics for a date range.",
    tags=["whatsapp-analytics"],
)
async def rebuild_whatsapp_stats(
    account_id: str | None = None,
    waba_id: str | None = None,
    phone_number_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    analytics_service: WhatsAppAnalyticsService = Depends(get_whatsapp_analytics_service),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("reports.whatsapp")),
) -> WhatsAppStatsRebuildResponse:
    _require_existing_account(account_id=account_id, actor=actor, runtime_state=runtime_state)
    audit_target_id, audit_scope_type = _resolve_rebuild_audit_scope(
        account_id=account_id,
        waba_id=waba_id,
        phone_number_id=phone_number_id,
    )
    try:
        rebuilt_at = await analytics_service.rebuild_stats(
            account_id=account_id,
            waba_id=waba_id,
            phone_number_id=phone_number_id,
            date_from=date_from,
            date_to=date_to,
            allowed_account_ids=None if actor.is_super_admin else set(actor.account_ids),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    runtime_state.add_audit_log(
        account_id=account_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        action="whatsapp_stats_rebuilt",
        target_type="whatsapp_daily_stats",
        target_id=audit_target_id,
        payload={
            "scope_type": audit_scope_type,
            "waba_id": waba_id,
            "phone_number_id": phone_number_id,
            "date_from": date_from,
            "date_to": date_to,
        },
    )
    runtime_state.commit()
    return WhatsAppStatsRebuildResponse(
        account_id=account_id,
        waba_id=waba_id,
        phone_number_id=phone_number_id,
        date_from=date_from,
        date_to=date_to,
        rebuilt_at=rebuilt_at.isoformat(),
    )


@router.get(
    "/summary",
    summary="Get WhatsApp stats summary",
    description="Get aggregated WhatsApp usage statistics.",
    tags=["whatsapp-analytics"],
)
async def get_whatsapp_stats_summary(
    account_id: str | None = None,
    waba_id: str | None = None,
    phone_number_id: str | None = None,
    conversation_origin_type: str | None = None,
    conversation_category: str | None = None,
    pricing_model: str | None = None,
    billable: bool | None = None,
    hour_bucket: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    analytics_service: WhatsAppAnalyticsService = Depends(get_whatsapp_analytics_service),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("reports.whatsapp")),
) -> WhatsAppStatsSummary:
    _require_existing_account(account_id=account_id, actor=actor, runtime_state=runtime_state)
    try:
        return await analytics_service.get_summary(
            account_id=account_id,
            waba_id=waba_id,
            phone_number_id=phone_number_id,
            conversation_origin_type=conversation_origin_type,
            conversation_category=conversation_category,
            pricing_model=pricing_model,
            billable=billable,
            hour_bucket=hour_bucket,
            date_from=date_from,
            date_to=date_to,
            allowed_account_ids=None if actor.is_super_admin else set(actor.account_ids),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        # DB/Redis unavailable, return empty summary
        from app.schemas.whatsapp_analytics import WhatsAppStatsSummary

        return WhatsAppStatsSummary(
            stats_by_country={},
            stats_by_date={},
            country_totals={},
            date_totals={},
        )


@router.get(
    "/daily",
    summary="List WhatsApp daily stats",
    description="List daily WhatsApp usage statistics.",
    tags=["whatsapp-analytics"],
)
async def list_whatsapp_daily_stats(
    account_id: str | None = None,
    waba_id: str | None = None,
    phone_number_id: str | None = None,
    conversation_origin_type: str | None = None,
    conversation_category: str | None = None,
    pricing_model: str | None = None,
    billable: bool | None = None,
    hour_bucket: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    analytics_service: WhatsAppAnalyticsService = Depends(get_whatsapp_analytics_service),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("reports.whatsapp")),
) -> list[WhatsAppStatsDailyRow]:
    _require_existing_account(account_id=account_id, actor=actor, runtime_state=runtime_state)
    try:
        return await analytics_service.list_daily_stats(
            account_id=account_id,
            waba_id=waba_id,
            phone_number_id=phone_number_id,
            conversation_origin_type=conversation_origin_type,
            conversation_category=conversation_category,
            pricing_model=pricing_model,
            billable=billable,
            hour_bucket=hour_bucket,
            date_from=date_from,
            date_to=date_to,
            allowed_account_ids=None if actor.is_super_admin else set(actor.account_ids),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/detail",
    summary="Get WhatsApp stats detail",
    description="Get detailed WhatsApp analytics statistics.",
    tags=["whatsapp-analytics"],
)
async def get_whatsapp_stats_detail(
    account_id: str | None = None,
    waba_id: str | None = None,
    phone_number_id: str | None = None,
    conversation_origin_type: str | None = None,
    conversation_category: str | None = None,
    pricing_model: str | None = None,
    billable: bool | None = None,
    hour_bucket: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    analytics_service: WhatsAppAnalyticsService = Depends(get_whatsapp_analytics_service),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("reports.whatsapp")),
) -> WhatsAppStatsDetailResponse:
    _require_existing_account(account_id=account_id, actor=actor, runtime_state=runtime_state)
    try:
        return await analytics_service.get_detail(
            account_id=account_id,
            waba_id=waba_id,
            phone_number_id=phone_number_id,
            conversation_origin_type=conversation_origin_type,
            conversation_category=conversation_category,
            pricing_model=pricing_model,
            billable=billable,
            hour_bucket=hour_bucket,
            date_from=date_from,
            date_to=date_to,
            allowed_account_ids=None if actor.is_super_admin else set(actor.account_ids),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger = structlog.get_logger()
        logger.warning("whatsapp_stats_detail_fallback_empty", error=str(exc))
        return WhatsAppStatsDetailResponse(
            summary=WhatsAppStatsSummary(
                inbound_message_count=0,
                outbound_message_count=0,
                conversation_count=0,
                active_conversation_count=0,
                unique_customer_count=0,
            ),
            daily_rows=[],
            fact_rows=[],
        )
