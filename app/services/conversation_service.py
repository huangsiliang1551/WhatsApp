import json
from datetime import datetime, timezone
from uuid import uuid4

from app.core.auth import RequestActor
from app.core.metrics import business_outbound_messages_total, message_processing_failures_total
from app.core.settings import Settings
from app.db.models import AppUser, Conversation, Message
from app.providers.ai.base import AIConversationTurn, AIProvider, AIReplyRequest
from app.providers.factory import get_ai_provider
from app.providers.messaging.base import MessagingProvider
from app.schemas.conversations import (
    ConversationMessageView,
    ConversationSummary,
    ConversationTimelineItem,
    OutboundMessageRequest,
    OutboundMessageResponse,
)
from app.services.data_scope_filter_service import DataScopeFilterService
from app.services.messaging_dispatch import build_outbound_dispatch_request
from app.services.meta_scope_validation import MetaScopeValidator
from app.services.runtime_state import RuntimeStateStore
from app.services.translation_service import TranslationService
from sqlalchemy import select


def _fmt_utc(dt):
    """Format naive UTC datetime as ISO 8601 with Z suffix, so frontend parses it as UTC."""
    return dt.isoformat() + "Z"


class ConversationService:
    def __init__(
        self,
        runtime_state: RuntimeStateStore,
        translation_service: TranslationService,
        settings: Settings,
        messaging_provider: MessagingProvider,
    ) -> None:
        self._runtime_state = runtime_state
        self._translation_service = translation_service
        self._settings = settings
        self._messaging_provider = messaging_provider
        self._meta_scope_validator = MetaScopeValidator(runtime_state.session)

    async def list_conversations(
        self,
        account_id: str | None = None,
        waba_id: str | None = None,
        phone_number_id: str | None = None,
        assigned_agent_id: str | None = None,
        status: str | None = None,
        management_mode: str | None = None,
        latest_intent_name: str | None = None,
        latest_handover_recommended: bool | None = None,
        tag: str | None = None,
        is_sleeping: bool | None = None,
        allowed_account_ids: set[str] | None = None,
        agency_id: str | None = None,
        scope_actor: RequestActor | None = None,
        *,
        sort_by: str | None = None,
        sort_desc: bool = True,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[ConversationSummary], int]:
        self._meta_scope_validator.validate_waba_scope(
            account_id=account_id,
            waba_id=waba_id,
            allowed_account_ids=allowed_account_ids,
        )
        self._meta_scope_validator.validate_phone_number_scope(
            phone_number_id=phone_number_id,
            account_id=account_id,
            waba_id=waba_id,
            allowed_account_ids=allowed_account_ids,
            enforce_waba_match=True,
        )
        conversations = await self._runtime_state.list_conversation_models(
            account_id=account_id,
            waba_id=waba_id,
            phone_number_id=phone_number_id,
            assigned_agent_id=assigned_agent_id,
            status=status,
            management_mode=management_mode,
            is_sleeping=is_sleeping,
            agency_id=agency_id,
            scope_actor=scope_actor,
            sort_by=sort_by,
            sort_desc=sort_desc,
            offset=max(0, (page - 1) * size),
            limit=size,
        )
        total = await self._runtime_state.count_conversation_models(
            account_id=account_id,
            waba_id=waba_id,
            phone_number_id=phone_number_id,
            assigned_agent_id=assigned_agent_id,
            status=status,
            management_mode=management_mode,
            is_sleeping=is_sleeping,
            agency_id=agency_id,
            scope_actor=scope_actor,
        )

        # Tag filter applied early (avoids unnecessary batch queries for filtered-out items)
        if tag is not None:
            conversations = [
                c for c in conversations
                if tag in (getattr(c, "tags", None) or [])
            ]
        if not conversations:
            return ([], total)

        # Batch-fetch customer lifecycle_status
        customer_ids = list({c.customer_id for c in conversations if c.customer_id})
        lifecycle_map: dict[str, str] = {}
        if customer_ids:
            from sqlalchemy import select

            stmt = select(AppUser.public_user_id, AppUser.lifecycle_status).where(AppUser.public_user_id.in_(customer_ids))
            rows = self._runtime_state.session.execute(stmt).all()
            lifecycle_map = {row[0]: row[1] for row in rows}

        # Batch-fetch latest messages (eliminates N+1: 2 queries instead of N per conversation)
        conv_db_ids = [c.id for c in conversations]
        latest_msg_map = await self._runtime_state.list_latest_messages_batch(conv_db_ids)
        latest_inbound_map = await self._runtime_state.list_latest_inbound_messages_batch(conv_db_ids)

        summaries: list[ConversationSummary] = []
        for conversation in conversations:
            phone_number = conversation.phone_number
            last_message = latest_msg_map.get(conversation.id)
            latest_inbound = latest_inbound_map.get(conversation.id)
            summaries.append(
                ConversationSummary(
                    account_id=conversation.account_id,
                    conversation_id=conversation.external_conversation_id,
                    waba_id=self._resolve_phone_number_waba_id(phone_number),
                    phone_number_id=(
                        phone_number.phone_number_id
                        if phone_number is not None
                        else None
                    ),
                    customer_id=conversation.customer_id,
                    customer_language=conversation.customer_language,
                    customer_language_source=conversation.customer_language_source,
                    status=conversation.status,
                    management_mode=conversation.management_mode,
                    ai_enabled=conversation.ai_enabled,
                    assigned_agent_id=self._runtime_state.get_public_agent_id(
                        conversation.assigned_agent,
                        fallback=conversation.assigned_agent_id,
                    ),
                    assigned_agent_name=(
                        conversation.assigned_agent.display_name
                        if conversation.assigned_agent is not None
                        else None
                    ),
                    last_message_at=_fmt_utc(conversation.last_message_at) if conversation.last_message_at else None,
                    last_message_preview=self._get_message_primary_text(last_message),
                    latest_intent_name=(
                        str(latest_inbound.payload.get("intent_name"))
                        if latest_inbound is not None
                        and latest_inbound.payload is not None
                        and latest_inbound.payload.get("intent_name") is not None
                        else None
                    ),
                    latest_handover_recommended=(
                        bool(latest_inbound.payload.get("handover_recommended"))
                        if latest_inbound is not None and latest_inbound.payload is not None
                        else False
                    ),
                    latest_handover_reason=(
                        str(latest_inbound.payload.get("handover_reason"))
                        if latest_inbound is not None
                        and latest_inbound.payload is not None
                        and latest_inbound.payload.get("handover_reason") is not None
                        else None
                    ),
                    customer_lifecycle_status=lifecycle_map.get(conversation.customer_id),
                    is_sleeping=bool(conversation.is_sleeping),
                    last_customer_message_at=_fmt_utc(conversation.last_customer_message_at) if conversation.last_customer_message_at else None,
                )
            )
        if latest_intent_name is not None:
            summaries = [
                summary
                for summary in summaries
                if summary.latest_intent_name == latest_intent_name
            ]
        if latest_handover_recommended is not None:
            summaries = [
                summary
                for summary in summaries
                if summary.latest_handover_recommended == latest_handover_recommended
            ]
        return summaries, total

    async def wake_conversation(
        self,
        account_id: str,
        conversation_id: str,
        actor_type: str = "system",
        actor_id: str | None = None,
    ) -> ConversationSummary:
        state = await self._runtime_state.wake_conversation(
            account_id=account_id,
            conversation_id=conversation_id,
            actor_type=actor_type,
            actor_id=actor_id,
        )
        conversation = await self._runtime_state.get_conversation_model(
            account_id=state.account_id,
            conversation_id=state.conversation_id,
        )
        phone_number = conversation.phone_number
        return ConversationSummary(
            account_id=conversation.account_id,
            conversation_id=conversation.external_conversation_id,
            waba_id=self._resolve_phone_number_waba_id(phone_number),
            phone_number_id=phone_number.phone_number_id if phone_number is not None else None,
            customer_id=conversation.customer_id,
            customer_language=conversation.customer_language,
            customer_language_source=conversation.customer_language_source,
            status=conversation.status,
            management_mode=conversation.management_mode,
            ai_enabled=conversation.ai_enabled,
            assigned_agent_id=self._runtime_state.get_public_agent_id(
                conversation.assigned_agent,
                fallback=conversation.assigned_agent_id,
            ),
            assigned_agent_name=(
                conversation.assigned_agent.display_name
                if conversation.assigned_agent is not None
                else None
            ),
            last_message_at=_fmt_utc(conversation.last_message_at) if conversation.last_message_at else None,
            is_sleeping=bool(conversation.is_sleeping),
            last_customer_message_at=_fmt_utc(conversation.last_customer_message_at) if conversation.last_customer_message_at else None,
        )

    async def list_messages(self, account_id: str, conversation_id: str) -> list[ConversationMessageView]:
        return await self.list_messages_with_options(
            account_id=account_id,
            conversation_id=conversation_id,
            include_translations=False,
        )

    async def _ensure_conversation_scope(
        self,
        *,
        account_id: str,
        conversation_id: str,
        scope_actor: RequestActor | None,
    ) -> None:
        if scope_actor is None or scope_actor.is_super_admin:
            return
        stmt = select(Conversation.id).where(
            Conversation.account_id == account_id,
            Conversation.external_conversation_id == conversation_id,
        )
        stmt = DataScopeFilterService(self._runtime_state.session).filter_conversations(
            stmt,
            scope_actor,
        )
        scoped_conversation_id = self._runtime_state.session.scalar(stmt.limit(1))
        if scoped_conversation_id is None:
            raise LookupError(
                f"Conversation '{conversation_id}' not found for account '{account_id}'."
            )

    async def list_messages_with_options(
        self,
        account_id: str,
        conversation_id: str,
        *,
        include_translations: bool,
        include_cold: bool = False,
        offset: int = 0,
        limit: int | None = None,
        scope_actor: RequestActor | None = None,
    ) -> list[ConversationMessageView]:
        # include_translations 仅控制是否返回已缓存的译文，不再触发自动翻译。
        # 翻译由前端通过 POST /messages/{id}/translate 和 /messages/translate-batch 显式触发。
        await self._ensure_conversation_scope(
            account_id=account_id,
            conversation_id=conversation_id,
            scope_actor=scope_actor,
        )
        messages = await self._runtime_state.list_message_models(
            account_id=account_id,
            conversation_id=conversation_id,
            offset=offset,
            limit=limit,
            include_cold=include_cold,
        )
        views = [self._serialize_message_view(message) for message in messages]

        # Batch-fetch delivery_status from message_events
        message_ids = [m.id for m in messages if m.direction == "outbound"]
        if message_ids:
            events = await self._runtime_state.list_message_event_models(
                account_id=account_id,
                conversation_id=conversation_id,
                message_ids=message_ids,
            )
            status_map: dict[str, dict[str, object]] = {}
            for event in events:
                msg_id = getattr(event, "message_id", None)
                if msg_id and msg_id in message_ids:
                    event_type = getattr(event, "event_type", "")
                    occurred = getattr(event, "occurred_at", None)
                    occurred_str = _fmt_utc(occurred) if occurred else None
                    if msg_id not in status_map:
                        status_map[msg_id] = {"delivery_status": None, "delivered_at": None, "read_at": None}
                    if event_type == "sent" and not status_map[msg_id]["delivery_status"]:
                        status_map[msg_id]["delivery_status"] = "sent"
                    elif event_type == "delivered":
                        status_map[msg_id]["delivery_status"] = "delivered"
                        status_map[msg_id]["delivered_at"] = occurred_str
                    elif event_type == "read":
                        status_map[msg_id]["delivery_status"] = "read"
                        status_map[msg_id]["read_at"] = occurred_str
                    elif event_type == "failed":
                        status_map[msg_id]["delivery_status"] = "failed"
            for view in views:
                if view.message_id in status_map:
                    info = status_map[view.message_id]
                    view.delivery_status = info["delivery_status"]
                    view.delivered_at = info["delivered_at"]
                    view.read_at = info["read_at"]
                    # Compute delivery_status_updated_at for frontend timestamp display
                    status = info["delivery_status"]
                    if status == "read" and info["read_at"]:
                        view.delivery_status_updated_at = info["read_at"]
                    elif status == "delivered" and info["delivered_at"]:
                        view.delivery_status_updated_at = info["delivered_at"]
                    elif status == "sent" and info["delivered_at"]:
                        view.delivery_status_updated_at = info["delivered_at"]

        return views

    async def list_timeline(
        self,
        account_id: str,
        conversation_id: str,
        limit: int = 50,
        scope_actor: RequestActor | None = None,
    ) -> list[ConversationTimelineItem]:
        await self._ensure_conversation_scope(
            account_id=account_id,
            conversation_id=conversation_id,
            scope_actor=scope_actor,
        )
        audit_logs = await self._runtime_state.list_conversation_audit_logs(
            account_id=account_id,
            conversation_id=conversation_id,
            limit=limit,
        )
        handover_logs = await self._runtime_state.list_handover_logs(
            account_id=account_id,
            conversation_id=conversation_id,
        )
        message_events = await self._runtime_state.list_message_event_models(
            account_id=account_id,
            conversation_id=conversation_id,
        )

        timeline_items = [
            *[self._serialize_audit_timeline_item(item) for item in audit_logs],
            *[self._serialize_handover_timeline_item(item) for item in handover_logs],
            *[self._serialize_message_event_timeline_item(item) for item in message_events],
        ]
        timeline_items.sort(key=lambda item: (item.created_at, item.id), reverse=True)
        return timeline_items[:limit]

    async def send_outbound_message(
        self,
        account_id: str,
        conversation_id: str,
        payload: OutboundMessageRequest,
        actor_type: str = "system",
        actor_id: str | None = None,
        scope_actor: RequestActor | None = None,
    ) -> OutboundMessageResponse:
        await self._ensure_conversation_scope(
            account_id=account_id,
            conversation_id=conversation_id,
            scope_actor=scope_actor,
        )
        conversation = await self._runtime_state.get_conversation_model(
            account_id=account_id,
            conversation_id=conversation_id,
        )
        self._runtime_state.ensure_conversation_messaging_available(conversation)
        self._ensure_agent_can_reply(
            conversation=conversation,
            agent_id=payload.agent_id,
        )
        sent_by_agent_id = self._runtime_state.resolve_agent_storage_id(
            account_id=account_id,
            agent_id=payload.agent_id,
        )
        source_language = self._translation_service.detect_language(text=payload.text)
        target_language = conversation.customer_language
        delivered_text, translated = await self._translation_service.translate_outbound_for_customer(
            text=payload.text,
            source_language=source_language,
            target_language=target_language,
        )
        phone_number = conversation.phone_number
        provider_phone_number_id = phone_number.phone_number_id if phone_number is not None else None
        provider_waba_id = self._resolve_phone_number_waba_id(phone_number)
        dispatch_request = build_outbound_dispatch_request(
            provider=self._messaging_provider,
            conversation=conversation,
            account_id=account_id,
            conversation_id=conversation_id,
            recipient_id=conversation.customer_id,
            text=delivered_text,
            message_type="text",
            metadata={
                "source_language": source_language,
                "target_language": target_language,
                "translated": translated,
            },
        )
        await self._ensure_conversation_scope(
            account_id=account_id,
            conversation_id=conversation_id,
            scope_actor=scope_actor,
        )
        try:
            dispatch_result = await self._messaging_provider.send_outbound(dispatch_request)
        except Exception:
            business_outbound_messages_total.labels(
                provider=self._messaging_provider.provider_name,
                delivery_mode="manual_operator_send",
                outcome="failed",
            ).inc()
            message_processing_failures_total.labels(
                provider=self._messaging_provider.provider_name,
                stage="manual_operator_send",
            ).inc()
            raise
        business_outbound_messages_total.labels(
            provider=dispatch_result.provider_name,
            delivery_mode="manual_operator_send",
            outcome="accepted",
        ).inc()
        message = await self._runtime_state.record_outbound_message(
            account_id=account_id,
            conversation_id=conversation_id,
            recipient_id=conversation.customer_id,
            text=delivered_text,
            language_code=target_language if translated else source_language,
            translated_text=payload.text if translated else None,
            translated_language_code=source_language if translated else None,
            delivery_mode="manual_operator_send",
            ai_generated=False,
            payload={
                "operator_text": payload.text,
                "delivered_text": delivered_text,
                "source_language": source_language,
                "target_language": target_language,
                "translated": translated,
                "waba_id": provider_waba_id,
                "phone_number_id": provider_phone_number_id,
                "agent_id": payload.agent_id,
                "provider": dispatch_result.provider_name,
                "provider_message_id": dispatch_result.provider_message_id,
                "provider_accepted": dispatch_result.accepted,
            },
            sent_by_agent_id=sent_by_agent_id,
            provider_message_id=dispatch_result.provider_message_id,
        )
        self._runtime_state.add_audit_log(
            account_id=account_id,
            actor_type=actor_type,
            actor_id=actor_id,
            action="manual_outbound_message_sent",
            target_type="conversation",
            target_id=conversation_id,
            payload={
                "message_id": message.id,
                "provider": dispatch_result.provider_name,
                "provider_message_id": dispatch_result.provider_message_id,
                "source_language": source_language,
                "target_language": target_language,
                "translated": translated,
                "waba_id": provider_waba_id,
                "phone_number_id": provider_phone_number_id,
            },
        )
        self._runtime_state.commit()
        return OutboundMessageResponse(
            conversation_id=conversation_id,
            account_id=account_id,
            waba_id=provider_waba_id,
            phone_number_id=provider_phone_number_id,
            original_text=payload.text,
            delivered_text=delivered_text,
            source_language=source_language,
            target_language=target_language,
            translated=translated,
            message_id=message.id,
            provider=self._messaging_provider.provider_name,
            provider_message_id=dispatch_result.provider_message_id,
        )

    @staticmethod
    def _resolve_phone_number_waba_id(phone_number: object | None) -> str | None:
        if phone_number is None:
            return None
        snapshot_waba_id = getattr(phone_number, "waba_id", None)
        if isinstance(snapshot_waba_id, str) and snapshot_waba_id:
            return snapshot_waba_id
        waba_account = getattr(phone_number, "waba_account", None)
        if waba_account is None:
            return None
        waba_id = getattr(waba_account, "waba_id", None)
        if isinstance(waba_id, str) and waba_id:
            return waba_id
        return None

    async def _ensure_conversation_view_translations(
        self,
        *,
        account_id: str,
        conversation_id: str,
    ) -> None:
        """批量翻译对话中所有未翻译的入站消息和 AI 外文回复（单次 AI 请求）。

        合并为一次 LLM 调用，AI 返回结构化 JSON 后拆分，减少 token 和请求数。
        """
        messages = await self._runtime_state.list_message_models(
            account_id=account_id,
            conversation_id=conversation_id,
        )

        # 筛选需要翻译的消息：入站 + 所有出站消息（包含坐席手动发送的外文）
        # batch_translate_conversation_view 内部会跳过同语言（中文→中文）
        to_translate: list[Message] = []
        for message in messages:
            if not message.content_text:
                continue
            if message.direction == "inbound":
                pass  # 入站消息需要翻译
            elif message.direction == "outbound":
                pass  # 所有出站消息（AI生成 + 坐席手动发送）都需要翻译
            else:
                continue
            if message.translated_text and message.translated_language_code:
                continue  # 已有译文，跳过
            to_translate.append(message)

        if not to_translate:
            return

        # 批量翻译：合并为单次 AI 请求
        texts = [m.content_text for m in to_translate]
        source_languages: list[str] = []
        for m in to_translate:
            src = m.language_code or self._translation_service.detect_language(m.content_text)
            source_languages.append(src)

        results = await self._translation_service.batch_translate_conversation_view(
            texts=texts,
            source_languages=source_languages,
            force=True,
        )

        translated_any = False
        for i, msg in enumerate(to_translate):
            translated_text, translated_language, translated = (
                results[i] if i < len(results) else (None, None, False)
            )
            if not translated:
                continue
            msg.translated_text = translated_text
            msg.translated_language_code = translated_language
            self._runtime_state.session.add(msg)
            translated_any = True

        if translated_any:
            self._runtime_state.commit()

    async def translate_message(
        self,
        *,
        account_id: str,
        conversation_id: str,
        message_id: str,
        scope_actor: RequestActor | None = None,
    ) -> dict[str, str | None]:
        """翻译单条消息并持久化。返回 {translated_text, translated_language_code}。"""
        await self._ensure_conversation_scope(
            account_id=account_id,
            conversation_id=conversation_id,
            scope_actor=scope_actor,
        )
        messages = await self._runtime_state.list_message_models(
            account_id=account_id,
            conversation_id=conversation_id,
        )
        target: Message | None = None
        for m in messages:
            if m.id == message_id:
                target = m
                break
        if target is None:
            raise ValueError(f"Message {message_id} not found")
        if not target.content_text:
            return {"translated_text": None, "translated_language_code": None}

        source_language = target.language_code or self._translation_service.detect_language(
            target.content_text
        )
        translated_text, translated_language, translated = (
            await self._translation_service.translate_conversation_view(
                text=target.content_text,
                source_language=source_language,
                force=True,
            )
        )
        if translated and translated_text:
            target.translated_text = translated_text
            target.translated_language_code = translated_language
            self._runtime_state.session.add(target)
            self._runtime_state.commit()

        return {
            "translated_text": translated_text,
            "translated_language_code": translated_language,
        }

    async def batch_translate_messages(
        self,
        *,
        account_id: str,
        conversation_id: str,
        scope_actor: RequestActor | None = None,
    ) -> dict:
        """批量翻译对话中所有未翻译的入站消息和 AI 外文回复。返回 {count, translations}。"""
        await self._ensure_conversation_scope(
            account_id=account_id,
            conversation_id=conversation_id,
            scope_actor=scope_actor,
        )
        await self._ensure_conversation_view_translations(
            account_id=account_id,
            conversation_id=conversation_id,
        )
        # 重新加载以便获取最新翻译结果
        messages = await self._runtime_state.list_message_models(
            account_id=account_id,
            conversation_id=conversation_id,
        )
        translations: dict[str, str] = {}
        for m in messages:
            if m.translated_text:
                translations[m.id] = m.translated_text
        return {"count": len(translations), "translations": translations}

    async def translate_outbound_preview(
        self,
        *,
        text: str,
        target_language: str,
    ) -> dict:
        """翻译发送预览：翻译文本为指定语言（不持久化）。

        Returns {original_text, translated_text, source_language, target_language, was_translated}。
        """
        source_language = self._translation_service.detect_language(text=text)
        original_text, translated_text, was_translated = (
            await self._translation_service.translate_outbound_preview(
                text=text,
                source_language=source_language,
                target_language=target_language,
            )
        )
        return {
            "original_text": original_text,
            "translated_text": translated_text,
            "source_language": source_language,
            "target_language": target_language,
            "was_translated": was_translated,
        }

    def _serialize_message_view(self, message: Message) -> ConversationMessageView:
        original_text = self._get_message_primary_text(message)
        translated_text = self._get_message_auxiliary_text(message)
        return ConversationMessageView(
            message_id=message.id,
            waba_id=self._resolve_message_waba_id(message),
            phone_number_id=self._resolve_message_phone_number_id(message),
            provider_message_id=message.provider_message_id,
            provider_media_id=self._resolve_message_provider_media_id(message),
            direction=message.direction,
            message_type=message.message_type,
            language_code=message.language_code,
            translated_language_code=self._get_message_auxiliary_language(message),
            original_text=original_text,
            translated_text=translated_text,
            console_text=original_text,
            delivered_text=message.content_text if message.direction == "outbound" else None,
            translation_kind=self._get_message_translation_kind(message),
            sender_id=message.sender_id,
            recipient_id=message.recipient_id,
            ai_generated=message.ai_generated,
            created_at=_fmt_utc(message.created_at),
            payload=message.payload,
        )

    def _resolve_message_waba_id(self, message: Message) -> str | None:
        payload = message.payload if isinstance(message.payload, dict) else None
        if payload is not None:
            result = self._pick_nested_payload_text(payload, "waba_id")
            if result:
                return result
        # Fallback to conversation-level scope (loaded once in list_message_models)
        return self._runtime_state.conv_waba_id

    def _resolve_message_phone_number_id(self, message: Message) -> str | None:
        payload = message.payload if isinstance(message.payload, dict) else None
        if payload is not None:
            result = self._pick_nested_payload_text(payload, "phone_number_id")
            if result:
                return result
        # Fallback to conversation-level scope (loaded once in list_message_models)
        return self._runtime_state.conv_phone_number_id

    def _resolve_message_provider_media_id(self, message: Message) -> str | None:
        payload = message.payload if isinstance(message.payload, dict) else None
        if payload is None:
            return None
        return self._pick_nested_payload_text(payload, "provider_media_id", "media_id")

    def _get_message_primary_text(self, message: Message | None) -> str | None:
        if message is None:
            return None
        if message.direction == "outbound":
            payload = message.payload or {}
            outbound_source_text = self._pick_payload_text(payload, "operator_text", "operator_caption")
            if outbound_source_text:
                return outbound_source_text
        return message.content_text

    def _get_message_auxiliary_text(self, message: Message) -> str | None:
        if message.direction == "outbound":
            payload = message.payload or {}
            if payload.get("translated") is True:
                delivered_text = self._pick_payload_text(payload, "delivered_text", "delivered_caption")
                return delivered_text or message.content_text
            return message.translated_text
        return message.translated_text

    def _get_message_auxiliary_language(self, message: Message) -> str | None:
        if message.direction == "outbound":
            payload = message.payload or {}
            if payload.get("translated") is True:
                return message.language_code
        return message.translated_language_code

    def _get_message_translation_kind(self, message: Message) -> str | None:
        if message.direction == "outbound":
            payload = message.payload or {}
            if payload.get("translated") is True:
                return "outbound_operator_translation"
        if message.translated_text:
            return "conversation_view_translation"
        return None

    @staticmethod
    def _pick_payload_text(payload: dict[str, object], *keys: str) -> str | None:
        for key in keys:
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value
        return None

    @classmethod
    def _pick_nested_payload_text(cls, payload: dict[str, object], *keys: str) -> str | None:
        direct_value = cls._pick_payload_text(payload, *keys)
        if direct_value is not None:
            return direct_value
        for candidate_key in ("metadata", "provider_payload", "raw_payload"):
            candidate = payload.get(candidate_key)
            if not isinstance(candidate, dict):
                continue
            nested_value = cls._pick_nested_payload_text(candidate, *keys)
            if nested_value is not None:
                return nested_value
        return None

    def _ensure_agent_can_reply(
        self,
        conversation: object,
        agent_id: str | None,
    ) -> None:
        if agent_id is None:
            return
        management_mode = str(getattr(conversation, "management_mode"))
        assigned_agent = getattr(conversation, "assigned_agent", None)
        assigned_agent_id = self._runtime_state.get_public_agent_id(
            assigned_agent,
            fallback=getattr(conversation, "assigned_agent_id"),
        )
        if management_mode not in {"human_managed", "paused"}:
            raise PermissionError(
                "Manual operator replies require the conversation to be in human_managed or paused mode."
            )
        if assigned_agent_id != agent_id:
            raise PermissionError(
                f"Agent '{agent_id}' cannot reply to this conversation; it is assigned to '{assigned_agent_id}'."
            )

    def _serialize_audit_timeline_item(self, item: object) -> ConversationTimelineItem:
        action = getattr(item, "action")
        payload = getattr(item, "payload")
        actor_type = getattr(item, "actor_type")
        actor_id = getattr(item, "actor_id")
        title = action
        summary_parts = [f"actor {actor_id or actor_type}"]
        if isinstance(payload, dict):
            if payload.get("route_name") is not None:
                summary_parts.append(f"route={payload['route_name']}")
            if payload.get("intent_name") is not None:
                summary_parts.append(f"intent={payload['intent_name']}")
            if payload.get("handover_reason") is not None:
                summary_parts.append(str(payload["handover_reason"]))
        return ConversationTimelineItem(
            id=getattr(item, "id"),
            item_type="audit",
            label="audit",
            title=title,
            summary=" / ".join(summary_parts),
            actor_type=actor_type,
            actor_id=actor_id,
            created_at=_fmt_utc(getattr(item, "created_at")),
            payload=payload,
        )

    def _serialize_handover_timeline_item(self, item: object) -> ConversationTimelineItem:
        from_mode = getattr(item, "from_mode") or "unknown"
        to_mode = getattr(item, "to_mode")
        reason = getattr(item, "reason")
        triggered_by_type = getattr(item, "triggered_by_type")
        triggered_by_id = getattr(item, "triggered_by_id")
        return ConversationTimelineItem(
            id=getattr(item, "id"),
            item_type="handover",
            label="handover",
            title=f"{from_mode} -> {to_mode}",
            summary=(
                f"by {triggered_by_id or triggered_by_type}"
                + (f" / {reason}" if reason else "")
            ),
            actor_type=triggered_by_type,
            actor_id=triggered_by_id,
            created_at=_fmt_utc(getattr(item, "created_at")),
            payload={
                "from_mode": from_mode,
                "to_mode": to_mode,
                "reason": reason,
            },
        )

    def _serialize_message_event_timeline_item(self, item: object) -> ConversationTimelineItem:
        payload = getattr(item, "payload")
        event_type = getattr(item, "event_type")
        summary_parts = []
        if isinstance(payload, dict):
            if payload.get("job_id") is not None:
                summary_parts.append(f"job={payload['job_id']}")
            if payload.get("queue") is not None:
                summary_parts.append(f"queue={payload['queue']}")
            if payload.get("intent_name") is not None:
                summary_parts.append(f"intent={payload['intent_name']}")
            if payload.get("handover_reason") is not None:
                summary_parts.append(str(payload["handover_reason"]))
            if payload.get("delivery_mode") is not None:
                summary_parts.append(f"delivery={payload['delivery_mode']}")
            if payload.get("external_status") is not None:
                summary_parts.append(f"status={payload['external_status']}")
            if payload.get("provider_message_id") is not None:
                summary_parts.append(f"message={payload['provider_message_id']}")
            if payload.get("error_code") is not None:
                summary_parts.append(f"error={payload['error_code']}")
        return ConversationTimelineItem(
            id=getattr(item, "id"),
            item_type="message_event",
            label="event",
            title=event_type,
            summary=" / ".join(summary_parts) if summary_parts else "conversation event",
            created_at=_fmt_utc(getattr(item, "created_at")),
            payload=payload,
        )

    # ── B-01: Message search ──
    async def search_messages(
        self,
        account_id: str,
        conversation_id: str,
        q: str,
        limit: int = 50,
        offset: int = 0,
        scope_actor: RequestActor | None = None,
    ) -> list[ConversationMessageView]:
        """搜索当前会话消息的 content_text 和 translated_text（ILIKE），返回匹配消息列表，支持分页。"""
        from sqlalchemy import select, or_

        await self._ensure_conversation_scope(
            account_id=account_id,
            conversation_id=conversation_id,
            scope_actor=scope_actor,
        )
        conversation = self._runtime_state._require_conversation(
            account_id=account_id, conversation_id=conversation_id
        )
        stmt = (
            select(Message)
            .where(
                Message.conversation_id == conversation.id,
                or_(
                    Message.content_text.ilike(f"%{q}%"),
                    Message.translated_text.ilike(f"%{q}%"),
                ),
            )
            .order_by(Message.created_at.desc(), Message.id.desc())
            .offset(offset)
            .limit(limit)
        )
        messages = self._runtime_state.session.scalars(stmt).all()
        messages = list(reversed(messages))
        return [self._serialize_message_view(msg) for msg in messages]

    # ── B-02: Customer conversations ──
    async def list_customer_conversations(
        self,
        account_id: str,
        customer_id: str,
        exclude_conversation_id: str | None = None,
        limit: int = 20,
        scope_actor: RequestActor | None = None,
    ) -> list[dict[str, object]]:
        """查询同 customer_id 的所有会话，按 last_message_at 倒序。"""
        from sqlalchemy import select
        from app.services.data_scope_filter_service import DataScopeFilterService

        stmt = (
            select(Conversation)
            .where(
                Conversation.account_id == account_id,
                Conversation.customer_id == customer_id,
            )
            .order_by(Conversation.last_message_at.desc().nulls_last())
        )
        if scope_actor is not None:
            stmt = DataScopeFilterService(self._runtime_state.session).filter_conversations(stmt, scope_actor)
        if exclude_conversation_id:
            stmt = stmt.where(
                Conversation.external_conversation_id != exclude_conversation_id
            )
        rows = self._runtime_state.session.scalars(stmt.limit(limit)).all()

        results: list[dict[str, object]] = []
        for conv in rows:
            messages = await self._runtime_state.list_message_models(
                account_id=conv.account_id,
                conversation_id=conv.external_conversation_id,
                offset=0,
                limit=1,
            )
            last_preview: str | None = None
            if messages:
                last_preview = self._get_message_primary_text(messages[0])
            results.append({
                "conversation_id": conv.external_conversation_id,
                "account_id": conv.account_id,
                "customer_id": conv.customer_id,
                "status": conv.status,
                "management_mode": conv.management_mode,
                "last_message_at": _fmt_utc(conv.last_message_at) if conv.last_message_at else None,
                "last_message_preview": last_preview,
            })
        return results

    # ── B-03: Forward message ──
    async def forward_message(
        self,
        account_id: str,
        conversation_id: str,
        message_id: str,
        target_conversation_id: str,
        include_context: bool = False,
        actor_type: str = "system",
        actor_id: str | None = None,
        scope_actor: RequestActor | None = None,
    ) -> dict[str, str]:
        """将一条消息转发到目标会话，作为 outbound 消息写入。"""
        messages = await self._runtime_state.list_message_models(
            account_id=account_id,
            conversation_id=conversation_id,
        )
        await self._ensure_conversation_scope(
            account_id=account_id,
            conversation_id=conversation_id,
            scope_actor=scope_actor,
        )
        await self._ensure_conversation_scope(
            account_id=account_id,
            conversation_id=target_conversation_id,
            scope_actor=scope_actor,
        )
        source_message: Message | None = None
        for m in messages:
            if m.id == message_id:
                source_message = m
                break
        if source_message is None:
            raise LookupError(f"Message '{message_id}' not found in conversation '{conversation_id}'.")
        if not source_message.content_text:
            raise ValueError("Cannot forward a message without text content.")

        from sqlalchemy import select

        target_conv = self._runtime_state.session.execute(
            select(Conversation).where(
                Conversation.account_id == account_id,
                Conversation.external_conversation_id == target_conversation_id,
            )
        ).scalar_one_or_none()
        if target_conv is None:
            raise LookupError(
                f"Target conversation '{target_conversation_id}' not found for account '{account_id}'."
            )

        forward_text = source_message.content_text
        if include_context:
            forward_text = f"[Forwarded] {forward_text}"

        new_msg_id = str(uuid4())
        message = Message(
            id=new_msg_id,
            account_id=account_id,
            conversation_id=target_conv.id,
            direction="outbound",
            message_type="text",
            content_text=forward_text,
            ai_generated=False,
            payload={
                "forwarded_from_conversation_id": conversation_id,
                "forwarded_from_message_id": message_id,
                "include_context": include_context,
            },
        )
        self._runtime_state.session.add(message)
        self._runtime_state.add_audit_log(
            account_id=account_id,
            actor_type=actor_type,
            actor_id=actor_id,
            action="message.forward",
            target_type="conversation",
            target_id=target_conversation_id,
            payload={
                "new_message_id": new_msg_id,
                "source_conversation_id": conversation_id,
                "source_message_id": message_id,
            },
        )
        self._runtime_state.commit()
        return {"message_id": new_msg_id, "target_conversation_id": target_conversation_id}

    # ── B-04: Sentiment analysis ──
    async def get_sentiment(
        self,
        account_id: str,
        conversation_id: str,
        scope_actor: RequestActor | None = None,
    ) -> dict[str, object]:
        """取最近 20 条入站消息，调用 AI 分析情绪。"""
        await self._ensure_conversation_scope(
            account_id=account_id,
            conversation_id=conversation_id,
            scope_actor=scope_actor,
        )
        messages = await self._runtime_state.list_message_models(
            account_id=account_id,
            conversation_id=conversation_id,
        )
        inbound_texts: list[str] = []
        for m in messages:
            if m.direction == "inbound" and m.content_text:
                inbound_texts.append(m.content_text)
        recent_texts = inbound_texts[-20:]

        if not recent_texts:
            return {
                "sentiment": "neutral",
                "confidence": 0.5,
                "summary": "没有入站消息可供分析。",
            }

        combined_text = "\n---\n".join(recent_texts)
        prompt = (
            "分析以下客服对话中客户的情绪，返回JSON格式 "
            '{"sentiment":"...","confidence":0.0-1.0,"summary":"简述"}。'
            "sentiment必须是以下之一: angry, anxious, satisfied, neutral。"
            "\n\n对话: " + combined_text
        )

        await self._ensure_conversation_scope(
            account_id=account_id,
            conversation_id=conversation_id,
            scope_actor=scope_actor,
        )
        try:
            ai_provider = get_ai_provider(self._settings, account_id=account_id)
            if ai_provider.provider_name == "mock":
                raise RuntimeError("AI provider unavailable (mock).")

            request = AIReplyRequest(
                account_id=account_id,
                conversation_id=conversation_id,
                customer_language="zh-CN",
                user_message=prompt,
                conversation_history=[],
            )
            raw = await ai_provider.generate_reply(request)
            result = self._extract_sentiment_json(raw)
            return result
        except Exception as exc:
            return {
                "sentiment": "neutral",
                "confidence": 0.0,
                "summary": f"情绪分析失败: {str(exc)}",
            }

    @staticmethod
    def _extract_sentiment_json(raw: str) -> dict[str, object]:
        """从 AI 回复中提取 JSON，处理可能的 markdown 包装。"""
        text = raw.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1]) if len(lines) >= 3 else text
            text = text.strip()
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            import re
            match = re.search(r"\{[^{}]*\}", text)
            if match:
                try:
                    data = json.loads(match.group())
                except json.JSONDecodeError:
                    return {"sentiment": "neutral", "confidence": 0.0, "summary": "无法解析情绪分析结果。"}
            else:
                return {"sentiment": "neutral", "confidence": 0.0, "summary": "无法解析情绪分析结果。"}
        return {
            "sentiment": data.get("sentiment", "neutral"),
            "confidence": float(data.get("confidence", 0.0)),
            "summary": str(data.get("summary", "")),
        }

    # ── B-05: SLA ──
    async def get_sla(
        self,
        account_id: str,
        conversation_id: str,
        scope_actor: RequestActor | None = None,
    ) -> dict[str, object]:
        """计算等待时间、SLA 状态。"""
        await self._ensure_conversation_scope(
            account_id=account_id,
            conversation_id=conversation_id,
            scope_actor=scope_actor,
        )
        messages = await self._runtime_state.list_message_models(
            account_id=account_id,
            conversation_id=conversation_id,
        )

        last_inbound_at: str | None = None
        last_agent_reply_at: str | None = None
        waiting_seconds: int = 0

        for m in reversed(messages):
            if m.direction == "inbound" and m.content_text:
                last_inbound_at = _fmt_utc(m.created_at)
                delta = datetime.now(timezone.utc).replace(tzinfo=None) - m.created_at
                waiting_seconds = max(0, int(delta.total_seconds()))
                break

        for m in reversed(messages):
            if m.direction == "outbound" and not m.ai_generated:
                last_agent_reply_at = _fmt_utc(m.created_at)
                break

        warning = self._settings.sla_warning_seconds
        critical = self._settings.sla_critical_seconds

        return {
            "waiting_seconds": waiting_seconds,
            "threshold_warning": warning,
            "threshold_critical": critical,
            "is_overdue": waiting_seconds > critical,
            "last_inbound_at": last_inbound_at,
            "last_agent_reply_at": last_agent_reply_at,
        }

    # ── B-06: AI reply preview ──
    async def preview_ai_reply(
        self,
        account_id: str,
        conversation_id: str,
        scope_actor: RequestActor | None = None,
    ) -> dict[str, object]:
        """取最近 10 条消息作为上下文，调用 AI 生成拟回复（不存储）。"""
        try:
            ai_provider = get_ai_provider(self._settings, account_id=account_id)
            if ai_provider.provider_name == "mock":
                return {
                    "preview_text": "",
                    "prompt_tokens": 0,
                    "error": "AI 不可用 (mock provider)",
                }

            messages = await self._runtime_state.list_message_models(
                account_id=account_id,
                conversation_id=conversation_id,
            )

            recent = messages[-10:] if len(messages) > 10 else messages

            history: list[AIConversationTurn] = []
            customer_language = "zh-CN"
            last_inbound_text = ""
            for m in recent:
                role = "customer" if m.direction == "inbound" else "agent"
                text = m.content_text or ""
                lang = m.language_code or ""
                history.append(AIConversationTurn(role=role, text=text, language_code=lang))
                if m.direction == "inbound" and text:
                    last_inbound_text = text
                    if lang:
                        customer_language = lang

            if not last_inbound_text:
                return {
                    "preview_text": "",
                    "prompt_tokens": 0,
                    "error": "没有入站消息可供生成回复。",
                }

            request = AIReplyRequest(
                account_id=account_id,
                conversation_id=conversation_id,
                customer_language=customer_language,
                user_message=last_inbound_text,
                conversation_history=history[:-1],
            )
            preview_text = await ai_provider.generate_reply(request)

            total_chars = sum(len(t.text) for t in history) + len(preview_text)
            estimated_tokens = max(1, total_chars // 4)

            return {
                "preview_text": preview_text,
                "prompt_tokens": estimated_tokens,
            }
        except Exception as exc:
            return {
                "preview_text": "",
                "prompt_tokens": 0,
                "error": f"AI 回复预览失败: {str(exc)}",
            }
