from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Conversation,
    Message,
    MessageEvent,
    WhatsAppBusinessAccount,
    WhatsAppConversationStat,
    WhatsAppDailyStat,
    WhatsAppPhoneNumber,
)
from app.services.whatsapp_analytics_service import WhatsAppAnalyticsService


@dataclass(frozen=True, slots=True)
class _ConversationStatScope:
    date: date
    account_id: str
    conversation_id: str
    customer_id: str
    waba_id: str | None
    phone_number_id: str | None
    conversation_origin_type: str | None
    conversation_category: str | None
    pricing_model: str | None
    billable: bool
    billable_key: str | None
    hour_bucket: int | None


@dataclass(frozen=True, slots=True)
class _DailyStatScope:
    date: date
    account_id: str
    waba_id: str | None
    phone_number_id: str | None
    conversation_origin_type: str | None
    conversation_category: str | None
    pricing_model: str | None
    billable: bool
    hour_bucket: int | None


class WhatsAppStatsAggregator:
    def __init__(self, session: Session) -> None:
        self._session = session

    def record_message_created(
        self,
        *,
        message: Message,
        conversation: Conversation | None = None,
    ) -> None:
        scope = self._build_message_scope(message=message, conversation=conversation)
        if scope is None:
            return

        row = self._get_or_create_fact_row(scope)
        if message.direction == "inbound":
            row.inbound_message_count += 1
        else:
            row.outbound_message_count += 1
        self._session.add(row)
        self._session.flush()
        self._recompute_daily_row(self._to_daily_scope(scope))

    def record_status_event(
        self,
        *,
        event: MessageEvent,
        message: Message | None = None,
        conversation: Conversation | None = None,
    ) -> None:
        if not event.event_type.startswith("whatsapp_status_"):
            return

        scope = self._build_status_scope(
            event=event,
            message=message,
            conversation=conversation,
        )
        if scope is None:
            return

        row = self._get_or_create_fact_row(scope)
        if event.event_type.endswith("delivered"):
            row.delivered_count += 1
        elif event.event_type.endswith("read"):
            row.read_count += 1
        elif event.event_type.endswith("failed"):
            row.failed_count += 1

        if scope.billable:
            row.billable_count = max(row.billable_count, 1)
            estimated_cost = Decimal(
                str(WhatsAppAnalyticsService._extract_estimated_cost(event.payload))
            )
            if estimated_cost > Decimal(row.estimated_cost or 0):
                row.estimated_cost = estimated_cost

        self._session.add(row)
        self._session.flush()
        self._recompute_daily_row(self._to_daily_scope(scope))

    def reclassify_message_dimensions(
        self,
        *,
        message: Message,
        previous_payload: dict[str, object] | None,
        conversation: Conversation | None = None,
    ) -> None:
        if message.direction != "outbound":
            return

        previous_scope = self._build_message_scope_from_payload(
            message=message,
            conversation=conversation,
            payload=previous_payload,
        )
        current_scope = self._build_message_scope(message=message, conversation=conversation)
        if previous_scope is None or current_scope is None or previous_scope == current_scope:
            return

        previous_row = self._find_fact_row(previous_scope)
        if previous_row is not None and previous_row.outbound_message_count > 0:
            previous_row.outbound_message_count -= 1
            if self._fact_row_is_empty(previous_row):
                self._session.delete(previous_row)
            else:
                self._session.add(previous_row)
            self._session.flush()
            self._recompute_daily_row(self._to_daily_scope(previous_scope))

        current_row = self._get_or_create_fact_row(current_scope)
        current_row.outbound_message_count += 1
        self._session.add(current_row)
        self._session.flush()
        self._recompute_daily_row(self._to_daily_scope(current_scope))

    def _build_message_scope(
        self,
        *,
        message: Message,
        conversation: Conversation | None,
    ) -> _ConversationStatScope | None:
        return self._build_message_scope_from_payload(
            message=message,
            conversation=conversation,
            payload=message.payload if isinstance(message.payload, dict) else None,
        )

    def _build_message_scope_from_payload(
        self,
        *,
        message: Message,
        conversation: Conversation | None,
        payload: dict[str, object] | None,
    ) -> _ConversationStatScope | None:
        resolved_conversation = conversation or message.conversation
        if resolved_conversation is None:
            resolved_conversation = self._session.get(Conversation, message.conversation_id)
        if resolved_conversation is None:
            return None

        phone_number = self._resolve_phone_number(
            phone_number_id=message.phone_number_id or resolved_conversation.phone_number_id,
            loaded_phone_number=message.phone_number or resolved_conversation.phone_number,
        )
        conversation_origin_type, conversation_category, pricing_model, billable = (
            WhatsAppAnalyticsService._extract_dimensions(payload=payload)
        )
        occurred_at = message.created_at
        resolved_waba_id = self._resolve_waba_id(
            phone_number=phone_number,
            payload=payload,
        )
        resolved_phone_number_id = self._resolve_provider_phone_number_id(
            phone_number=phone_number,
            payload=payload,
        )
        if resolved_waba_id is None and resolved_phone_number_id is None:
            return None
        return _ConversationStatScope(
            date=occurred_at.date(),
            account_id=message.account_id,
            conversation_id=resolved_conversation.id,
            customer_id=resolved_conversation.customer_id,
            waba_id=resolved_waba_id,
            phone_number_id=resolved_phone_number_id,
            conversation_origin_type=conversation_origin_type,
            conversation_category=conversation_category,
            pricing_model=pricing_model,
            billable=billable,
            billable_key=None,
            hour_bucket=occurred_at.hour,
        )

    def _find_fact_row(self, scope: _ConversationStatScope) -> WhatsAppConversationStat | None:
        return self._session.scalars(
            select(WhatsAppConversationStat).where(
                WhatsAppConversationStat.date == scope.date,
                WhatsAppConversationStat.account_id == scope.account_id,
                WhatsAppConversationStat.conversation_id == scope.conversation_id,
                WhatsAppConversationStat.waba_id == scope.waba_id,
                WhatsAppConversationStat.phone_number_id == scope.phone_number_id,
                WhatsAppConversationStat.conversation_origin_type == scope.conversation_origin_type,
                WhatsAppConversationStat.conversation_category == scope.conversation_category,
                WhatsAppConversationStat.pricing_model == scope.pricing_model,
                WhatsAppConversationStat.billable == scope.billable,
                WhatsAppConversationStat.billable_key == scope.billable_key,
                WhatsAppConversationStat.hour_bucket == scope.hour_bucket,
            )
        ).first()

    @staticmethod
    def _fact_row_is_empty(row: WhatsAppConversationStat) -> bool:
        return (
            row.inbound_message_count <= 0
            and row.outbound_message_count <= 0
            and row.delivered_count <= 0
            and row.read_count <= 0
            and row.failed_count <= 0
            and row.billable_count <= 0
            and Decimal(row.estimated_cost or 0) <= 0
        )

    def _build_status_scope(
        self,
        *,
        event: MessageEvent,
        message: Message | None,
        conversation: Conversation | None,
    ) -> _ConversationStatScope | None:
        resolved_message = message or event.message
        resolved_conversation = conversation or event.conversation
        if resolved_message is not None and resolved_conversation is None:
            resolved_conversation = resolved_message.conversation
        if resolved_conversation is None and event.conversation_id is not None:
            resolved_conversation = self._session.get(Conversation, event.conversation_id)
        if resolved_conversation is None:
            return None

        phone_number = self._resolve_phone_number(
            phone_number_id=(
                resolved_message.phone_number_id
                if resolved_message is not None and resolved_message.phone_number_id is not None
                else resolved_conversation.phone_number_id
            ),
            loaded_phone_number=(
                resolved_message.phone_number
                if resolved_message is not None and resolved_message.phone_number is not None
                else resolved_conversation.phone_number
            ),
        )
        occurred_at = (
            WhatsAppAnalyticsService._parse_event_occurred_at(event.payload) or event.created_at
        )
        conversation_origin_type, conversation_category, pricing_model, billable = (
            WhatsAppAnalyticsService._extract_dimensions(payload=event.payload)
        )
        resolved_waba_id = self._resolve_waba_id(
            phone_number=phone_number,
            payload=event.payload if isinstance(event.payload, dict) else None,
            event_waba_id=event.waba_id,
        )
        resolved_phone_number_id = self._resolve_provider_phone_number_id(
            phone_number=phone_number,
            payload=event.payload if isinstance(event.payload, dict) else None,
            event_phone_number_id=event.phone_number_id,
        )
        if resolved_waba_id is None and resolved_phone_number_id is None:
            return None
        billable_key = None
        if billable:
            billable_key = WhatsAppAnalyticsService._build_billing_key(
                event=event,
                message=resolved_message,
                conversation=resolved_conversation,
            )
        return _ConversationStatScope(
            date=occurred_at.date(),
            account_id=event.account_id,
            conversation_id=resolved_conversation.id,
            customer_id=resolved_conversation.customer_id,
            waba_id=resolved_waba_id,
            phone_number_id=resolved_phone_number_id,
            conversation_origin_type=conversation_origin_type,
            conversation_category=conversation_category,
            pricing_model=pricing_model,
            billable=billable,
            billable_key=billable_key,
            hour_bucket=occurred_at.hour,
        )

    def _get_or_create_fact_row(self, scope: _ConversationStatScope) -> WhatsAppConversationStat:
        row = self._session.scalars(
            select(WhatsAppConversationStat).where(
                WhatsAppConversationStat.date == scope.date,
                WhatsAppConversationStat.account_id == scope.account_id,
                WhatsAppConversationStat.conversation_id == scope.conversation_id,
                WhatsAppConversationStat.waba_id == scope.waba_id,
                WhatsAppConversationStat.phone_number_id == scope.phone_number_id,
                WhatsAppConversationStat.conversation_origin_type == scope.conversation_origin_type,
                WhatsAppConversationStat.conversation_category == scope.conversation_category,
                WhatsAppConversationStat.pricing_model == scope.pricing_model,
                WhatsAppConversationStat.billable == scope.billable,
                WhatsAppConversationStat.billable_key == scope.billable_key,
                WhatsAppConversationStat.hour_bucket == scope.hour_bucket,
            )
        ).first()
        if row is not None:
            return row

        row = WhatsAppConversationStat(
            date=scope.date,
            account_id=scope.account_id,
            conversation_id=scope.conversation_id,
            customer_id=scope.customer_id,
            waba_id=scope.waba_id,
            phone_number_id=scope.phone_number_id,
            conversation_origin_type=scope.conversation_origin_type,
            conversation_category=scope.conversation_category,
            pricing_model=scope.pricing_model,
            billable=scope.billable,
            billable_key=scope.billable_key,
            inbound_message_count=0,
            outbound_message_count=0,
            delivered_count=0,
            read_count=0,
            failed_count=0,
            billable_count=0,
            estimated_cost=Decimal("0"),
            hour_bucket=scope.hour_bucket,
        )
        self._session.add(row)
        self._session.flush()
        return row

    def _recompute_daily_row(self, scope: _DailyStatScope) -> None:
        fact_rows = self._session.scalars(
            select(WhatsAppConversationStat).where(
                WhatsAppConversationStat.date == scope.date,
                WhatsAppConversationStat.account_id == scope.account_id,
                WhatsAppConversationStat.waba_id == scope.waba_id,
                WhatsAppConversationStat.phone_number_id == scope.phone_number_id,
                WhatsAppConversationStat.conversation_origin_type == scope.conversation_origin_type,
                WhatsAppConversationStat.conversation_category == scope.conversation_category,
                WhatsAppConversationStat.pricing_model == scope.pricing_model,
                WhatsAppConversationStat.billable == scope.billable,
                WhatsAppConversationStat.hour_bucket == scope.hour_bucket,
            )
        ).all()
        row = self._session.scalars(
            select(WhatsAppDailyStat).where(
                WhatsAppDailyStat.date == scope.date,
                WhatsAppDailyStat.account_id == scope.account_id,
                WhatsAppDailyStat.waba_id == scope.waba_id,
                WhatsAppDailyStat.phone_number_id == scope.phone_number_id,
                WhatsAppDailyStat.conversation_origin_type == scope.conversation_origin_type,
                WhatsAppDailyStat.conversation_category == scope.conversation_category,
                WhatsAppDailyStat.pricing_model == scope.pricing_model,
                WhatsAppDailyStat.billable == scope.billable,
                WhatsAppDailyStat.hour_bucket == scope.hour_bucket,
            )
        ).first()

        if not fact_rows:
            if row is not None:
                self._session.delete(row)
            return

        inbound_message_count = sum(item.inbound_message_count for item in fact_rows)
        outbound_message_count = sum(item.outbound_message_count for item in fact_rows)
        delivered_count = sum(item.delivered_count for item in fact_rows)
        read_count = sum(item.read_count for item in fact_rows)
        failed_count = sum(item.failed_count for item in fact_rows)
        conversation_ids = {item.conversation_id for item in fact_rows}
        customer_ids = {item.customer_id for item in fact_rows}
        billable_keys = {
            item.billable_key or f"conversation:{item.conversation_id}"
            for item in fact_rows
            if item.billable_count > 0
        }
        estimated_cost_by_key: dict[str, Decimal] = {}
        for item in fact_rows:
            if item.billable_count <= 0:
                continue
            key = item.billable_key or f"conversation:{item.conversation_id}"
            estimated_cost_by_key[key] = max(
                estimated_cost_by_key.get(key, Decimal("0")),
                Decimal(item.estimated_cost or 0),
            )

        if row is None:
            row = WhatsAppDailyStat(
                date=scope.date,
                account_id=scope.account_id,
                waba_id=scope.waba_id,
                phone_number_id=scope.phone_number_id,
                conversation_origin_type=scope.conversation_origin_type,
                conversation_category=scope.conversation_category,
                pricing_model=scope.pricing_model,
                billable=scope.billable,
                hour_bucket=scope.hour_bucket,
            )

        row.inbound_message_count = inbound_message_count
        row.outbound_message_count = outbound_message_count
        row.delivered_count = delivered_count
        row.read_count = read_count
        row.failed_count = failed_count
        row.billable_count = len(billable_keys)
        row.conversation_count = len(conversation_ids)
        row.unique_customer_count = len(customer_ids)
        row.estimated_cost = sum(estimated_cost_by_key.values(), start=Decimal("0"))
        self._session.add(row)

    @staticmethod
    def _to_daily_scope(scope: _ConversationStatScope) -> _DailyStatScope:
        return _DailyStatScope(
            date=scope.date,
            account_id=scope.account_id,
            waba_id=scope.waba_id,
            phone_number_id=scope.phone_number_id,
            conversation_origin_type=scope.conversation_origin_type,
            conversation_category=scope.conversation_category,
            pricing_model=scope.pricing_model,
            billable=scope.billable,
            hour_bucket=scope.hour_bucket,
        )

    def _resolve_phone_number(
        self,
        *,
        phone_number_id: str | None,
        loaded_phone_number: WhatsAppPhoneNumber | None,
    ) -> WhatsAppPhoneNumber | None:
        if loaded_phone_number is not None:
            return loaded_phone_number
        if phone_number_id is None:
            return None
        return self._session.get(WhatsAppPhoneNumber, phone_number_id)

    def _resolve_waba_id(
        self,
        *,
        phone_number: WhatsAppPhoneNumber | None,
        payload: dict[str, object] | None,
        event_waba_id: str | None = None,
    ) -> str | None:
        resolved_waba_id = WhatsAppAnalyticsService._first_non_empty_str(
            event_waba_id,
            WhatsAppAnalyticsService._extract_nested_payload_string(payload, "waba_id"),
            phone_number.waba_id if phone_number is not None else None,
        )
        if resolved_waba_id is not None:
            return resolved_waba_id
        if phone_number is None:
            return None
        if phone_number.waba_account is not None:
            return phone_number.waba_account.waba_id
        waba_account = self._session.get(WhatsAppBusinessAccount, phone_number.waba_account_id)
        return waba_account.waba_id if waba_account is not None else None

    @staticmethod
    def _resolve_provider_phone_number_id(
        *,
        phone_number: WhatsAppPhoneNumber | None,
        payload: dict[str, object] | None,
        event_phone_number_id: str | None = None,
    ) -> str | None:
        return WhatsAppAnalyticsService._first_non_empty_str(
            event_phone_number_id,
            WhatsAppAnalyticsService._extract_payload_phone_number_id(payload),
            phone_number.phone_number_id if phone_number is not None else None,
        )
