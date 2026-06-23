from typing import Literal

from sqlalchemy.exc import IntegrityError

from app.core.metrics import (
    business_ai_replies_total,
    business_inbound_messages_total,
    business_outbound_messages_total,
    message_processing_failures_total,
    mock_inbound_messages_total,
)
from app.core.settings import Settings
from app.db.models import Message
from app.providers.factory import (
    get_ai_provider,
    get_ecommerce_provider,
)
from app.providers.messaging.mock_provider import MockMessagingProvider
from app.providers.messaging.base import MessagingProvider
from app.schemas.mock_message import MockInboundMessage, NormalizedMessage
from app.services.messaging_dispatch import build_outbound_dispatch_request
from app.services.ecommerce_service import EcommerceService
from app.services.queue_service import QueueService
from app.services.runtime_state import RuntimeStateStore
from app.services.support_intent_service import SupportIntentService
from app.services.support_intent_service import SupportIntentDecision
from app.services.support_knowledge_service import SupportKnowledgeService
from app.services.support_router import SupportRouter
from app.services.translation_service import TranslationService


async def _build_deduplicated_result(
    normalized: NormalizedMessage,
    existing: Message,
    runtime_state_store: RuntimeStateStore,
) -> dict[str, object]:
    """Build the standard "duplicate inbound ignored" response payload."""
    return {
        "inbound": normalized.model_dump(),
        "translation": {
            "source_language": None,
            "console_language": None,
            "console_text": normalized.text,
        },
        "account_id": normalized.account_id,
        "outbound": {
            "provider": None,
            "provider_message_id": None,
            "text": None,
            "delivery_mode": "duplicate_inbound_ignored",
        },
        "ai": {
            "provider": "none",
            "model": "none",
        },
        "queue": None,
        "runtime": await runtime_state_store.get_effective_ai_status(
            normalized.account_id,
            normalized.conversation_id,
        ),
        "intent": {
            "intent_name": None,
            "confidence": None,
            "handover_recommended": False,
            "handover_reason": None,
        },
        "deduplicated": True,
        "existing_message_id": existing.id,
    }


async def process_inbound_message(
    normalized: NormalizedMessage,
    *,
    messaging_provider: MessagingProvider,
    requested_mode: Literal["echo", "ai"],
    settings: Settings,
    runtime_state_store: RuntimeStateStore,
    translation_service: TranslationService,
    queue_service: QueueService,
    language_hint: str | None = None,
) -> dict[str, object]:
    if (
        isinstance(messaging_provider, MockMessagingProvider)
        and runtime_state_store.get_account_model(normalized.account_id) is None
    ):
        await runtime_state_store.ensure_account(
            account_id=normalized.account_id,
            display_name=normalized.account_id,
            provider_type="mock",
        )
    runtime_state_store.ensure_account_active(normalized.account_id)
    if normalized.phone_number_id:
        scoped_phone_number = runtime_state_store.get_phone_number_in_scope(
            account_id=normalized.account_id,
            waba_id=normalized.waba_id,
            provider_phone_number_id=normalized.phone_number_id,
            include_inactive=True,
        )
        if scoped_phone_number is not None:
            scoped_waba_id = _resolve_phone_number_waba_id(scoped_phone_number)
            if not normalized.waba_id and scoped_waba_id is not None:
                normalized.waba_id = scoped_waba_id
            if scoped_phone_number.waba_account is not None and not scoped_phone_number.waba_account.is_active:
                raise ValueError(
                    f"WABA '{scoped_waba_id or scoped_phone_number.waba_account.waba_id}' is inactive."
                )
            if not scoped_phone_number.is_active:
                raise ValueError(f"Phone number '{normalized.phone_number_id}' is inactive.")
    if normalized.external_message_id:
        duplicate_message = await runtime_state_store.get_message_model_by_provider_message_id(
            normalized.account_id,
            normalized.external_message_id,
        )
        if duplicate_message is not None:
            business_inbound_messages_total.labels(
                provider=messaging_provider.provider_name,
                outcome="duplicate",
            ).inc()
            return await _build_deduplicated_result(
                normalized, duplicate_message, runtime_state_store
            )
    ecommerce_service = EcommerceService(
        provider=get_ecommerce_provider(settings),
        runtime_state=runtime_state_store,
    )
    support_router = SupportRouter(
        ecommerce_service=ecommerce_service,
        translation_service=translation_service,
        support_knowledge_service=SupportKnowledgeService(runtime_state_store.session),
    )
    intent_service = SupportIntentService()
    has_meaningful_text = _normalized_message_has_meaningful_text(normalized)
    detected_language = (
        translation_service.detect_language(
            text=normalized.text,
            language_hint=language_hint,
        )
        if has_meaningful_text
        else (language_hint or "und")
    )
    intent_decision = (
        intent_service.classify(normalized.text)
        if has_meaningful_text
        else SupportIntentDecision(
            intent_name=f"{normalized.message_type}_requires_review",
            confidence=1.0,
            handover_recommended=True,
            handover_reason="non_text_message_requires_manual_review",
        )
    )
    await runtime_state_store.ensure_conversation(
        account_id=normalized.account_id,
        conversation_id=normalized.conversation_id,
        customer_id=normalized.user_id,
        customer_language=detected_language,
        customer_language_source="hint" if language_hint else "detected",
        provider_phone_number_id=normalized.phone_number_id,
    )
    try:
        await runtime_state_store.record_inbound_message(
            account_id=normalized.account_id,
            conversation_id=normalized.conversation_id,
            sender_id=normalized.user_id,
            text=normalized.text,
            language_code=detected_language,
            translated_text=None,
            translated_language_code=None,
            message_type=normalized.message_type,
            provider_message_id=normalized.external_message_id,
            payload={
                **normalized.model_dump(),
                "intent_name": intent_decision.intent_name,
                "intent_confidence": intent_decision.confidence,
                "handover_recommended": intent_decision.handover_recommended,
                "handover_reason": intent_decision.handover_reason,
            },
        )
    except IntegrityError:
        # Race condition: another worker inserted the same provider_message_id
        # between our pre-check and commit. The DB unique constraint on
        # ``messages.provider_message_id`` is the final authority. Roll back
        # and return the already-stored message as a deduplicated result.
        runtime_state_store.session.rollback()
        existing = await runtime_state_store.get_message_model_by_provider_message_id(
            normalized.account_id,
            normalized.external_message_id,
        )
        if existing is not None:
            business_inbound_messages_total.labels(
                provider=messaging_provider.provider_name,
                outcome="duplicate",
            ).inc()
            return await _build_deduplicated_result(
                normalized, existing, runtime_state_store
            )
        raise
    business_inbound_messages_total.labels(
        provider=messaging_provider.provider_name,
        outcome="accepted",
    ).inc()
    runtime_state_store.add_audit_log(
        account_id=normalized.account_id,
        actor_type="system",
        actor_id=None,
        action="support_intent_evaluated",
        target_type="conversation",
        target_id=normalized.conversation_id,
        payload={
            "intent_name": intent_decision.intent_name,
            "confidence": intent_decision.confidence,
            "handover_recommended": intent_decision.handover_recommended,
            "handover_reason": intent_decision.handover_reason,
            "waba_id": normalized.waba_id,
            "phone_number_id": normalized.phone_number_id,
        },
    )
    runtime_state_store.commit()
    effective_ai_status = await runtime_state_store.get_effective_ai_status(
        normalized.account_id,
        normalized.conversation_id,
    )

    queue_job: dict[str, object] | None = None
    route_decision = None
    dispatch_provider = messaging_provider.provider_name
    dispatch_provider_message_id: str | None = None

    if requested_mode == "ai" and effective_ai_status["effective_ai_enabled"]:
        if not has_meaningful_text:
            reply_text = None
            ai_provider_name = "media_router"
            ai_model = normalized.message_type
            delivery_mode = "handover_recommended"
            business_ai_replies_total.labels(
                provider="media_router",
                outcome="skipped_handover",
            ).inc()
            await runtime_state_store.record_queue_event(
                account_id=normalized.account_id,
                conversation_id=normalized.conversation_id,
                event_type="handover_recommended",
                payload={
                    "intent_name": intent_decision.intent_name,
                    "handover_reason": intent_decision.handover_reason,
                    "message_type": normalized.message_type,
                    "requires_manual_review": True,
                },
            )
        else:
            route_decision = await support_router.resolve(
                account_id=normalized.account_id,
                customer_language=detected_language,
                user_message=normalized.text,
            )
            if route_decision is not None:
                reply_text = route_decision.reply_text
                ai_provider_name = "rule_router"
                ai_model = route_decision.route_name
                delivery_mode = "rule_auto_reply"
                business_ai_replies_total.labels(provider="rule_router", outcome="routed").inc()
            elif intent_decision.handover_recommended:
                reply_text = None
                ai_provider_name = "intent_router"
                ai_model = intent_decision.intent_name
                delivery_mode = "handover_recommended"
                business_ai_replies_total.labels(
                    provider="intent_router",
                    outcome="skipped_handover",
                ).inc()
                await runtime_state_store.record_queue_event(
                    account_id=normalized.account_id,
                    conversation_id=normalized.conversation_id,
                    event_type="handover_recommended",
                    payload={
                        "intent_name": intent_decision.intent_name,
                        "handover_reason": intent_decision.handover_reason,
                    },
                )
            else:
                ai_provider = get_ai_provider(settings, account_id=normalized.account_id)
                enqueue_result = queue_service.enqueue_ai_generation(
                    {
                        "account_id": normalized.account_id,
                        "conversation_id": normalized.conversation_id,
                        "recipient_id": normalized.user_id,
                        "waba_id": normalized.waba_id,
                        "phone_number_id": normalized.phone_number_id,
                        "user_message": normalized.text,
                        "language_code": detected_language,
                        "intent_name": intent_decision.intent_name,
                        "intent_confidence": intent_decision.confidence,
                        "handover_recommended": intent_decision.handover_recommended,
                        "handover_reason": intent_decision.handover_reason,
                    }
                )
                await runtime_state_store.record_queue_event(
                    account_id=normalized.account_id,
                    conversation_id=normalized.conversation_id,
                    event_type="ai_generation_queued",
                    payload={
                        "job_id": enqueue_result.job_id,
                        "queue": enqueue_result.queue,
                        "source_message": normalized.model_dump(),
                    },
                )
                reply_text = None
                ai_provider_name = ai_provider.provider_name
                ai_model = ai_provider.model
                delivery_mode = "ai_async_queued"
                queue_job = enqueue_result.model_dump()
                business_ai_replies_total.labels(
                    provider=ai_provider.provider_name,
                    outcome="queued",
                ).inc()
    else:
        if requested_mode == "ai":
            reply_text = None
            delivery_mode = "manual_queue"
            business_ai_replies_total.labels(provider="none", outcome="disabled").inc()
            await runtime_state_store.record_queue_event(
                account_id=normalized.account_id,
                conversation_id=normalized.conversation_id,
                event_type="manual_queue",
                payload=normalized.model_dump(),
            )
        else:
            reply_text = f"Echo: {normalized.text}"
            delivery_mode = "echo"
        ai_provider_name = "none"
        ai_model = "none"

    if reply_text is not None:
        conversation = await runtime_state_store.get_conversation_model(
            account_id=normalized.account_id,
            conversation_id=normalized.conversation_id,
        )
        outbound_language = detected_language
        dispatch_request = build_outbound_dispatch_request(
            provider=messaging_provider,
            conversation=conversation,
            account_id=normalized.account_id,
            conversation_id=normalized.conversation_id,
            recipient_id=normalized.user_id,
            text=reply_text,
            message_type="text",
            metadata={
                "delivery_mode": delivery_mode,
                "route_name": route_decision.route_name if route_decision is not None else None,
                "intent_name": intent_decision.intent_name,
            },
        )
        try:
            dispatch_result = await messaging_provider.send_outbound(dispatch_request)
        except Exception:
            business_outbound_messages_total.labels(
                provider=messaging_provider.provider_name,
                delivery_mode=delivery_mode,
                outcome="failed",
            ).inc()
            message_processing_failures_total.labels(
                provider=messaging_provider.provider_name,
                stage=delivery_mode,
            ).inc()
            raise
        dispatch_provider = dispatch_result.provider_name
        dispatch_provider_message_id = dispatch_result.provider_message_id
        business_outbound_messages_total.labels(
            provider=dispatch_result.provider_name,
            delivery_mode=delivery_mode,
            outcome="accepted",
        ).inc()
        await runtime_state_store.record_outbound_message(
            account_id=normalized.account_id,
            conversation_id=normalized.conversation_id,
            recipient_id=conversation.customer_id,
            text=reply_text,
            language_code=outbound_language,
            translated_text=None,
            translated_language_code=None,
            delivery_mode=delivery_mode,
            ai_generated=False,
            payload={
                "provider": dispatch_result.provider_name,
                "provider_message_id": dispatch_result.provider_message_id,
                "provider_accepted": dispatch_result.accepted,
                "text": reply_text,
                "delivery_mode": delivery_mode,
                "waba_id": normalized.waba_id,
                "phone_number_id": normalized.phone_number_id,
                "route_name": route_decision.route_name if route_decision is not None else None,
                "route_metadata": route_decision.metadata if route_decision is not None else None,
                "intent_name": intent_decision.intent_name,
                "intent_confidence": intent_decision.confidence,
                "handover_recommended": intent_decision.handover_recommended,
                "handover_reason": intent_decision.handover_reason,
            },
            provider_message_id=dispatch_result.provider_message_id,
        )
        if route_decision is not None:
            runtime_state_store.add_audit_log(
                account_id=normalized.account_id,
                actor_type="system",
                actor_id=None,
                action="support_route_resolved",
                target_type="conversation",
                target_id=normalized.conversation_id,
                payload={
                    "route_name": route_decision.route_name,
                    "delivery_mode": delivery_mode,
                    "metadata": route_decision.metadata,
                },
            )
            runtime_state_store.commit()

    return {
        "inbound": normalized.model_dump(),
        "translation": {
            "source_language": detected_language,
            "console_language": None,
            "console_text": normalized.text,
            "translated": False,
        },
        "account_id": normalized.account_id,
        "outbound": {
            "provider": dispatch_provider,
            "provider_message_id": dispatch_provider_message_id,
            "text": reply_text,
            "delivery_mode": delivery_mode,
        },
        "ai": {
            "provider": ai_provider_name,
            "model": ai_model,
        },
        "queue": queue_job,
        "runtime": effective_ai_status,
        "intent": {
            "intent_name": intent_decision.intent_name,
            "confidence": intent_decision.confidence,
            "handover_recommended": intent_decision.handover_recommended,
            "handover_reason": intent_decision.handover_reason,
        },
    }


async def handle_mock_inbound_message(
    payload: MockInboundMessage,
    settings: Settings,
    runtime_state_store: RuntimeStateStore,
    translation_service: TranslationService,
    queue_service: QueueService,
) -> dict[str, object]:
    messaging_provider = MockMessagingProvider()
    normalized_messages = await messaging_provider.normalize_inbound(payload)
    normalized = normalized_messages[0]
    mock_inbound_messages_total.inc()
    return await process_inbound_message(
        normalized,
        messaging_provider=messaging_provider,
        requested_mode=payload.mode,
        settings=settings,
        runtime_state_store=runtime_state_store,
        translation_service=translation_service,
        queue_service=queue_service,
        language_hint=payload.language_hint,
    )


def _normalized_message_has_meaningful_text(normalized: NormalizedMessage) -> bool:
    metadata = normalized.metadata or {}
    if metadata.get("has_meaningful_text") is False:
        return False
    return bool(normalized.text.strip())


def _resolve_phone_number_waba_id(phone_number: object | None) -> str | None:
    if phone_number is None:
        return None
    snapshot_waba_id = getattr(phone_number, "waba_id", None)
    if isinstance(snapshot_waba_id, str) and snapshot_waba_id:
        return snapshot_waba_id
    waba_account = getattr(phone_number, "waba_account", None)
    waba_id = getattr(waba_account, "waba_id", None)
    if isinstance(waba_id, str) and waba_id:
        return waba_id
    return None
