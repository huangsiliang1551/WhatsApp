import asyncio
import json
import structlog
from sqlalchemy.orm import Session

from app.core.metrics import (
    business_ai_replies_total,
    business_outbound_messages_total,
    message_processing_failures_total,
)
from app.core.settings import Settings
from app.db.session import get_sessionmaker
from app.providers.ai.base import AIConversationTurn, AIModelParams, AIReplyRequest
from app.providers.factory import get_ai_provider, get_ecommerce_provider, get_messaging_provider
from app.providers.translation.factory import get_translation_provider
from app.services.ai_chat_config_service import AiChatConfigService
from app.services.ai_tool_executor import AIToolExecutor
from app.services.context_window import ContextWindowOptimizer, ContextWindowStats
from app.services.ecommerce_service import EcommerceService
from app.services.messaging_dispatch import build_outbound_dispatch_request
from app.services.notification_service import NotificationService
from app.services.runtime_state import RuntimeStateStore
from app.services.support_intent_service import SupportIntentService
from app.services.support_knowledge_service import SupportKnowledgeService
from app.services.support_router import SupportRouter
from app.services.translation_service import TranslationService

logger = structlog.get_logger()

FALLBACK_REPLY_TEXT = "抱歉，我暂时无法自动处理这条消息，稍后会由人工继续跟进。"


async def process_ai_generation_job(
    payload: dict[str, object],
    settings: Settings,
    runtime_state: RuntimeStateStore | None = None,
) -> dict[str, object]:
    session: Session | None = None
    own_runtime_state = runtime_state
    if own_runtime_state is None:
        session = get_sessionmaker()()
        own_runtime_state = RuntimeStateStore(session)

    try:
        translation_service = TranslationService(
            settings=settings,
            provider=get_translation_provider(settings),
        )
        ecommerce_service = EcommerceService(
            provider=get_ecommerce_provider(settings),
            runtime_state=own_runtime_state,
        )
        support_router = SupportRouter(
            ecommerce_service=ecommerce_service,
            translation_service=translation_service,
            support_knowledge_service=SupportKnowledgeService(own_runtime_state.session),
        )
        intent_service = SupportIntentService()
        account_id = str(payload["account_id"])
        conversation_id = str(payload["conversation_id"])
        recipient_id = str(payload["recipient_id"])
        queued_waba_id = _optional_payload_string(payload.get("waba_id"))
        queued_phone_number_id = _optional_payload_string(payload.get("phone_number_id"))
        customer_language = str(payload["language_code"])
        source_job_id = str(payload["job_id"]) if payload.get("job_id") is not None else None
        if source_job_id is not None:
            existing_message = await own_runtime_state.get_outbound_message_by_source_job_id(
                account_id=account_id,
                conversation_id=conversation_id,
                source_job_id=source_job_id,
            )
            if existing_message is not None:
                return {
                    "status": "deduplicated",
                    "reason": "job_already_processed",
                    "db_message_id": existing_message.id,
                    "message_id": existing_message.id,
                    "provider_message_id": existing_message.provider_message_id,
                }
        effective_ai_status = await own_runtime_state.get_effective_ai_status(
            account_id=account_id,
            conversation_id=conversation_id,
        )
        if not bool(effective_ai_status["effective_ai_enabled"]):
            business_ai_replies_total.labels(provider="none", outcome="disabled").inc()
            await own_runtime_state.record_queue_event(
                account_id=account_id,
                conversation_id=conversation_id,
                event_type="ai_generation_skipped",
                payload={
                    "job_type": "ai_generation",
                    "reason": "effective_ai_disabled_before_processing",
                },
            )
            return {
                "status": "skipped",
                "reason": "effective_ai_disabled_before_processing",
            }

        conversation = await own_runtime_state.get_conversation_model(
            account_id=account_id,
            conversation_id=conversation_id,
        )
        # Skip AI generation for sleeping conversations (auto-wake on customer message handles this)
        if bool(conversation.is_sleeping):
            return {
                "status": "skipped",
                "reason": "conversation_sleeping",
            }
        current_scope = _conversation_scope_snapshot(conversation)
        if not _ai_queue_scope_matches_conversation(
            conversation=conversation,
            queued_waba_id=queued_waba_id,
            queued_phone_number_id=queued_phone_number_id,
        ):
            await own_runtime_state.record_queue_event(
                account_id=account_id,
                conversation_id=conversation_id,
                event_type="ai_generation_skipped",
                payload={
                    "job_type": "ai_generation",
                    "reason": "queue_scope_mismatch_before_processing",
                    "queued_waba_id": queued_waba_id,
                    "queued_phone_number_id": queued_phone_number_id,
                    "current_waba_id": current_scope["waba_id"],
                    "current_phone_number_id": current_scope["phone_number_id"],
                },
            )
            business_ai_replies_total.labels(provider="none", outcome="skipped_scope").inc()
            return {
                "status": "skipped",
                "reason": "queue_scope_mismatch_before_processing",
                "queued_waba_id": queued_waba_id,
                "queued_phone_number_id": queued_phone_number_id,
                "current_waba_id": current_scope["waba_id"],
                "current_phone_number_id": current_scope["phone_number_id"],
            }

        # ── 加载 AI 聊天配置 ──
        config_service = AiChatConfigService(own_runtime_state.session)
        ai_config = None
        agency_id: str | None = None
        try:
            # 通过 account 获取 agency_id
            conversation_account = getattr(conversation, "account", None)
            agency_id = getattr(conversation_account, "agency_id", None) if conversation_account else None
            ai_config = config_service.get_effective_config(agency_id=agency_id)
        except Exception:
            logger.warning("failed_to_load_ai_chat_config", account_id=account_id, conversation_id=conversation_id)

        route_decision = await support_router.resolve(
            account_id=account_id,
            customer_language=customer_language,
            user_message=str(payload["user_message"]),
        )
        intent_name = str(payload.get("intent_name") or "")
        handover_recommended = payload.get("handover_recommended")
        handover_reason = payload.get("handover_reason")
        intent_confidence = payload.get("intent_confidence")
        if not intent_name:
            intent_decision = intent_service.classify(str(payload["user_message"]))
            intent_name = intent_decision.intent_name
            handover_recommended = intent_decision.handover_recommended
            handover_reason = intent_decision.handover_reason
            intent_confidence = intent_decision.confidence
        if route_decision is None and bool(handover_recommended):
            business_ai_replies_total.labels(
                provider="intent_router",
                outcome="skipped_handover",
            ).inc()
            await own_runtime_state.record_queue_event(
                account_id=account_id,
                conversation_id=conversation_id,
                event_type="handover_recommended",
                payload={
                    "intent_name": intent_name,
                    "handover_reason": handover_reason,
                },
            )
            own_runtime_state.add_audit_log(
                account_id=account_id,
                actor_type="system",
                actor_id=None,
                action="support_intent_evaluated",
                target_type="conversation",
                target_id=conversation_id,
                payload={
                    "intent_name": intent_name,
                    "confidence": intent_confidence,
                    "handover_recommended": handover_recommended,
                    "handover_reason": handover_reason,
                    "phone_number_id": effective_ai_status.get("phone_number_id"),
                },
            )
            own_runtime_state.commit()
            return {
                "status": "skipped",
                "reason": "handover_recommended_before_ai",
                "intent_name": intent_name,
                "handover_reason": handover_reason,
            }

        # ── 检查 AI 聊天配置转人工条件 ──
        if ai_config and route_decision is None:
            should_escalate, escalate_reason = config_service.check_escalation(
                ai_config,
                str(payload.get("user_message", "")),
                intent_name=intent_name or None,
                unknown_count=0,
            )
            if should_escalate:
                business_ai_replies_total.labels(
                    provider="ai_chat_config",
                    outcome="escalated",
                ).inc()
                await own_runtime_state.record_queue_event(
                    account_id=account_id,
                    conversation_id=conversation_id,
                    event_type="handover_recommended",
                    payload={
                        "source": "ai_chat_config",
                        "reason": escalate_reason,
                    },
                )
                own_runtime_state.add_audit_log(
                    account_id=account_id,
                    actor_type="system",
                    actor_id=None,
                    action="ai_chat_config_escalated",
                    target_type="conversation",
                    target_id=conversation_id,
                    payload={
                        "reason": escalate_reason,
                    },
                )
                own_runtime_state.commit()
                return {
                    "status": "skipped",
                    "reason": f"escalated_by_config: {escalate_reason}",
                }

        ai_provider = get_ai_provider(settings, account_id=account_id)
        messaging_provider = get_messaging_provider(settings)
        delivery_mode = "ai_auto_reply"
        payload_provider = ai_provider.provider_name
        payload_model = ai_provider.model
        degraded = False
        fallback_reason: str | None = None
        token_stats: ContextWindowStats | None = None

        if route_decision is not None:
            reply_text = route_decision.reply_text
            customer_language = route_decision.delivered_language
            delivery_mode = "rule_auto_reply"
            payload_provider = "rule_router"
            payload_model = route_decision.route_name
            business_ai_replies_total.labels(provider="rule_router", outcome="routed").inc()
        else:
            optimizer = ContextWindowOptimizer(
                max_messages=settings.ai_context_max_messages,
                max_history_chars=settings.ai_context_max_history_chars,
                max_message_chars=settings.ai_context_max_message_chars,
                max_total_context_chars=settings.ai_context_max_total_chars,
            )
            history, token_stats = await _build_conversation_history(
                runtime_state=own_runtime_state,
                account_id=account_id,
                conversation_id=conversation_id,
                optimizer=optimizer,
                user_message=str(payload["user_message"]),
            )
            # ── 从配置构建模型参数 ──
            model_params = None
            if ai_config:
                model_params = AIModelParams(
                    temperature=ai_config.temperature or 0.3,
                    max_tokens=ai_config.max_tokens or 300,
                    top_p=ai_config.top_p or 1.0,
                    frequency_penalty=ai_config.frequency_penalty or 0.0,
                    presence_penalty=ai_config.presence_penalty or 0.0,
                )

            # ── 从配置构建 system_prompt ──
            system_prompt = None
            if ai_config:
                system_prompt = config_service.build_system_prompt(
                    ai_config,
                    extra_vars={
                        "customer_language": customer_language,
                    },
                )

            # ── 从配置获取可用工具 ──
            available_tools = config_service.get_available_tools(ai_config) if ai_config else []

            # ── 获取已验证用户 ID（会话 metadata_json） ──
            verified_user_id: str | None = None
            metadata_json = getattr(conversation, "metadata_json", None) or {}
            if isinstance(metadata_json, dict):
                verified_user_id = metadata_json.get("verified_user_id") or None

            request = AIReplyRequest(
                account_id=account_id,
                conversation_id=conversation_id,
                customer_language=customer_language,
                user_message=str(payload["user_message"]),
                conversation_history=history,
                system_prompt=system_prompt,
                model_params=model_params,
                available_tools=available_tools,
                verified_user_id=verified_user_id,
                agency_id=agency_id,
            )

            try:
                reply_text = await _generate_with_tool_loop(
                    ai_provider=ai_provider,
                    request=request,
                    tool_executor=AIToolExecutor(
                        session=own_runtime_state.session,
                        settings=settings,
                        conversation_id=conversation_id,
                        account_id=account_id,
                        agency_id=agency_id,
                    ),
                    config=ai_config,
                )
                # ── 截断过长的回复 ──
                if ai_config and ai_config.max_response_length:
                    max_len = int(ai_config.max_response_length)
                    if max_len > 0:
                        reply_text = _truncate_reply_text(reply_text, max_len)
                business_ai_replies_total.labels(
                    provider=ai_provider.provider_name,
                    outcome="success",
                ).inc()
            except Exception as exc:
                degraded = True
                fallback_reason = str(exc)
                business_ai_replies_total.labels(
                    provider=ai_provider.provider_name,
                    outcome="fallback",
                ).inc()
                logger.warning(
                    "ai_generation_fallback_used",
                    account_id=account_id,
                    conversation_id=conversation_id,
                    provider=ai_provider.provider_name,
                    model=ai_provider.model,
                    error=fallback_reason,
                )
                # 创建通知：AI 回复失败
                try:
                    notif_svc = NotificationService(own_runtime_state.session)
                    notif_svc.create_notification(
                        account_id=account_id,
                        type="alert",
                        category="ai",
                        title="AI 回复失败，已降级",
                        message=f"会话 {conversation_id}: AI 回复失败 ({fallback_reason[:200]})",
                        severity="error",
                    )
                except Exception:
                    logger.warning("ai_failure_notification_creation_failed", account_id=account_id)
                reply_text = await _build_fallback_reply(
                    translation_service=translation_service,
                    customer_language=customer_language,
                )

        # Track token usage if optimizer was used
        if route_decision is None and token_stats is not None:
            logger.info(
                "ai_context_token_usage",
                account_id=account_id,
                conversation_id=conversation_id,
                token_usage=token_stats.to_dict(),
            )

        # ── 自动回复延迟 ──
        if ai_config and ai_config.auto_reply_enabled and ai_config.auto_reply_delay_seconds:
            delay = int(ai_config.auto_reply_delay_seconds)
            if delay > 0 and route_decision is None:
                await asyncio.sleep(delay)

        own_runtime_state.ensure_conversation_messaging_available(conversation)
        dispatch_request = build_outbound_dispatch_request(
            provider=messaging_provider,
            conversation=conversation,
            account_id=account_id,
            conversation_id=conversation_id,
            recipient_id=recipient_id,
            text=reply_text,
            message_type="text",
            metadata={
                "delivery_mode": delivery_mode,
                "job_type": "ai_generation",
                "source_job_id": source_job_id,
                "route_name": route_decision.route_name if route_decision is not None else None,
                "intent_name": intent_name,
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
        business_outbound_messages_total.labels(
            provider=dispatch_result.provider_name,
            delivery_mode=delivery_mode,
            outcome="accepted",
        ).inc()
        message = await own_runtime_state.record_outbound_message(
            account_id=account_id,
            conversation_id=conversation_id,
            recipient_id=recipient_id,
            text=reply_text,
            language_code=customer_language,
            translated_text=None,
            translated_language_code=None,
            delivery_mode=delivery_mode,
            ai_generated=delivery_mode == "ai_auto_reply",
            payload={
                "provider": payload_provider,
                "model": payload_model,
                "messaging_provider": dispatch_result.provider_name,
                "provider_message_id": dispatch_result.provider_message_id,
                "provider_accepted": dispatch_result.accepted,
                "job_type": "ai_generation",
                "source_job_id": source_job_id,
                "waba_id": current_scope["waba_id"],
                "phone_number_id": current_scope["phone_number_id"],
                "degraded": degraded,
                "fallback_reason": fallback_reason,
                "route_name": route_decision.route_name if route_decision is not None else None,
                "route_metadata": route_decision.metadata if route_decision is not None else None,
                "intent_name": intent_name,
                "intent_confidence": intent_confidence,
                "handover_recommended": handover_recommended,
                "handover_reason": handover_reason,
            },
            provider_message_id=dispatch_result.provider_message_id,
        )

        # ── A7: Record AI usage for billing ──
        if delivery_mode == "ai_auto_reply":
            try:
                from app.services.ai_usage_service import AiUsageService
                ai_usage_svc = AiUsageService(own_runtime_state.session)
                ai_usage_svc.record_ai_usage(
                    agency_id=agency_id,
                    site_id=current_scope.get("site_id"),
                    conversation_id=conversation_id,
                    provider_name=payload_provider,
                    message_count=1,
                )
                own_runtime_state.session.flush()
            except Exception as usage_err:
                logger.warning("ai_usage_record_failed", error=str(usage_err))

        if route_decision is not None:
            own_runtime_state.add_audit_log(
                account_id=account_id,
                actor_type="system",
                actor_id=None,
                action="support_route_resolved",
                target_type="conversation",
                target_id=conversation_id,
                payload={
                    "route_name": route_decision.route_name,
                    "delivery_mode": delivery_mode,
                    "metadata": route_decision.metadata,
                },
            )
            own_runtime_state.commit()
        return {
            "status": "completed",
            "provider": payload_provider,
            "ai_provider": payload_provider,
            "model": payload_model,
            "db_message_id": message.id,
            "message_id": message.id,
            "messaging_provider": dispatch_result.provider_name,
            "provider_message_id": dispatch_result.provider_message_id,
            "reply_text": reply_text,
            "degraded": degraded,
            "fallback_reason": fallback_reason,
            "route_name": route_decision.route_name if route_decision is not None else None,
            "token_usage": token_stats.to_dict() if token_stats is not None else None,
        }
    finally:
        if session is not None:
            session.close()


def _optional_payload_string(value: object) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None


def _conversation_scope_snapshot(conversation: object) -> dict[str, str | None]:
    phone_number = getattr(conversation, "phone_number", None)
    return {
        "waba_id": _resolve_phone_waba_id(phone_number),
        "phone_number_id": getattr(phone_number, "phone_number_id", None),
    }


def _resolve_phone_waba_id(phone_number: object | None) -> str | None:
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


def _ai_queue_scope_matches_conversation(
    *,
    conversation: object,
    queued_waba_id: str | None,
    queued_phone_number_id: str | None,
) -> bool:
    current_scope = _conversation_scope_snapshot(conversation)
    if queued_waba_id is not None and current_scope["waba_id"] != queued_waba_id:
        return False
    if (
        queued_phone_number_id is not None
        and current_scope["phone_number_id"] != queued_phone_number_id
    ):
        return False
    return True


async def _build_fallback_reply(
    translation_service: TranslationService,
    customer_language: str,
) -> str:
    translated_text, translated = await translation_service.translate_outbound_for_customer(
        text=FALLBACK_REPLY_TEXT,
        source_language="zh-CN",
        target_language=customer_language,
    )
    return translated_text if translated else FALLBACK_REPLY_TEXT


async def _build_conversation_history(
    runtime_state: RuntimeStateStore,
    account_id: str,
    conversation_id: str,
    optimizer: ContextWindowOptimizer | None = None,
    user_message: str = "",
) -> tuple[list[AIConversationTurn], ContextWindowStats | None]:
    messages = await runtime_state.list_message_models(
        account_id=account_id,
        conversation_id=conversation_id,
    )
    if optimizer is not None:
        history, stats = optimizer.trim_history(
            messages,
            user_message=user_message,
        )
        return history, stats
    return _truncate_history(messages), None


def _truncate_history(
    messages: list[object],
) -> list[AIConversationTurn]:
    if not messages:
        return []

    selected_messages = messages[-6:]
    history: list[AIConversationTurn] = []

    for message in reversed(selected_messages):
        text = _safe_message_text(message)
        if not text:
            continue
        role = "user" if getattr(message, "direction", None) == "inbound" else "assistant"
        language_code = getattr(message, "language_code", None)

        truncated = text[:500]
        if len(text) > 500:
            truncated = truncated + "..."

        current_total = sum(len(t.text) for t in history)
        if current_total + len(truncated) > 1600:
            remaining = 1600 - current_total
            if remaining > 50:
                truncated = truncated[-remaining:]
            else:
                continue

        history.append(
            AIConversationTurn(
                role=role,
                text=truncated,
                language_code=language_code,
            )
        )

    history.reverse()
    return history


def _safe_message_text(message: object) -> str:
    return (getattr(message, "content_text", None) or "").strip()


# ═══════════════════════════════════════════════════════════════════════════════
# AI 聊天配置辅助函数
# ═══════════════════════════════════════════════════════════════════════════════


async def _generate_with_tool_loop(
    ai_provider: Any,
    request: AIReplyRequest,
    tool_executor: AIToolExecutor,
    config: Any | None,
) -> str:
    """生成回复，支持 tool_call 循环处理。

    当 AI 返回 ``{"__tool_calls__": [...]}`` 时，自动执行工具调用，
    并将结果回传给 AI 获取最终自然语言回复。
    """
    max_rounds = 3  # 防止无限循环
    current_request = request

    for round_idx in range(max_rounds):
        reply = await ai_provider.generate_reply(current_request)

        # 检查是否为工具调用响应
        if not reply.startswith('{"__tool_calls__'):
            return reply

        # 解析工具调用
        try:
            data = json.loads(reply)
            tool_calls = data.get("__tool_calls__", [])
        except (json.JSONDecodeError, TypeError):
            return reply

        if not tool_calls:
            continue

        # 执行工具调用
        results_text = ""
        for tc in tool_calls:
            func_name = tc.get("function", {}).get("name", "")
            func_args_raw = tc.get("function", {}).get("arguments", "{}")
            try:
                func_args = (
                    json.loads(func_args_raw)
                    if isinstance(func_args_raw, str)
                    else func_args_raw
                )
            except json.JSONDecodeError:
                func_args = {}

            max_calls = (config.max_tool_calls_per_session or 10) if config else 10
            timeout = (config.tool_call_timeout_seconds or 5) if config else 5

            result = await tool_executor.execute_tool(
                tool_name=func_name,
                arguments=func_args,
                verified_user_id=current_request.verified_user_id,
                max_calls=max_calls,
                timeout_seconds=timeout,
            )
            results_text += f"\n[{func_name}]：{json.dumps(result, ensure_ascii=False)}"

        # 构建下一次请求的消息历史
        new_history = list(current_request.conversation_history)
        new_history.append(
            AIConversationTurn(
                role="assistant",
                text=f"[工具调用结果]\n{results_text.strip()}",
            )
        )

        current_request = AIReplyRequest(
            account_id=current_request.account_id,
            conversation_id=current_request.conversation_id,
            customer_language=current_request.customer_language,
            user_message="请根据以上工具调用结果的最终输出，用自然语言回复客户。",
            conversation_history=new_history,
            system_prompt=current_request.system_prompt,
            model_params=current_request.model_params,
            available_tools=[],  # 工具结果回传时不再触发新调用
            verified_user_id=current_request.verified_user_id,
            agency_id=current_request.agency_id,
        )

    # 超过最大轮次，返回最终回复
    return await ai_provider.generate_reply(current_request)


def _truncate_reply_text(text: str, max_length: int) -> str:
    """截断回复文本到指定长度。"""
    if not text or max_length <= 0:
        return text
    if len(text) <= max_length:
        return text
    return text[:max_length].strip() + "..."
