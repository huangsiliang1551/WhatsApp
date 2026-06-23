from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from pydantic import ValidationError

from app.api.deps import (
    get_db_session,
    get_media_asset_service,
    get_meta_account_registry,
    get_queue_service,
    get_runtime_state_service,
    get_template_service,
    get_translation_service,
)
from app.core.metrics import (
    business_inbound_messages_total,
    message_processing_failures_total,
    whatsapp_webhook_signature_failures_total,
    whatsapp_webhook_signature_failures_scoped_total,
    whatsapp_webhook_messages_scoped_total,
    whatsapp_webhook_messages_total,
    whatsapp_webhook_phone_scope_rejections_total,
    whatsapp_webhook_phone_number_updates_total,
    whatsapp_webhook_status_updates_scoped_total,
    whatsapp_webhook_status_updates_total,
    whatsapp_webhook_template_updates_total,
)
from app.core.settings import Settings, get_settings
from app.providers.messaging.whatsapp_provider import WhatsAppProvider
from app.schemas.whatsapp_webhook import WhatsAppWebhookPayload
from app.services.chat import process_inbound_message
from app.services.media_asset_service import MediaAssetService
from app.services.media_message_processor import MediaMessageProcessor
from app.services.meta_account_registry import (
    MetaAccountConflictError,
    MetaAccountRegistry,
    WebhookAuthContext,
)
from app.services.queue_service import QueueService
from app.services.runtime_state import RuntimeStateStore
from app.services.template_service import TemplateService
from app.services.translation_service import TranslationService
from sqlalchemy.orm import Session

import structlog

router = APIRouter(prefix="/webhooks/whatsapp", tags=["webhooks"])

TEMPLATE_WEBHOOK_FIELDS = {
    "message_template_status_update",
    "message_template_quality_update",
}
PHONE_NUMBER_WEBHOOK_FIELDS = {
    "phone_number_quality_update",
    "phone_number_name_update",
    "phone_number_status_update",
}

# BE2-007: Message dedup - module-level processed message ID tracking
_deduplicated_message_ids: set[str] = set()
logger = structlog.get_logger()


def _reset_message_dedup() -> None:
    """Reset dedup state (used in tests)."""
    _deduplicated_message_ids.clear()


def _is_message_deduplicated(message_id: str) -> bool:
    """Check if message_id has already been processed (dedup)."""
    if not message_id:
        return False
    return message_id in _deduplicated_message_ids


def _mark_message_processed(message_id: str) -> None:
    """Mark message_id as processed."""
    if message_id:
        _deduplicated_message_ids.add(message_id)


def _is_whatsapp_provider_mode(settings: Settings) -> bool:
    return settings.messaging_provider.strip().lower() == "whatsapp"


async def _assert_whatsapp_webhook_delivery_ready(
    *,
    settings: Settings,
    meta_account_registry: MetaAccountRegistry,
    runtime_state_store: RuntimeStateStore,
    account_id: str,
    waba_id: str,
) -> None:
    if not _is_whatsapp_provider_mode(settings):
        return

    scoped_accounts = await meta_account_registry.list_accounts(
        account_id=account_id,
        waba_id=waba_id,
    )
    if not scoped_accounts:
        raise HTTPException(status_code=404, detail=f"WABA '{waba_id}' was not found.")

    scoped_account = scoped_accounts[0]
    if scoped_account.ready_for_webhook_delivery:
        return

    verification_status = scoped_account.webhook_verification_status or "pending"
    subscription_status = scoped_account.webhook_subscription_status or "missing"
    blocking_reasons = list(scoped_account.blocking_reasons)
    primary_reason = blocking_reasons[0] if blocking_reasons else "webhook_delivery_not_ready"
    error_message = (
        f"webhook_verification_{verification_status}"
        if verification_status != "verified"
        else primary_reason
    )
    meta_account_registry.record_webhook_runtime_result(
        account_id=account_id,
        waba_id=waba_id,
        status="verification_pending",
        error_message=error_message,
    )
    runtime_state_store.add_audit_log(
        account_id=account_id,
        actor_type="system",
        actor_id=None,
        action="meta_webhook_delivery_blocked",
        target_type="waba_account",
        target_id=waba_id,
        payload={
            "reason": primary_reason,
            "webhook_verification_status": verification_status,
            "webhook_subscription_status": subscription_status,
            "ready_for_webhook_delivery": scoped_account.ready_for_webhook_delivery,
            "blocking_reasons": blocking_reasons,
        },
    )
    runtime_state_store.commit()
    raise HTTPException(
        status_code=412,
        detail=(
            f"Webhook delivery is not ready for WABA '{waba_id}': "
            f"webhook_verification_status='{verification_status}', "
            f"webhook_subscription_status='{subscription_status}', "
            f"ready_for_webhook_delivery={scoped_account.ready_for_webhook_delivery}, "
            f"blocking_reasons={blocking_reasons}. "
            "With MESSAGING_PROVIDER=whatsapp, signed webhook delivery remains blocked until "
            "the WABA is ready for webhook delivery."
        ),
    )


def _record_webhook_phone_scope_rejection(
    *,
    runtime_state_store: RuntimeStateStore,
    account_id: str,
    waba_id: str,
    phone_number_id: str | None,
    item_type: str,
    external_id: str | None,
    reason: str,
) -> None:
    whatsapp_webhook_phone_scope_rejections_total.labels(
        account_id=account_id,
        waba_id=waba_id,
        phone_number_id=phone_number_id or "unknown",
        item_type=item_type,
        reason=reason,
    ).inc()
    runtime_state_store.add_audit_log(
        account_id=account_id,
        actor_type="system",
        actor_id=None,
        action="meta_webhook_phone_scope_rejected",
        target_type="waba_account",
        target_id=waba_id,
        payload={
            "phone_number_id": phone_number_id,
            "item_type": item_type,
            "external_id": external_id,
            "reason": reason,
        },
    )


def _record_webhook_signature_failure(
    *,
    meta_account_registry: MetaAccountRegistry,
    runtime_state_store: RuntimeStateStore,
    account_id: str,
    waba_id: str,
    signature_header: str | None,
) -> None:
    meta_account_registry.record_webhook_runtime_result(
        account_id=account_id,
        waba_id=waba_id,
        status="signature_failed",
        error_message="invalid_signature",
        signature_failed=True,
    )
    whatsapp_webhook_signature_failures_total.inc()
    whatsapp_webhook_signature_failures_scoped_total.labels(
        account_id=account_id,
        waba_id=waba_id,
    ).inc()
    message_processing_failures_total.labels(
        provider=WhatsAppProvider.provider_name,
        stage="webhook_signature",
    ).inc()
    runtime_state_store.add_audit_log(
        account_id=account_id,
        actor_type="system",
        actor_id=None,
        action="meta_webhook_signature_failed",
        target_type="waba_account",
        target_id=waba_id,
        payload={"signature_header_present": signature_header is not None},
    )


async def _process_template_webhook_updates(
    *,
    payload: WhatsAppWebhookPayload,
    account_id: str,
    waba_id: str,
    runtime_state_store: RuntimeStateStore,
    template_service: TemplateService,
) -> dict[str, int]:
    accepted = 0
    matched = 0
    skipped = 0
    for entry in payload.entry:
        for change in entry.changes:
            if change.field not in TEMPLATE_WEBHOOK_FIELDS:
                continue
            accepted += 1
            value = change.value
            status = value.event if change.field == "message_template_status_update" else None
            raw_payload = value.model_dump(mode="json", exclude_none=True)
            updated_template = await template_service.apply_template_webhook_update(
                account_id=account_id,
                waba_id=waba_id,
                meta_template_id=value.message_template_id,
                name=value.message_template_name,
                language=value.message_template_language,
                status=status,
                rejected_reason=value.reason,
                quality_score=value.new_quality_score,
                event_type=change.field,
                raw_payload=raw_payload,
            )
            if updated_template is None:
                skipped += 1
                whatsapp_webhook_template_updates_total.labels(
                    account_id=account_id,
                    waba_id=waba_id,
                    event_type=change.field,
                    outcome="skipped",
                ).inc()
                runtime_state_store.add_audit_log(
                    account_id=account_id,
                    actor_type="system",
                    actor_id=None,
                    action="template_webhook_update_unmatched",
                    target_type="waba_account",
                    target_id=waba_id,
                    payload={
                        "event_type": change.field,
                        "meta_template_id": value.message_template_id,
                        "name": value.message_template_name,
                        "language": value.message_template_language,
                        "status": status,
                        "quality_score": value.new_quality_score,
                    },
                )
                continue
            matched += 1
            whatsapp_webhook_template_updates_total.labels(
                account_id=account_id,
                waba_id=waba_id,
                event_type=change.field,
                outcome="matched",
            ).inc()
    return {
        "accepted_template_updates": accepted,
        "matched_template_updates": matched,
        "skipped_template_updates": skipped,
    }


async def _process_phone_number_webhook_updates(
    *,
    payload: WhatsAppWebhookPayload,
    account_id: str,
    waba_id: str,
    runtime_state_store: RuntimeStateStore,
    meta_account_registry: MetaAccountRegistry,
) -> dict[str, int]:
    accepted = 0
    matched = 0
    skipped = 0
    for entry in payload.entry:
        for change in entry.changes:
            if change.field not in PHONE_NUMBER_WEBHOOK_FIELDS:
                continue
            accepted += 1
            value = change.value
            raw_payload = value.model_dump(mode="json", exclude_none=True)
            phone_number_id = _pick_string(
                value.phone_number_id,
                raw_payload.get("phone_number_id"),
                raw_payload.get("phone_number"),
            )
            display_phone_number = _pick_string(
                value.display_phone_number,
                raw_payload.get("display_phone_number"),
            )
            quality_rating = _pick_string(
                raw_payload.get("new_quality_rating"),
                raw_payload.get("current_quality_rating"),
                raw_payload.get("quality_rating"),
                raw_payload.get("quality_score"),
                value.new_quality_score,
            )
            previous_quality_rating = _pick_string(
                raw_payload.get("previous_quality_rating"),
                value.previous_quality_score,
            )
            messaging_limit_tier = _pick_string(
                value.current_limit,
                raw_payload.get("messaging_limit_tier"),
                raw_payload.get("current_limit"),
            )
            updated_phone = await meta_account_registry.apply_phone_number_webhook_update(
                account_id=account_id,
                waba_id=waba_id,
                phone_number_id=phone_number_id,
                display_phone_number=display_phone_number,
                event_type=change.field,
                event=value.event,
                quality_rating=quality_rating,
                previous_quality_rating=previous_quality_rating,
                messaging_limit_tier=messaging_limit_tier,
                max_daily_conversations_per_business=_pick_int(
                    value.max_daily_conversations_per_business,
                    raw_payload.get("max_daily_conversations_per_business"),
                ),
                is_registered=_pick_bool(raw_payload.get("is_registered")),
                is_active=_pick_bool(raw_payload.get("is_active")),
                raw_payload=raw_payload,
            )
            if updated_phone is None:
                skipped += 1
                whatsapp_webhook_phone_number_updates_total.labels(
                    account_id=account_id,
                    waba_id=waba_id,
                    phone_number_id=phone_number_id or "unknown",
                    event_type=change.field,
                    outcome="skipped",
                ).inc()
                runtime_state_store.add_audit_log(
                    account_id=account_id,
                    actor_type="system",
                    actor_id=None,
                    action="whatsapp_phone_number_webhook_unmatched",
                    target_type="waba_account",
                    target_id=waba_id,
                    payload={
                        "event_type": change.field,
                        "event": value.event,
                        "phone_number_id": phone_number_id,
                        "display_phone_number": display_phone_number,
                        "reason": "phone_number_not_found_in_waba_scope",
                        "raw_payload": raw_payload,
                    },
                )
                continue
            matched += 1
            whatsapp_webhook_phone_number_updates_total.labels(
                account_id=account_id,
                waba_id=waba_id,
                phone_number_id=updated_phone.phone_number_id,
                event_type=change.field,
                outcome="matched",
            ).inc()
    return {
        "accepted_phone_number_updates": accepted,
        "matched_phone_number_updates": matched,
        "skipped_phone_number_updates": skipped,
    }


def _pick_string(*values: object) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, int):
            return str(value)
    return None


def _pick_int(*values: object) -> int | None:
    for value in values:
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.strip().isdigit():
            return int(value.strip())
    return None


def _pick_bool(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "registered", "active"}:
            return True
        if normalized in {"false", "0", "no", "unregistered", "inactive"}:
            return False
    return None


def _build_root_webhook_scope_failure(
    *,
    waba_id: str,
    account_id: str | None,
    exc: Exception,
) -> dict[str, object]:
    if isinstance(exc, HTTPException):
        return {
            "account_id": account_id,
            "waba_id": waba_id,
            "status_code": exc.status_code,
            "detail": exc.detail,
        }

    return {
        "account_id": account_id,
        "waba_id": waba_id,
        "status_code": 500,
        "detail": "Scoped WhatsApp webhook processing failed.",
        "error_type": type(exc).__name__,
    }


def _record_root_webhook_scope_failure(
    *,
    runtime_state_store: RuntimeStateStore,
    waba_id: str,
    account_id: str | None,
    exc: Exception,
    source_stage: str,
) -> dict[str, object]:
    failure = _build_root_webhook_scope_failure(
        waba_id=waba_id,
        account_id=account_id,
        exc=exc,
    )
    payload: dict[str, object] = {
        "source_stage": source_stage,
        "status_code": failure["status_code"],
        "detail": failure["detail"],
        "account_id_present": account_id is not None,
    }
    error_type = failure.get("error_type")
    if isinstance(error_type, str):
        payload["error_type"] = error_type
    runtime_state_store.add_audit_log(
        account_id=account_id,
        actor_type="system",
        actor_id=None,
        action="meta_webhook_root_scope_failed",
        target_type="waba_account",
        target_id=waba_id,
        payload=payload,
    )
    return failure


def _record_root_webhook_payload_rejected(
    *,
    runtime_state_store: RuntimeStateStore,
    reason: str,
    object_name: str | None,
    entry_count: int | None,
    validation_error_count: int | None = None,
) -> None:
    payload: dict[str, object] = {
        "reason": reason,
        "object": object_name,
        "entry_count": entry_count,
    }
    if validation_error_count is not None:
        payload["validation_error_count"] = validation_error_count
    runtime_state_store.add_audit_log(
        account_id=None,
        actor_type="system",
        actor_id=None,
        action="meta_webhook_root_payload_rejected",
        target_type="webhook_payload",
        target_id=None,
        payload=payload,
    )


def _validation_error_details(exc: ValidationError) -> list[dict[str, object]]:
    return exc.errors(include_input=False)


def _sum_root_webhook_scope_metric(
    scoped_results: list[dict[str, object]],
    key: str,
) -> int:
    return sum(int(result.get(key, 0)) for result in scoped_results)


async def _verify_whatsapp_webhook_for_scope(
    *,
    account_id: str,
    waba_id: str,
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
    settings: Settings = Depends(get_settings),
    meta_account_registry: MetaAccountRegistry = Depends(get_meta_account_registry),
    runtime_state_store: RuntimeStateStore = Depends(get_runtime_state_service),
) -> PlainTextResponse:
    try:
        auth_context = await meta_account_registry.get_webhook_auth_context(
            account_id=account_id,
            waba_id=waba_id,
        )
    except (LookupError, ValueError) as exc:
        runtime_state_store.add_audit_log(
            account_id=account_id,
            actor_type="system",
            actor_id=None,
            action="meta_webhook_verification_scope_missing",
            target_type="waba_account",
            target_id=waba_id,
            payload={
                "mode": hub_mode,
                "reason": "waba_scope_not_found",
                "error": str(exc),
                "verify_token_present": bool(hub_verify_token.strip()),
            },
        )
        runtime_state_store.commit()
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    expected_verify_token = auth_context.verify_token or (
        "" if _is_whatsapp_provider_mode(settings) else settings.wa_verify_token
    )
    if not expected_verify_token:
        meta_account_registry.record_webhook_verification_result(
            account_id=account_id,
            waba_id=waba_id,
            status="unavailable",
            error_message="missing_verify_token",
        )
        runtime_state_store.add_audit_log(
            account_id=account_id,
            actor_type="system",
            actor_id=None,
            action="meta_webhook_verification_unavailable",
            target_type="waba_account",
            target_id=waba_id,
            payload={"reason": "missing_verify_token"},
        )
        runtime_state_store.commit()
        raise HTTPException(
            status_code=503,
            detail="Webhook verify token is not configured for this WABA.",
        )

    provider = WhatsAppProvider(timeout_seconds=settings.messaging_request_timeout_seconds)
    try:
        challenge = provider.verify_challenge(
            mode=hub_mode,
            verify_token=hub_verify_token,
            challenge=hub_challenge,
            expected_verify_token=expected_verify_token,
        )
    except ValueError as exc:
        meta_account_registry.record_webhook_verification_result(
            account_id=account_id,
            waba_id=waba_id,
            status="failed",
            error_message=str(exc),
        )
        runtime_state_store.add_audit_log(
            account_id=account_id,
            actor_type="system",
            actor_id=None,
            action="meta_webhook_verification_failed",
            target_type="waba_account",
            target_id=waba_id,
            payload={"mode": hub_mode, "error": str(exc)},
        )
        runtime_state_store.commit()
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    meta_account_registry.record_webhook_verification_result(
        account_id=account_id,
        waba_id=waba_id,
        status="verified",
        error_message=None,
    )
    runtime_state_store.add_audit_log(
        account_id=account_id,
        actor_type="system",
        actor_id=None,
        action="meta_webhook_verification_succeeded",
        target_type="waba_account",
        target_id=waba_id,
        payload={"mode": hub_mode},
    )
    runtime_state_store.commit()

    return PlainTextResponse(challenge)


@router.get(
    "",
    summary="Verify webhook (root)",
    description="Verify WhatsApp webhook by resolving verify token to a WABA.",
    tags=["webhooks"],
)
async def verify_whatsapp_webhook_root(
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
    settings: Settings = Depends(get_settings),
    meta_account_registry: MetaAccountRegistry = Depends(get_meta_account_registry),
    runtime_state_store: RuntimeStateStore = Depends(get_runtime_state_service),
) -> PlainTextResponse:
    try:
        auth_context = await meta_account_registry.resolve_webhook_auth_context_by_verify_token(
            hub_verify_token
        )
    except LookupError as exc:
        runtime_state_store.add_audit_log(
            account_id=None,
            actor_type="system",
            actor_id=None,
            action="meta_webhook_root_verify_token_unmatched",
            target_type="waba_account",
            target_id=None,
            payload={
                "reason": "no_matching_waba",
                "verify_token_present": True,
            },
        )
        runtime_state_store.commit()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except MetaAccountConflictError as exc:
        conflicting_auth_contexts = await meta_account_registry.list_webhook_auth_contexts_by_verify_token(
            hub_verify_token
        )
        matching_waba_count = len(conflicting_auth_contexts)
        for auth_context in conflicting_auth_contexts:
            runtime_state_store.add_audit_log(
                account_id=auth_context.account_id,
                actor_type="system",
                actor_id=None,
                action="meta_webhook_root_verify_token_conflict",
                target_type="waba_account",
                target_id=auth_context.waba_id,
                payload={
                    "reason": "shared_verify_token",
                    "verify_token_present": True,
                    "matching_waba_count": matching_waba_count,
                },
            )
            runtime_state_store.commit()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        runtime_state_store.add_audit_log(
            account_id=None,
            actor_type="system",
            actor_id=None,
            action="meta_webhook_root_verify_token_invalid",
            target_type="waba_account",
            target_id=None,
            payload={
                "reason": "invalid_verify_token",
                "verify_token_present": True,
            },
        )
        runtime_state_store.commit()
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return await _verify_whatsapp_webhook_for_scope(
        account_id=auth_context.account_id,
        waba_id=auth_context.waba_id,
        hub_mode=hub_mode,
        hub_verify_token=hub_verify_token,
        hub_challenge=hub_challenge,
        settings=settings,
        meta_account_registry=meta_account_registry,
        runtime_state_store=runtime_state_store,
    )


@router.get(
    "/{account_id}/wabas/{waba_id}",
    summary="Verify webhook (scoped)",
    description="Verify WhatsApp webhook for a specific account and WABA.",
    tags=["webhooks"],
)
async def verify_whatsapp_webhook(
    account_id: str,
    waba_id: str,
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
    settings: Settings = Depends(get_settings),
    meta_account_registry: MetaAccountRegistry = Depends(get_meta_account_registry),
    runtime_state_store: RuntimeStateStore = Depends(get_runtime_state_service),
) -> PlainTextResponse:
    return await _verify_whatsapp_webhook_for_scope(
        account_id=account_id,
        waba_id=waba_id,
        hub_mode=hub_mode,
        hub_verify_token=hub_verify_token,
        hub_challenge=hub_challenge,
        settings=settings,
        meta_account_registry=meta_account_registry,
        runtime_state_store=runtime_state_store,
    )


async def _receive_whatsapp_webhook_for_scope(
    *,
    raw_body: bytes,
    signature_header: str | None,
    account_id: str,
    waba_id: str,
    settings: Settings,
    meta_account_registry: MetaAccountRegistry,
    runtime_state_store: RuntimeStateStore,
    translation_service: TranslationService,
    queue_service: QueueService,
    template_service: TemplateService,
    session: Session,
    media_asset_service: MediaAssetService,
    auth_context: WebhookAuthContext | None = None,
    payload: WhatsAppWebhookPayload | None = None,
    signature_verified: bool = False,
) -> dict[str, object]:
    if auth_context is None:
        try:
            auth_context = await meta_account_registry.get_webhook_auth_context(
                account_id=account_id,
                waba_id=waba_id,
            )
        except (LookupError, ValueError) as exc:
            runtime_state_store.add_audit_log(
                account_id=account_id,
                actor_type="system",
                actor_id=None,
                action="meta_webhook_receive_scope_missing",
                target_type="waba_account",
                target_id=waba_id,
                payload={
                    "reason": "waba_scope_not_found",
                    "error": str(exc),
                    "signature_header_present": signature_header is not None,
                },
            )
            runtime_state_store.commit()
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    provider = WhatsAppProvider(timeout_seconds=settings.messaging_request_timeout_seconds)
    app_secret = auth_context.app_secret if auth_context is not None else None

    # Check for missing app_secret before delivery readiness (even if signature is pre-verified)
    if _is_whatsapp_provider_mode(settings) and auth_context is not None and not app_secret:
        meta_account_registry.record_webhook_runtime_result(
            account_id=account_id,
            waba_id=waba_id,
            status="verification_pending",
            error_message="missing_app_secret",
        )
        runtime_state_store.add_audit_log(
            account_id=account_id,
            actor_type="system",
            actor_id=None,
            action="meta_webhook_signature_unavailable",
            target_type="waba_account",
            target_id=waba_id,
            payload={"reason": "missing_app_secret"},
        )
        runtime_state_store.commit()
        raise HTTPException(
            status_code=503,
            detail="Webhook app secret is not configured for this WABA.",
        )

    if not _is_whatsapp_provider_mode(settings):
        signature_verified = True
    elif not signature_verified:
        signature_header = signature_header or ""
        if app_secret:
            try:
                signature_verified = provider.verify_signature(
                    signature_header=signature_header,
                    app_secret=app_secret,
                    body=raw_body,
                )
            except Exception:
                logger.exception("webhook_signature_verification_exception")
        if not app_secret:
            meta_account_registry.record_webhook_runtime_result(
                account_id=account_id,
                waba_id=waba_id,
                status="signature_unavailable",
                error_message="missing_app_secret",
            )
            runtime_state_store.add_audit_log(
                account_id=account_id,
                actor_type="system",
                actor_id=None,
                action="meta_webhook_receive_app_secret_missing",
                target_type="waba_account",
                target_id=waba_id,
                payload={
                    "reason": "missing_app_secret",
                    "signature_header_present": bool(signature_header),
                },
            )
            runtime_state_store.commit()
            raise HTTPException(
                status_code=503,
                detail="Webhook app secret is not configured for this WABA.",
            )
        if app_secret and not signature_verified:
            signature_verified = provider.verify_signature(
                signature_header=signature_header,
                app_secret=app_secret,
                body=raw_body,
            )
            if not signature_verified:
                _record_webhook_signature_failure(
                    meta_account_registry=meta_account_registry,
                    runtime_state_store=runtime_state_store,
                    account_id=account_id,
                    waba_id=waba_id,
                    signature_header=signature_header,
                )
                runtime_state_store.commit()
                raise HTTPException(status_code=403, detail="Invalid WhatsApp webhook signature.")

    await _assert_whatsapp_webhook_delivery_ready(
        settings=settings,
        meta_account_registry=meta_account_registry,
        runtime_state_store=runtime_state_store,
        account_id=account_id,
        waba_id=waba_id,
    )

    if payload is None:
        try:
            payload = WhatsAppWebhookPayload.model_validate_json(raw_body)
        except ValidationError as exc:
            details = _validation_error_details(exc)
            meta_account_registry.record_webhook_runtime_result(
                account_id=account_id,
                waba_id=waba_id,
                status="payload_invalid",
                error_message="payload_validation_failed",
            )
            runtime_state_store.add_audit_log(
                account_id=account_id,
                actor_type="system",
                actor_id=None,
                action="meta_webhook_receive_payload_invalid",
                target_type="waba_account",
                target_id=waba_id,
                payload={
                    "reason": "invalid_payload",
                    "validation_error_count": len(details),
                },
            )
            runtime_state_store.commit()
            raise HTTPException(status_code=422, detail=details) from exc

    if payload.object != "whatsapp_business_account":
        meta_account_registry.record_webhook_runtime_result(
            account_id=account_id,
            waba_id=waba_id,
            status="payload_invalid",
            error_message="unsupported_webhook_object",
        )
        runtime_state_store.add_audit_log(
            account_id=account_id,
            actor_type="system",
            actor_id=None,
            action="meta_webhook_receive_payload_invalid",
            target_type="waba_account",
            target_id=waba_id,
            payload={
                "reason": "unsupported_object",
                "object": payload.object,
                "entry_count": len(payload.entry),
            },
        )
        runtime_state_store.commit()
        raise HTTPException(status_code=422, detail="Unsupported webhook object.")

    if not payload.entry:
        meta_account_registry.record_webhook_runtime_result(
            account_id=account_id,
            waba_id=waba_id,
            status="payload_invalid",
            error_message="missing_waba_entry",
        )
        runtime_state_store.add_audit_log(
            account_id=account_id,
            actor_type="system",
            actor_id=None,
            action="meta_webhook_receive_payload_invalid",
            target_type="waba_account",
            target_id=waba_id,
            payload={
                "reason": "missing_waba_entry",
                "object": payload.object,
                "entry_count": len(payload.entry),
            },
        )
        runtime_state_store.commit()
        raise HTTPException(status_code=422, detail="Webhook payload entry is required.")

    if any(entry.id != waba_id for entry in payload.entry):
        payload_waba_id = next((entry.id for entry in payload.entry if entry.id != waba_id), None)
        meta_account_registry.record_webhook_runtime_result(
            account_id=account_id,
            waba_id=waba_id,
            status="payload_invalid",
            error_message="payload_waba_route_mismatch",
        )
        runtime_state_store.add_audit_log(
            account_id=account_id,
            actor_type="system",
            actor_id=None,
            action="meta_webhook_receive_payload_invalid",
            target_type="waba_account",
            target_id=waba_id,
            payload={
                "reason": "payload_waba_route_mismatch",
                "payload_waba_id": payload_waba_id,
                "route_waba_id": waba_id,
            },
        )
        runtime_state_store.commit()
        raise HTTPException(status_code=400, detail="Webhook payload WABA does not match route.")

    total_messages = sum(
        len(change.value.messages)
        for entry in payload.entry
        for change in entry.changes
        if change.field == "messages"
    )
    total_status_updates = sum(
        len(change.value.statuses)
        for entry in payload.entry
        for change in entry.changes
        if change.field == "messages"
    )
    normalized_messages = await provider.normalize_inbound(payload)
    normalized_status_updates = await provider.normalize_status_updates(payload)
    template_update_counts = await _process_template_webhook_updates(
        payload=payload,
        account_id=account_id,
        waba_id=waba_id,
        runtime_state_store=runtime_state_store,
        template_service=template_service,
    )
    phone_number_update_counts = await _process_phone_number_webhook_updates(
        payload=payload,
        account_id=account_id,
        waba_id=waba_id,
        runtime_state_store=runtime_state_store,
        meta_account_registry=meta_account_registry,
    )
    account = runtime_state_store.get_account_model(account_id)
    account_is_active = bool(account.is_active) if account is not None else True

    media_processor = MediaMessageProcessor(
        session=session,
        messaging_provider=provider,
        media_asset_service=media_asset_service,
    )

    results: list[dict[str, object]] = []
    rejected_phone_scope_messages = 0
    accepted_message_phone_counts: dict[str, int] = {}
    processing_failures = 0
    for normalized in normalized_messages:
        normalized.account_id = account_id
        normalized.waba_id = normalized.waba_id or waba_id
        scoped_phone_number = runtime_state_store.get_phone_number_in_scope(
            account_id=account_id,
            waba_id=normalized.waba_id,
            provider_phone_number_id=normalized.phone_number_id,
            include_inactive=True,
        )
        if not account_is_active:
            rejected_phone_scope_messages += 1
            business_inbound_messages_total.labels(
                provider=provider.provider_name,
                outcome="skipped",
            ).inc()
            message_processing_failures_total.labels(
                provider=provider.provider_name,
                stage="webhook_phone_scope",
            ).inc()
            _record_webhook_phone_scope_rejection(
                runtime_state_store=runtime_state_store,
                account_id=account_id,
                waba_id=waba_id,
                phone_number_id=normalized.phone_number_id,
                item_type="message",
                external_id=normalized.external_message_id,
                reason="account_inactive",
            )
            continue
        if scoped_phone_number is None:
            rejected_phone_scope_messages += 1
            business_inbound_messages_total.labels(
                provider=provider.provider_name,
                outcome="skipped",
            ).inc()
            message_processing_failures_total.labels(
                provider=provider.provider_name,
                stage="webhook_phone_scope",
            ).inc()
            _record_webhook_phone_scope_rejection(
                runtime_state_store=runtime_state_store,
                account_id=account_id,
                waba_id=waba_id,
                phone_number_id=normalized.phone_number_id,
                item_type="message",
                external_id=normalized.external_message_id,
                reason="phone_number_id_not_registered_for_account_waba",
            )
            continue
        if scoped_phone_number.waba_account is not None and not scoped_phone_number.waba_account.is_active:
            rejected_phone_scope_messages += 1
            business_inbound_messages_total.labels(
                provider=provider.provider_name,
                outcome="skipped",
            ).inc()
            message_processing_failures_total.labels(
                provider=provider.provider_name,
                stage="webhook_phone_scope",
            ).inc()
            _record_webhook_phone_scope_rejection(
                runtime_state_store=runtime_state_store,
                account_id=account_id,
                waba_id=waba_id,
                phone_number_id=normalized.phone_number_id,
                item_type="message",
                external_id=normalized.external_message_id,
                reason="waba_inactive",
            )
            continue
        if not scoped_phone_number.is_active:
            rejected_phone_scope_messages += 1
            business_inbound_messages_total.labels(
                provider=provider.provider_name,
                outcome="skipped",
            ).inc()
            message_processing_failures_total.labels(
                provider=provider.provider_name,
                stage="webhook_phone_scope",
            ).inc()
            _record_webhook_phone_scope_rejection(
                runtime_state_store=runtime_state_store,
                account_id=account_id,
                waba_id=waba_id,
                phone_number_id=normalized.phone_number_id,
                item_type="message",
                external_id=normalized.external_message_id,
                reason="phone_number_inactive",
            )
            continue

        # BE2-007: Message dedup check
        message_id = normalized.external_message_id or ""
        if _is_message_deduplicated(message_id):
            logger.warning(
                "webhook_deduplicated_message_skipped",
                account_id=account_id,
                waba_id=waba_id,
                message_id=message_id,
            )
            continue
        _mark_message_processed(message_id)

        # BE2-009: Download and store inbound media
        await media_processor.process_inbound_media(normalized)

        try:
            results.append(
                await process_inbound_message(
                    normalized,
                    messaging_provider=provider,
                    requested_mode="ai",
                    settings=settings,
                    runtime_state_store=runtime_state_store,
                    translation_service=translation_service,
                    queue_service=queue_service,
                )
            )
            accepted_message_phone_counts[normalized.phone_number_id or "unknown"] = (
                accepted_message_phone_counts.get(normalized.phone_number_id or "unknown", 0) + 1
            )
        except Exception:
            processing_failures += 1
            message_processing_failures_total.labels(
                provider=provider.provider_name,
                stage="webhook_inbound",
            ).inc()
            logger.exception(
                "webhook_message_processing_failed",
                account_id=account_id,
                waba_id=waba_id,
                message_id=message_id,
            )
            raise

    matched_status_updates = 0
    accepted_status_updates = 0
    rejected_phone_scope_status_updates = 0
    accepted_status_phone_counts: dict[str, int] = {}
    for update in normalized_status_updates:
        update.account_id = account_id
        update.waba_id = update.waba_id or waba_id
        scoped_phone_number = (
            runtime_state_store.get_phone_number_in_scope(
                account_id=account_id,
                waba_id=update.waba_id,
                provider_phone_number_id=update.phone_number_id,
                include_inactive=True,
            )
            if update.phone_number_id is not None
            else None
        )
        if not account_is_active:
            rejected_phone_scope_status_updates += 1
            message_processing_failures_total.labels(
                provider=provider.provider_name,
                stage="webhook_phone_scope",
            ).inc()
            _record_webhook_phone_scope_rejection(
                runtime_state_store=runtime_state_store,
                account_id=account_id,
                waba_id=waba_id,
                phone_number_id=update.phone_number_id,
                item_type="status_update",
                external_id=update.provider_message_id,
                reason="account_inactive",
            )
            continue
        if update.phone_number_id is not None and scoped_phone_number is None:
            rejected_phone_scope_status_updates += 1
            message_processing_failures_total.labels(
                provider=provider.provider_name,
                stage="webhook_phone_scope",
            ).inc()
            _record_webhook_phone_scope_rejection(
                runtime_state_store=runtime_state_store,
                account_id=account_id,
                waba_id=waba_id,
                phone_number_id=update.phone_number_id,
                item_type="status_update",
                external_id=update.provider_message_id,
                reason="phone_number_id_not_registered_for_account_waba",
            )
            continue
        if update.phone_number_id is not None and scoped_phone_number is not None:
            if scoped_phone_number.waba_account is not None and not scoped_phone_number.waba_account.is_active:
                rejected_phone_scope_status_updates += 1
                message_processing_failures_total.labels(
                    provider=provider.provider_name,
                    stage="webhook_phone_scope",
                ).inc()
                _record_webhook_phone_scope_rejection(
                    runtime_state_store=runtime_state_store,
                    account_id=account_id,
                    waba_id=waba_id,
                    phone_number_id=update.phone_number_id,
                    item_type="status_update",
                    external_id=update.provider_message_id,
                    reason="waba_inactive",
                )
                continue
            if not scoped_phone_number.is_active:
                rejected_phone_scope_status_updates += 1
                message_processing_failures_total.labels(
                    provider=provider.provider_name,
                    stage="webhook_phone_scope",
                ).inc()
                _record_webhook_phone_scope_rejection(
                    runtime_state_store=runtime_state_store,
                    account_id=account_id,
                    waba_id=waba_id,
                    phone_number_id=update.phone_number_id,
                    item_type="status_update",
                    external_id=update.provider_message_id,
                    reason="phone_number_inactive",
                )
                continue

        try:
            matched = await runtime_state_store.record_provider_status_event(
                account_id=account_id,
                update=update,
            )
            accepted_status_updates += 1
            if matched:
                matched_status_updates += 1
            accepted_status_phone_counts[update.phone_number_id or "unknown"] = (
                accepted_status_phone_counts.get(update.phone_number_id or "unknown", 0) + 1
            )
        except Exception:
            message_processing_failures_total.labels(
                provider=provider.provider_name,
                stage="webhook_status",
            ).inc()
            logger.exception(
                "webhook_status_update_failed",
                account_id=account_id,
                waba_id=waba_id,
                provider_message_id=update.provider_message_id,
            )

    meta_account_registry.record_webhook_runtime_result(
        account_id=account_id,
        waba_id=waba_id,
        status="healthy",
        error_message=None,
        message_count=len(results),
        status_update_count=accepted_status_updates,
        management_event_count=(
            template_update_counts.get("accepted_template_updates", 0)
            + phone_number_update_counts.get("accepted_phone_number_updates", 0)
        ),
    )
    runtime_state_store.commit()

    whatsapp_webhook_messages_total.labels(
        provider=provider.provider_name,
        outcome="accepted",
    ).inc(len(results))
    whatsapp_webhook_status_updates_total.labels(
        provider=provider.provider_name,
        outcome="accepted",
    ).inc(accepted_status_updates)

    return {
        "account_id": account_id,
        "waba_id": waba_id,
        "provider": provider.provider_name,
        "signature_verified": signature_verified,
        "total_messages": total_messages,
        "total_status_updates": total_status_updates,
        "normalized_messages": len(normalized_messages),
        "normalized_status_updates": len(normalized_status_updates),
        "results": results,
        "accepted_messages": len(results),
        "skipped_messages": rejected_phone_scope_messages,
        "rejected_phone_scope_messages": rejected_phone_scope_messages,
        "processing_failures": processing_failures,
        "accepted_message_phone_counts": accepted_message_phone_counts,
        "accepted_status_updates": accepted_status_updates,
        "matched_status_updates": matched_status_updates,
        "unmatched_status_updates": accepted_status_updates - matched_status_updates,
        "rejected_phone_scope_status_updates": rejected_phone_scope_status_updates,
        "accepted_status_phone_counts": accepted_status_phone_counts,
        "accepted_template_updates": template_update_counts.get("accepted_template_updates", 0),
        "matched_template_updates": template_update_counts.get("matched_template_updates", 0),
        "skipped_template_updates": template_update_counts.get("skipped_template_updates", 0),
        "accepted_phone_number_updates": phone_number_update_counts.get("accepted_phone_number_updates", 0),
        "matched_phone_number_updates": phone_number_update_counts.get("matched_phone_number_updates", 0),
        "skipped_phone_number_updates": phone_number_update_counts.get("skipped_phone_number_updates", 0),
        **template_update_counts,
        **phone_number_update_counts,
    }



@router.post(
    "",
    summary="Receive webhook (root)",
    description="Receive WhatsApp webhook events, automatically routing to matching WABA scopes.",
    tags=["webhooks"],
)
async def receive_whatsapp_webhook_root(
    request: Request,
    settings: Settings = Depends(get_settings),
    meta_account_registry: MetaAccountRegistry = Depends(get_meta_account_registry),
    runtime_state_store: RuntimeStateStore = Depends(get_runtime_state_service),
    translation_service: TranslationService = Depends(get_translation_service),
    queue_service: QueueService = Depends(get_queue_service),
    template_service: TemplateService = Depends(get_template_service),
    session: Session = Depends(get_db_session),
    media_asset_service: MediaAssetService = Depends(get_media_asset_service),
) -> dict[str, object]:
    raw_body = await request.body()
    provider = WhatsAppProvider(timeout_seconds=settings.messaging_request_timeout_seconds)
    try:
        payload = WhatsAppWebhookPayload.model_validate_json(raw_body)
    except ValidationError as exc:
        details = _validation_error_details(exc)
        _record_root_webhook_payload_rejected(
            runtime_state_store=runtime_state_store,
            reason="invalid_payload",
            object_name=None,
            entry_count=None,
            validation_error_count=len(details),
        )
        runtime_state_store.commit()
        raise HTTPException(status_code=422, detail=details) from exc

    if payload.object != "whatsapp_business_account":
        _record_root_webhook_payload_rejected(
            runtime_state_store=runtime_state_store,
            reason="unsupported_object",
            object_name=payload.object,
            entry_count=len(payload.entry),
        )
        runtime_state_store.commit()
        raise HTTPException(status_code=422, detail="Unsupported webhook object.")

    waba_ids = {entry.id for entry in payload.entry}
    if not waba_ids:
        _record_root_webhook_payload_rejected(
            runtime_state_store=runtime_state_store,
            reason="missing_waba_entry",
            object_name=payload.object,
            entry_count=len(payload.entry),
        )
        runtime_state_store.commit()
        raise HTTPException(status_code=422, detail="Webhook payload entry is required.")

    # --- Resolve all WABA auth contexts ---
    resolved_auth_contexts: dict[str, WebhookAuthContext] = {}
    failed_scopes: list[dict[str, object]] = []
    for waba_id in waba_ids:
        try:
            auth_context = await meta_account_registry.resolve_webhook_auth_context(waba_id=waba_id)
            resolved_auth_contexts[waba_id] = auth_context
        except (LookupError, ValueError) as exc:
            failure = _record_root_webhook_scope_failure(
                runtime_state_store=runtime_state_store,
                waba_id=waba_id,
                account_id=None,
                exc=HTTPException(status_code=404, detail=str(exc)),
                source_stage="scope_resolution",
            )
            failed_scopes.append(failure)

    # --- app_secret conflict detection (must run even in non-whatsapp mode) ---
    signature_header = request.headers.get("X-Hub-Signature-256")
    unique_secrets = list({
        ctx.app_secret
        for ctx in resolved_auth_contexts.values()
        if ctx.app_secret
    })
    if len(unique_secrets) > 1:
        for waba_id, ctx in resolved_auth_contexts.items():
            runtime_state_store.add_audit_log(
                account_id=ctx.account_id,
                actor_type="system",
                actor_id=None,
                action="meta_webhook_root_app_secret_conflict",
                target_type="waba_account",
                target_id=waba_id,
                payload={
                    "reason": "multiple_app_secrets",
                    "root_entry_waba_ids": list(sorted(waba_ids)),
                    "resolved_waba_count": len(resolved_auth_contexts),
                    "app_secret_count": len(unique_secrets),
                    "signature_header_present": bool(signature_header),
                },
            )
            meta_account_registry.record_webhook_runtime_result(
                account_id=ctx.account_id,
                waba_id=waba_id,
                status="signature_failed",
                error_message="multiple_app_secrets",
            )
        runtime_state_store.commit()
        raise HTTPException(
            status_code=409,
            detail="Webhook payload references multiple app secrets. "
                   "Use the scoped WABA endpoint when accounts have different app secrets.",
        )

    # --- signature validation (whatsapp mode only) ---
    signature_verified = False
    if _is_whatsapp_provider_mode(settings):
        if unique_secrets:
            app_secret = unique_secrets[0]
            if signature_header:
                try:
                    signature_verified = provider.verify_signature(
                        signature_header=signature_header,
                        app_secret=app_secret,
                        body=raw_body,
                    )
                except Exception:
                    logger.exception("webhook_signature_verification_exception")
            if not signature_verified:
                for ctx in resolved_auth_contexts.values():
                    meta_account_registry.record_webhook_runtime_result(
                        account_id=ctx.account_id,
                        waba_id=ctx.waba_id,
                        status="signature_failed",
                        error_message="invalid_signature",
                    )
                runtime_state_store.commit()
                raise HTTPException(
                    status_code=403,
                    detail="Invalid WhatsApp webhook signature.",
                )
    else:
        signature_verified = True

    # --- Build per-WABA filtered payloads ---
    waba_entries_map: dict[str, list[object]] = {waba_id: [] for waba_id in waba_ids}
    for entry in payload.entry:
        waba_entries_map.setdefault(entry.id, []).append(entry)

    def _filtered_payload(waba_id: str) -> WhatsAppWebhookPayload:
        return WhatsAppWebhookPayload(
            object=payload.object,
            entry=waba_entries_map.get(waba_id, []),
        )

    # --- If a single WABA was entirely unresolved, raise the failure ---
    if len(waba_ids) == 1 and not resolved_auth_contexts and failed_scopes:
        runtime_state_store.commit()
        raise HTTPException(
            status_code=failed_scopes[0].get("status_code", 404),
            detail=failed_scopes[0].get("detail", "WABA not found."),
        )

    # --- Single WABA: delegate directly ---
    if len(waba_ids) == 1 and len(resolved_auth_contexts) == 1:
        _, auth_context = next(iter(resolved_auth_contexts.items()))
        try:
            scoped_result = await _receive_whatsapp_webhook_for_scope(
                raw_body=raw_body,
                signature_header=signature_header,
                account_id=auth_context.account_id,
                waba_id=auth_context.waba_id,
                settings=settings,
                meta_account_registry=meta_account_registry,
                runtime_state_store=runtime_state_store,
                translation_service=translation_service,
                queue_service=queue_service,
                template_service=template_service,
                session=session,
                media_asset_service=media_asset_service,
                auth_context=auth_context,
                payload=_filtered_payload(auth_context.waba_id),
                signature_verified=signature_verified,
            )
            return scoped_result
        except HTTPException as http_exc:
            _record_root_webhook_scope_failure(
                runtime_state_store=runtime_state_store,
                waba_id=auth_context.waba_id,
                account_id=auth_context.account_id,
                exc=http_exc,
                source_stage="scoped_processing",
            )
            runtime_state_store.commit()
            raise
        except Exception as exc:
            _record_root_webhook_scope_failure(
                runtime_state_store=runtime_state_store,
                waba_id=auth_context.waba_id,
                account_id=auth_context.account_id,
                exc=exc,
                source_stage="scoped_processing",
            )
            runtime_state_store.commit()
            raise

    # --- Multi-WABA: fan-out ---
    scoped_results: list[dict[str, object]] = []
    for waba_id in sorted(waba_ids):
        auth_context = resolved_auth_contexts.get(waba_id)
        if auth_context is None:
            continue
        if not waba_entries_map.get(waba_id):
            continue

        try:
            scoped_result = await _receive_whatsapp_webhook_for_scope(
                raw_body=raw_body,
                signature_header=signature_header,
                account_id=auth_context.account_id,
                waba_id=auth_context.waba_id,
                settings=settings,
                meta_account_registry=meta_account_registry,
                runtime_state_store=runtime_state_store,
                translation_service=translation_service,
                queue_service=queue_service,
                template_service=template_service,
                session=session,
                media_asset_service=media_asset_service,
                auth_context=auth_context,
                payload=_filtered_payload(waba_id),
                signature_verified=signature_verified,
            )
            scoped_results.append(scoped_result)
        except HTTPException as http_exc:
            failure = _record_root_webhook_scope_failure(
                runtime_state_store=runtime_state_store,
                waba_id=auth_context.waba_id,
                account_id=auth_context.account_id,
                exc=http_exc,
                source_stage="scoped_processing",
            )
            failed_scopes.append(failure)
        except Exception as exc:
            failure = _record_root_webhook_scope_failure(
                runtime_state_store=runtime_state_store,
                waba_id=auth_context.waba_id,
                account_id=auth_context.account_id,
                exc=exc,
                source_stage="scoped_processing",
            )
            failed_scopes.append(failure)

    runtime_state_store.commit()

    return {
        "provider": provider.provider_name,
        "waba_count": len(waba_ids),
        "successful_scope_count": len(scoped_results),
        "failed_scope_count": len(failed_scopes),
        "accepted_messages": _sum_root_webhook_scope_metric(scoped_results, "accepted_messages"),
        "skipped_messages": _sum_root_webhook_scope_metric(scoped_results, "skipped_messages"),
        "rejected_phone_scope_messages": _sum_root_webhook_scope_metric(scoped_results, "rejected_phone_scope_messages"),
        "scopes": scoped_results,
        "scope_failures": failed_scopes,
    }


@router.post(
    "/{account_id}/wabas/{waba_id}",
    summary="Receive webhook (scoped)",
    description="Receive WhatsApp webhook events for a specific account and WABA.",
    tags=["webhooks"],
)
async def receive_whatsapp_webhook(
    account_id: str,
    waba_id: str,
    request: Request,
    settings: Settings = Depends(get_settings),
    meta_account_registry: MetaAccountRegistry = Depends(get_meta_account_registry),
    runtime_state_store: RuntimeStateStore = Depends(get_runtime_state_service),
    translation_service: TranslationService = Depends(get_translation_service),
    queue_service: QueueService = Depends(get_queue_service),
    template_service: TemplateService = Depends(get_template_service),
    session: Session = Depends(get_db_session),
    media_asset_service: MediaAssetService = Depends(get_media_asset_service),
) -> dict[str, object]:
    raw_body = await request.body()
    return await _receive_whatsapp_webhook_for_scope(
        raw_body=raw_body,
        signature_header=request.headers.get("X-Hub-Signature-256"),
        account_id=account_id,
        waba_id=waba_id,
        settings=settings,
        meta_account_registry=meta_account_registry,
        runtime_state_store=runtime_state_store,
        translation_service=translation_service,
        queue_service=queue_service,
        template_service=template_service,
        session=session,
        media_asset_service=media_asset_service,
    )
