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


# AI / 规则自动回复的统一 delivery_mode 集合：这些模式必须标记 ai_generated=True
# 并写入 AI 接待归属和 owner / entry link 快照（spec 5.9 / 8.4）。
AI_DELIVERY_MODES = {
    "ai_sync_reply",
    "ai_async_queued",
    "ai_generation_queued",
    "rule_auto_reply",
    "intent_auto_reply",
    "ai_outbound_job",
}


def _is_ai_delivery_mode(delivery_mode: str | None) -> bool:
    return delivery_mode in AI_DELIVERY_MODES


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
    # ── 解析 entry 上下文并确保会话 AI 归属（spec 6.1 / 6.2 / 6.7） ──
    entry_context: dict[str, object] = {
        "user_id": normalized.user_id,
        "waba_id": normalized.waba_id,
        "phone_number_id": normalized.phone_number_id,
        "customer_wa_id": normalized.user_id,
    }
    inbound_metadata = normalized.metadata or {}
    if isinstance(inbound_metadata, dict):
        for key in ("entry_code", "ref", "referral_entry_code"):
            value = inbound_metadata.get(key)
            if isinstance(value, str) and value:
                entry_context["entry_code"] = value
                break
        if "referral" in inbound_metadata and isinstance(inbound_metadata["referral"], dict):
            ref = inbound_metadata["referral"]
            for key in ("entry_code", "ref", "source_url"):
                value = ref.get(key)
                if isinstance(value, str) and value:
                    entry_context["entry_code"] = value
                    break
    if "entry_code" not in entry_context:
        entry_context["entry_code"] = None
    entry_context["text"] = normalized.text

    conversation_ai_assignment = None
    try:
        from app.services.conversation_ai_assignment_service import (
            AI_DELIVERY_MODES as _AI_DELIVERY_MODES,  # noqa: F401  consistency check
            ConversationAIAssignmentService,
        )
        from app.services.ownership_snapshot_service import OwnershipSnapshotService
        from sqlalchemy.orm.attributes import flag_modified

        ai_svc = ConversationAIAssignmentService(runtime_state_store.session)
        resolved = ai_svc.resolve_entry_context_from_inbound_message(
            account_id=normalized.account_id,
            conversation_id=normalized.conversation_id,
            text=normalized.text,
            waba_id=normalized.waba_id,
            phone_number_id=normalized.phone_number_id,
            customer_wa_id=normalized.user_id,
            user_id=normalized.user_id,
            entry_code=entry_context.get("entry_code"),  # type: ignore[arg-type]
            referral_metadata=inbound_metadata if isinstance(inbound_metadata, dict) else None,
        )
        entry_context.update({k: v for k, v in resolved.items() if v is not None})
        try:
            conversation_ai_assignment = ai_svc.ensure_conversation_ai_assignment(
                account_id=normalized.account_id,
                conversation_id=normalized.conversation_id,
                entry_context=resolved,
            )
        except Exception as assignment_exc:  # noqa: BLE001
            # AI 归属解析失败不能阻塞主链路；保留骨架日志后继续。
            runtime_state_store.add_audit_log(
                account_id=normalized.account_id,
                actor_type="system",
                actor_id=None,
                action="conversation_ai_assignment_skipped",
                target_type="conversation",
                target_id=normalized.conversation_id,
                payload={"reason": str(assignment_exc)},
            )
        # 将会话当前归属同步到 Conversation 行（一次刷新即可）
        conversation_model = runtime_state_store.session.get(
            type(runtime_state_store._require_conversation(  # type: ignore[attr-defined]
                account_id=normalized.account_id,
                conversation_id=normalized.conversation_id,
            )),
            runtime_state_store._require_conversation(  # type: ignore[attr-defined]
                account_id=normalized.account_id,
                conversation_id=normalized.conversation_id,
            ).id,
        )
        if conversation_ai_assignment is not None and conversation_model is not None:
            conversation_model.current_ai_agent_id = conversation_ai_assignment.actual_ai_agent_id
            conversation_model.current_ai_assignment_id = conversation_ai_assignment.id
            if conversation_ai_assignment.failover_from_ai_agent_id:
                conversation_model.ai_failover_active = True
                conversation_model.ai_failover_from_agent_id = (
                    conversation_ai_assignment.failover_from_ai_agent_id
                )
                conversation_model.ai_failover_reason = conversation_ai_assignment.failover_reason
            else:
                conversation_model.ai_failover_active = False
                conversation_model.ai_failover_from_agent_id = None
                conversation_model.ai_failover_reason = None
            if conversation_ai_assignment.source_entry_link_id is not None:
                conversation_model.current_entry_link_id = (
                    conversation_ai_assignment.source_entry_link_id
                )
            runtime_state_store.session.add(conversation_model)
        # 把 owner / entry 快照预热到 conversation（业务消息发件人/客服使用）
        try:
            snap_svc = OwnershipSnapshotService(runtime_state_store.session)
            snap = snap_svc.build_snapshot_for_user(normalized.account_id, normalized.user_id)
            if conversation_model is not None and snap.owner_staff_user_id_snapshot:
                conversation_model.current_owner_agency_id_snapshot = (
                    snap.owner_agency_id_snapshot
                )
                conversation_model.current_owner_staff_user_id_snapshot = (
                    snap.owner_staff_user_id_snapshot
                )
                conversation_model.current_owner_agency_member_id_snapshot = (
                    snap.owner_agency_member_id_snapshot
                )
                conversation_model.current_owner_assignment_id_snapshot = (
                    snap.owner_assignment_id_snapshot
                )
                if conversation_model.current_entry_link_id is None:
                    conversation_model.current_entry_link_id = (
                        snap.source_entry_link_id_snapshot
                    )
                runtime_state_store.session.add(conversation_model)
        except Exception:  # noqa: BLE001
            # 快照解析失败不影响主流程
            pass
    except Exception:  # noqa: BLE001
        # 整段 AI 归属入口解析失败也不能阻塞主消息链路
        pass

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
                "entry_code": entry_context.get("entry_code"),
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
                # 收集当前 AI 归属快照塞入 queue payload，确保 worker 最终
                # 发送消息时也能补上 ai_agent_id / owner snapshot（spec 5.9 / 8.4）。
                queued_ai_agent_id: str | None = None
                queued_owner_snapshot: dict[str, object] = {}
                queued_entry_link_id: str | None = None
                try:
                    if conversation_ai_assignment is not None:
                        queued_ai_agent_id = conversation_ai_assignment.actual_ai_agent_id
                    from app.services.ownership_snapshot_service import OwnershipSnapshotService
                    snap_svc = OwnershipSnapshotService(runtime_state_store.session)
                    snap = snap_svc.build_snapshot_for_conversation(
                        account_id=normalized.account_id,
                        conversation_id=normalized.conversation_id,
                    )
                    queued_owner_snapshot = snap.as_dict()
                    queued_entry_link_id = (
                        normalized.entry_link_id
                        if hasattr(normalized, "entry_link_id")
                        else None
                    ) or snap.source_entry_link_id_snapshot
                except Exception:  # noqa: BLE001
                    pass
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
                        "ai_agent_id": queued_ai_agent_id,
                        "source_entry_link_id_snapshot": queued_entry_link_id,
                        "owner_snapshot": queued_owner_snapshot,
                        "ai_provider_name": ai_provider.provider_name,
                        "ai_model": ai_provider.model,
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
        # ── 计算本条出站消息的 AI / 归属快照（spec 5.9 / 8.4） ──
        is_ai_message = _is_ai_delivery_mode(delivery_mode)
        actual_ai_agent_id: str | None = None
        if is_ai_message:
            actual_ai_agent_id = (
                conversation_ai_assignment.actual_ai_agent_id
                if conversation_ai_assignment is not None
                else None
            ) or conversation.current_ai_agent_id if conversation else None
        owner_snapshot: dict[str, object] = {}
        entry_link_id_for_message: str | None = None
        try:
            from app.services.ownership_snapshot_service import OwnershipSnapshotService
            snap_svc = OwnershipSnapshotService(runtime_state_store.session)
            snap = snap_svc.build_snapshot_for_conversation(
                account_id=normalized.account_id,
                conversation_id=normalized.conversation_id,
            )
            owner_snapshot = snap.as_dict()
            if actual_ai_agent_id:
                owner_snapshot["ai_agent_id_snapshot"] = actual_ai_agent_id
            entry_link_id_for_message = (
                conversation.current_entry_link_id if conversation else None
            ) or snap.source_entry_link_id_snapshot
        except Exception:  # noqa: BLE001
            owner_snapshot = {}
            entry_link_id_for_message = (
                conversation.current_entry_link_id if conversation else None
            )
        # Actor 口径：AI 自动消息 = ai_agent；echo/system fallback = system
        if is_ai_message:
            actor_type = "ai_agent"
            actor_id_for_message = actual_ai_agent_id
        else:
            actor_type = "system"
            actor_id_for_message = None
        failover_from_id: str | None = None
        failover_reason_value: str | None = None
        if is_ai_message and conversation_ai_assignment is not None:
            failover_from_id = conversation_ai_assignment.failover_from_ai_agent_id
            failover_reason_value = conversation_ai_assignment.failover_reason
        if not failover_from_id and conversation is not None:
            failover_from_id = conversation.ai_failover_from_agent_id
            failover_reason_value = conversation.ai_failover_reason

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
            ai_generated=is_ai_message,
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
            actor_type=actor_type,
            actor_id=actor_id_for_message,
            ai_agent_id=actual_ai_agent_id,
            ai_assignment_id_snapshot=(
                conversation.current_ai_assignment_id if conversation else None
            ) or (conversation_ai_assignment.id if conversation_ai_assignment is not None else None),
            source_entry_link_id_snapshot=entry_link_id_for_message,
            owner_agency_id_snapshot=owner_snapshot.get("owner_agency_id_snapshot"),
            owner_staff_user_id_snapshot=owner_snapshot.get("owner_staff_user_id_snapshot"),
            owner_agency_member_id_snapshot=owner_snapshot.get("owner_agency_member_id_snapshot"),
            owner_assignment_id_snapshot=owner_snapshot.get("owner_assignment_id_snapshot"),
            ai_provider=ai_provider_name,
            ai_model=ai_model,
            failover_from_ai_agent_id=failover_from_id,
            failover_reason=failover_reason_value,
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
