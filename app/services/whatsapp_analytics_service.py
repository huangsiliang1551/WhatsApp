from datetime import UTC, date, datetime, time
from decimal import Decimal

from sqlalchemy import and_, delete, or_, select
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.sql.elements import ColumnElement

from app.db.models import (
    Conversation,
    Message,
    MessageEvent,
    WhatsAppBusinessAccount,
    WhatsAppConversationStat,
    WhatsAppDailyStat,
    WhatsAppPhoneNumber,
)
from app.schemas.whatsapp_analytics import (
    WhatsAppStatsDailyRow,
    WhatsAppStatsDetailResponse,
    WhatsAppStatsSummary,
)


class WhatsAppAnalyticsService:
    def __init__(self, session: Session) -> None:
        self._session = session

    async def get_summary(
        self,
        *,
        account_id: str | None,
        waba_id: str | None,
        phone_number_id: str | None,
        conversation_origin_type: str | None,
        conversation_category: str | None,
        pricing_model: str | None,
        billable: bool | None,
        hour_bucket: int | None,
        date_from: str | None,
        date_to: str | None,
        allowed_account_ids: set[str] | None,
    ) -> WhatsAppStatsSummary:
        self._validate_scope_filters(
            account_id=account_id,
            waba_id=waba_id,
            phone_number_id=phone_number_id,
            allowed_account_ids=allowed_account_ids,
        )
        start_date, end_date = self._normalize_date_window(date_from=date_from, date_to=date_to)
        fact_rows = self._load_fact_rows(
            account_id=account_id,
            waba_id=waba_id,
            phone_number_id=phone_number_id,
            conversation_origin_type=conversation_origin_type,
            conversation_category=conversation_category,
            pricing_model=pricing_model,
            billable=billable,
            hour_bucket=hour_bucket,
            allowed_account_ids=allowed_account_ids,
            start_date=start_date,
            end_date=end_date,
        )
        return self._build_summary_from_facts(fact_rows)

    async def list_daily_stats(
        self,
        *,
        account_id: str | None,
        waba_id: str | None,
        phone_number_id: str | None,
        conversation_origin_type: str | None,
        conversation_category: str | None,
        pricing_model: str | None,
        billable: bool | None,
        hour_bucket: int | None,
        date_from: str | None,
        date_to: str | None,
        allowed_account_ids: set[str] | None,
    ) -> list[WhatsAppStatsDailyRow]:
        self._validate_scope_filters(
            account_id=account_id,
            waba_id=waba_id,
            phone_number_id=phone_number_id,
            allowed_account_ids=allowed_account_ids,
        )
        start_date, end_date = self._normalize_date_window(date_from=date_from, date_to=date_to)
        rows = self._load_daily_rows(
            account_id=account_id,
            waba_id=waba_id,
            phone_number_id=phone_number_id,
            conversation_origin_type=conversation_origin_type,
            conversation_category=conversation_category,
            pricing_model=pricing_model,
            billable=billable,
            hour_bucket=hour_bucket,
            allowed_account_ids=allowed_account_ids,
            start_date=start_date,
            end_date=end_date,
        )
        return [self._serialize_row(item) for item in rows]

    async def get_detail(
        self,
        *,
        account_id: str | None,
        waba_id: str | None,
        phone_number_id: str | None,
        conversation_origin_type: str | None,
        conversation_category: str | None,
        pricing_model: str | None,
        billable: bool | None,
        hour_bucket: int | None,
        date_from: str | None,
        date_to: str | None,
        allowed_account_ids: set[str] | None,
    ) -> WhatsAppStatsDetailResponse:
        self._validate_scope_filters(
            account_id=account_id,
            waba_id=waba_id,
            phone_number_id=phone_number_id,
            allowed_account_ids=allowed_account_ids,
        )
        start_date, end_date = self._normalize_date_window(date_from=date_from, date_to=date_to)
        rows = self._load_daily_rows(
            account_id=account_id,
            waba_id=waba_id,
            phone_number_id=phone_number_id,
            conversation_origin_type=conversation_origin_type,
            conversation_category=conversation_category,
            pricing_model=pricing_model,
            billable=billable,
            hour_bucket=hour_bucket,
            allowed_account_ids=allowed_account_ids,
            start_date=start_date,
            end_date=end_date,
        )
        return WhatsAppStatsDetailResponse(
            summary=self._build_summary_from_facts(
                self._load_fact_rows(
                    account_id=account_id,
                    waba_id=waba_id,
                    phone_number_id=phone_number_id,
                    conversation_origin_type=conversation_origin_type,
                    conversation_category=conversation_category,
                    pricing_model=pricing_model,
                    billable=billable,
                    hour_bucket=hour_bucket,
                    allowed_account_ids=allowed_account_ids,
                    start_date=start_date,
                    end_date=end_date,
                )
            ),
            daily_rows=[self._serialize_row(item) for item in rows],
            generated_at=self._resolve_generated_at(rows).isoformat(),
        )

    def _validate_scope_filters(
        self,
        *,
        account_id: str | None,
        waba_id: str | None,
        phone_number_id: str | None,
        allowed_account_ids: set[str] | None,
    ) -> None:
        self._validate_account_waba_scope(
            account_id=account_id,
            waba_id=waba_id,
            allowed_account_ids=allowed_account_ids,
        )
        if phone_number_id is None:
            return

        phone_number = self._find_current_phone_number(
            phone_number_id=phone_number_id,
            allowed_account_ids=allowed_account_ids,
        )
        if phone_number is None:
            if account_id is None and waba_id is None:
                raise LookupError(f"Phone-Number-ID '{phone_number_id}' was not found.")
            return

        if account_id is not None and phone_number.account_id != account_id:
            raise ValueError(
                f"Phone-Number-ID '{phone_number_id}' belongs to account '{phone_number.account_id}', "
                f"not '{account_id}'."
            )

        if waba_id is None:
            return

        resolved_waba_id = self._resolve_phone_waba_id(phone_number)
        if resolved_waba_id is None or resolved_waba_id == waba_id:
            return
        requested_account_id = account_id or phone_number.account_id
        requested_waba = self._session.scalars(
            select(WhatsAppBusinessAccount)
            .options(selectinload(WhatsAppBusinessAccount.phone_numbers))
            .where(
                WhatsAppBusinessAccount.account_id == requested_account_id,
                WhatsAppBusinessAccount.waba_id == waba_id,
            )
        ).first()
        if requested_waba is not None and any(
            item.phone_number_id == phone_number_id for item in requested_waba.phone_numbers
        ):
            return
        if (
            requested_waba is not None
            and not requested_waba.phone_numbers
            and self._has_historical_scope(
                account_id=requested_account_id,
                waba_id=resolved_waba_id,
                phone_number_id=phone_number_id,
            )
        ):
            return
        if self._has_historical_scope(
            account_id=requested_account_id,
            waba_id=waba_id,
            phone_number_id=phone_number_id,
        ):
            return
        raise ValueError(
            f"Phone-Number-ID '{phone_number_id}' belongs to WABA '{resolved_waba_id}', "
            f"not '{waba_id}'."
        )

    def _validate_account_waba_scope(
        self,
        *,
        account_id: str | None,
        waba_id: str | None,
        allowed_account_ids: set[str] | None,
    ) -> None:
        if account_id is None or waba_id is None:
            return

        current_waba = self._session.scalars(
            select(WhatsAppBusinessAccount).where(
                WhatsAppBusinessAccount.account_id == account_id,
                WhatsAppBusinessAccount.waba_id == waba_id,
            )
        ).first()
        if current_waba is not None:
            return

        if self._has_historical_waba_scope(account_id=account_id, waba_id=waba_id):
            return

        owner_query = select(WhatsAppBusinessAccount.account_id).where(
            WhatsAppBusinessAccount.waba_id == waba_id
        )
        if allowed_account_ids is not None:
            owner_query = owner_query.where(
                WhatsAppBusinessAccount.account_id.in_(allowed_account_ids)
            )
        owner_account_id = self._session.execute(owner_query.limit(1)).scalar_one_or_none()
        if owner_account_id is not None and owner_account_id != account_id:
            raise ValueError(
                f"WABA '{waba_id}' belongs to account '{owner_account_id}', not '{account_id}'."
            )

    def _find_current_phone_number(
        self,
        *,
        phone_number_id: str,
        allowed_account_ids: set[str] | None,
    ) -> WhatsAppPhoneNumber | None:
        query = (
            select(WhatsAppPhoneNumber)
            .options(selectinload(WhatsAppPhoneNumber.waba_account))
            .where(WhatsAppPhoneNumber.phone_number_id == phone_number_id)
        )
        if allowed_account_ids is not None:
            query = query.where(WhatsAppPhoneNumber.account_id.in_(allowed_account_ids))
        return self._session.scalars(query).first()

    def _has_historical_scope(
        self,
        *,
        account_id: str,
        waba_id: str,
        phone_number_id: str,
    ) -> bool:
        if self._session.scalars(
            select(WhatsAppDailyStat)
            .where(
                WhatsAppDailyStat.account_id == account_id,
                WhatsAppDailyStat.waba_id == waba_id,
                WhatsAppDailyStat.phone_number_id == phone_number_id,
            )
            .limit(1)
        ).first() is not None:
            return True
        if self._session.scalars(
            select(WhatsAppConversationStat)
            .where(
                WhatsAppConversationStat.account_id == account_id,
                WhatsAppConversationStat.waba_id == waba_id,
                WhatsAppConversationStat.phone_number_id == phone_number_id,
            )
            .limit(1)
        ).first() is not None:
            return True
        message_payloads = self._session.execute(
            select(Message.payload).where(Message.account_id == account_id)
        ).scalars()
        for payload in message_payloads:
            if not isinstance(payload, dict):
                continue
            if (
                self._extract_nested_payload_string(payload, "waba_id") == waba_id
                and self._extract_payload_phone_number_id(payload) == phone_number_id
            ):
                return True
        event_rows = self._session.execute(
            select(MessageEvent.waba_id, MessageEvent.phone_number_id, MessageEvent.payload).where(
                MessageEvent.account_id == account_id,
                MessageEvent.event_type.like("whatsapp_status_%"),
            )
        ).all()
        for event_waba_id, event_phone_number_id, payload in event_rows:
            row_waba_id, row_phone_number_id = self._resolve_scope_identifiers(
                payload=payload if isinstance(payload, dict) else None,
                phone_number=None,
                event_waba_id=event_waba_id,
                event_phone_number_id=event_phone_number_id,
            )
            if row_waba_id == waba_id and row_phone_number_id == phone_number_id:
                return True
        return False

    def _has_historical_waba_scope(
        self,
        *,
        account_id: str,
        waba_id: str,
    ) -> bool:
        if self._session.scalars(
            select(WhatsAppDailyStat)
            .where(
                WhatsAppDailyStat.account_id == account_id,
                WhatsAppDailyStat.waba_id == waba_id,
            )
            .limit(1)
        ).first() is not None:
            return True
        if self._session.scalars(
            select(WhatsAppConversationStat)
            .where(
                WhatsAppConversationStat.account_id == account_id,
                WhatsAppConversationStat.waba_id == waba_id,
            )
            .limit(1)
        ).first() is not None:
            return True
        message_payloads = self._session.execute(
            select(Message.payload).where(Message.account_id == account_id)
        ).scalars()
        for payload in message_payloads:
            if (
                isinstance(payload, dict)
                and self._extract_nested_payload_string(payload, "waba_id") == waba_id
            ):
                return True
        event_rows = self._session.execute(
            select(MessageEvent.waba_id, MessageEvent.payload).where(
                MessageEvent.account_id == account_id,
                MessageEvent.event_type.like("whatsapp_status_%"),
            )
        ).all()
        for event_waba_id, payload in event_rows:
            row_waba_id, _ = self._resolve_scope_identifiers(
                payload=payload if isinstance(payload, dict) else None,
                phone_number=None,
                event_waba_id=event_waba_id,
                event_phone_number_id=None,
            )
            if row_waba_id == waba_id:
                return True
        return False

    def _load_fact_rows(
        self,
        *,
        account_id: str | None,
        waba_id: str | None,
        phone_number_id: str | None,
        conversation_origin_type: str | None,
        conversation_category: str | None,
        pricing_model: str | None,
        billable: bool | None,
        hour_bucket: int | None,
        allowed_account_ids: set[str] | None,
        start_date: date | None,
        end_date: date | None,
    ) -> list[WhatsAppConversationStat]:
        query = select(WhatsAppConversationStat)
        query = self._apply_fact_filters(
            query=query,
            account_id=account_id,
            waba_id=waba_id,
            phone_number_id=phone_number_id,
            conversation_origin_type=conversation_origin_type,
            conversation_category=conversation_category,
            pricing_model=pricing_model,
            billable=billable,
            hour_bucket=hour_bucket,
            start_date=start_date,
            end_date=end_date,
            allowed_account_ids=allowed_account_ids,
        )
        return self._session.scalars(query).all()

    def _load_daily_rows(
        self,
        *,
        account_id: str | None,
        waba_id: str | None,
        phone_number_id: str | None,
        conversation_origin_type: str | None,
        conversation_category: str | None,
        pricing_model: str | None,
        billable: bool | None,
        hour_bucket: int | None,
        allowed_account_ids: set[str] | None,
        start_date: date | None,
        end_date: date | None,
    ) -> list[WhatsAppDailyStat]:
        query = select(WhatsAppDailyStat).order_by(
            WhatsAppDailyStat.date.desc(),
            WhatsAppDailyStat.hour_bucket.desc(),
            WhatsAppDailyStat.phone_number_id.asc(),
        )
        query = self._apply_row_filters(
            query=query,
            account_id=account_id,
            waba_id=waba_id,
            phone_number_id=phone_number_id,
            conversation_origin_type=conversation_origin_type,
            conversation_category=conversation_category,
            pricing_model=pricing_model,
            billable=billable,
            hour_bucket=hour_bucket,
            start_date=start_date,
            end_date=end_date,
            allowed_account_ids=allowed_account_ids,
        )
        return self._session.scalars(query).all()

    async def rebuild_stats(
        self,
        *,
        account_id: str | None,
        waba_id: str | None,
        phone_number_id: str | None,
        date_from: str | None,
        date_to: str | None,
        allowed_account_ids: set[str] | None,
    ) -> datetime:
        self._validate_scope_filters(
            account_id=account_id,
            waba_id=waba_id,
            phone_number_id=phone_number_id,
            allowed_account_ids=allowed_account_ids,
        )
        start_date, end_date = self._normalize_date_window(date_from=date_from, date_to=date_to)
        return await self._refresh_daily_stats(
            account_id=account_id,
            waba_id=waba_id,
            phone_number_id=phone_number_id,
            allowed_account_ids=allowed_account_ids,
            start_date=start_date,
            end_date=end_date,
        )

    async def _refresh_daily_stats(
        self,
        *,
        account_id: str | None,
        waba_id: str | None,
        phone_number_id: str | None,
        allowed_account_ids: set[str] | None,
        start_date: date | None,
        end_date: date | None,
    ) -> datetime:
        messages, events = self._load_source_records(
            account_id=account_id,
            waba_id=waba_id,
            phone_number_id=phone_number_id,
            allowed_account_ids=allowed_account_ids,
            start_date=start_date,
            end_date=end_date,
        )

        daily_delete_stmt = delete(WhatsAppDailyStat)
        fact_delete_stmt = delete(WhatsAppConversationStat)
        if account_id is not None:
            daily_delete_stmt = daily_delete_stmt.where(WhatsAppDailyStat.account_id == account_id)
            fact_delete_stmt = fact_delete_stmt.where(WhatsAppConversationStat.account_id == account_id)
        elif allowed_account_ids is not None:
            daily_delete_stmt = daily_delete_stmt.where(WhatsAppDailyStat.account_id.in_(allowed_account_ids))
            fact_delete_stmt = fact_delete_stmt.where(
                WhatsAppConversationStat.account_id.in_(allowed_account_ids)
            )
        if waba_id is not None:
            daily_delete_stmt = daily_delete_stmt.where(WhatsAppDailyStat.waba_id == waba_id)
            fact_delete_stmt = fact_delete_stmt.where(WhatsAppConversationStat.waba_id == waba_id)
        if phone_number_id is not None:
            daily_delete_stmt = daily_delete_stmt.where(WhatsAppDailyStat.phone_number_id == phone_number_id)
            fact_delete_stmt = fact_delete_stmt.where(
                WhatsAppConversationStat.phone_number_id == phone_number_id
            )
        if start_date is not None:
            daily_delete_stmt = daily_delete_stmt.where(WhatsAppDailyStat.date >= start_date)
            fact_delete_stmt = fact_delete_stmt.where(WhatsAppConversationStat.date >= start_date)
        if end_date is not None:
            daily_delete_stmt = daily_delete_stmt.where(WhatsAppDailyStat.date <= end_date)
            fact_delete_stmt = fact_delete_stmt.where(WhatsAppConversationStat.date <= end_date)
        self._session.execute(daily_delete_stmt)
        self._session.execute(fact_delete_stmt)

        daily_aggregates: dict[
            tuple[str, date, str | None, str | None, str | None, str | None, str | None, bool, int | None],
            dict[str, int | float | Decimal | set[str]],
        ] = {}
        fact_aggregates: dict[
            tuple[
                str,
                date,
                str,
                str,
                str | None,
                str | None,
                str | None,
                str | None,
                str | None,
                bool,
                str | None,
                int | None,
            ],
            dict[str, int | float | Decimal | set[str]],
        ] = {}

        for message in messages:
            conversation = message.conversation
            if conversation is None:
                continue
            occurred_at = message.created_at
            occurred_date = occurred_at.date()
            if start_date is not None and occurred_date < start_date:
                continue
            if end_date is not None and occurred_date > end_date:
                continue
            event_scope_waba_id, event_scope_phone_number_id = self._extract_message_event_scope_identifiers(
                message
            )
            # Rebuilds must preserve rows whose historical payload never carried
            # explicit scope identifiers. Snapshot/event values still win when
            # present; relationship fallback is only a last resort.
            row_waba_id, row_phone_number_id = self._resolve_scope_identifiers(
                payload=message.payload if isinstance(message.payload, dict) else None,
                phone_number=message.phone_number,
                event_waba_id=event_scope_waba_id,
                event_phone_number_id=event_scope_phone_number_id,
                allow_waba_phone_relation_fallback=True,
                allow_phone_number_relation_fallback=True,
            )
            if row_waba_id is None and row_phone_number_id is None:
                continue
            if not self._matches_source_scope_filters(
                waba_id=waba_id,
                row_waba_id=row_waba_id,
                phone_number_id=phone_number_id,
                row_phone_number_id=row_phone_number_id,
            ):
                continue
            conversation_origin_type, conversation_category, pricing_model, billable = self._extract_dimensions(
                payload=message.payload,
            )
            daily_key = (
                message.account_id,
                occurred_date,
                row_waba_id,
                row_phone_number_id,
                conversation_origin_type,
                conversation_category,
                pricing_model,
                billable,
                occurred_at.hour,
            )
            fact_key = (
                message.account_id,
                occurred_date,
                conversation.id,
                conversation.customer_id,
                row_waba_id,
                row_phone_number_id,
                conversation_origin_type,
                conversation_category,
                pricing_model,
                billable,
                None,
                occurred_at.hour,
            )
            daily_current = daily_aggregates.setdefault(
                daily_key,
                self._empty_counter(),
            )
            fact_current = fact_aggregates.setdefault(fact_key, self._empty_fact_counter())
            if message.direction == "inbound":
                daily_current["inbound_message_count"] = int(daily_current["inbound_message_count"]) + 1
                fact_current["inbound_message_count"] = int(fact_current["inbound_message_count"]) + 1
            else:
                daily_current["outbound_message_count"] = int(daily_current["outbound_message_count"]) + 1
                fact_current["outbound_message_count"] = int(fact_current["outbound_message_count"]) + 1
            cast_conversation_ids = daily_current["conversation_ids"]
            if isinstance(cast_conversation_ids, set):
                cast_conversation_ids.add(conversation.id)
            cast_customer_ids = daily_current["customer_ids"]
            if isinstance(cast_customer_ids, set):
                cast_customer_ids.add(conversation.customer_id)

        for event in events:
            if not event.event_type.startswith("whatsapp_status_"):
                continue
            message = event.message
            conversation = event.conversation or (message.conversation if message is not None else None)
            if conversation is None:
                continue

            occurred_at = self._resolve_event_occurred_at(event)
            occurred_date = occurred_at.date()
            if start_date is not None and occurred_date < start_date:
                continue
            if end_date is not None and occurred_date > end_date:
                continue
            row_waba_id, row_phone_number_id = self._resolve_scope_identifiers(
                payload=event.payload if isinstance(event.payload, dict) else None,
                phone_number=message.phone_number if message is not None else None,
                event_waba_id=event.waba_id,
                event_phone_number_id=event.phone_number_id,
                allow_waba_phone_relation_fallback=True,
                allow_phone_number_relation_fallback=True,
            )
            if row_waba_id is None and row_phone_number_id is None:
                continue
            if not self._matches_source_scope_filters(
                waba_id=waba_id,
                row_waba_id=row_waba_id,
                phone_number_id=phone_number_id,
                row_phone_number_id=row_phone_number_id,
            ):
                continue
            conversation_origin_type, conversation_category, pricing_model, billable = self._extract_dimensions(
                payload=event.payload,
            )
            daily_key = (
                event.account_id,
                occurred_date,
                row_waba_id,
                row_phone_number_id,
                conversation_origin_type,
                conversation_category,
                pricing_model,
                billable,
                occurred_at.hour,
            )
            fact_key = (
                event.account_id,
                occurred_date,
                conversation.id,
                conversation.customer_id,
                row_waba_id,
                row_phone_number_id,
                conversation_origin_type,
                conversation_category,
                pricing_model,
                billable,
                (
                    self._build_billing_key(event=event, message=message, conversation=conversation)
                    if billable
                    else None
                ),
                occurred_at.hour,
            )
            daily_current = daily_aggregates.setdefault(daily_key, self._empty_counter())
            fact_current = fact_aggregates.setdefault(fact_key, self._empty_fact_counter())
            if event.event_type.endswith("delivered"):
                daily_current["delivered_count"] = int(daily_current["delivered_count"]) + 1
                fact_current["delivered_count"] = int(fact_current["delivered_count"]) + 1
            elif event.event_type.endswith("read"):
                daily_current["read_count"] = int(daily_current["read_count"]) + 1
                fact_current["read_count"] = int(fact_current["read_count"]) + 1
            elif event.event_type.endswith("failed"):
                daily_current["failed_count"] = int(daily_current["failed_count"]) + 1
                fact_current["failed_count"] = int(fact_current["failed_count"]) + 1
            if billable:
                billing_key = self._build_billing_key(event=event, message=message, conversation=conversation)
                cost_value = self._extract_estimated_cost(event.payload)
                self._register_billable_occurrence(
                    counter=daily_current,
                    billing_key=billing_key,
                    estimated_cost=cost_value,
                )
                self._register_billable_occurrence(
                    counter=fact_current,
                    billing_key=billing_key,
                    estimated_cost=cost_value,
                )
            cast_conversation_ids = daily_current["conversation_ids"]
            if isinstance(cast_conversation_ids, set):
                cast_conversation_ids.add(conversation.id)
            cast_customer_ids = daily_current["customer_ids"]
            if isinstance(cast_customer_ids, set):
                cast_customer_ids.add(conversation.customer_id)

        for key, counts in daily_aggregates.items():
            (
                aggregated_account_id,
                stat_date,
                waba_id,
                phone_number_id,
                conversation_origin_type,
                conversation_category,
                pricing_model,
                billable,
                hour_bucket,
            ) = key
            conversation_ids = counts.pop("conversation_ids")
            customer_ids = counts.pop("customer_ids")
            self._session.add(
                WhatsAppDailyStat(
                    date=stat_date,
                    account_id=aggregated_account_id,
                    waba_id=waba_id,
                    phone_number_id=phone_number_id,
                    conversation_origin_type=conversation_origin_type,
                    conversation_category=conversation_category,
                    pricing_model=pricing_model,
                    billable=billable,
                    inbound_message_count=int(counts["inbound_message_count"]),
                    outbound_message_count=int(counts["outbound_message_count"]),
                    delivered_count=int(counts["delivered_count"]),
                    read_count=int(counts["read_count"]),
                    failed_count=int(counts["failed_count"]),
                    billable_count=int(counts["billable_count"]),
                    conversation_count=len(conversation_ids) if isinstance(conversation_ids, set) else 0,
                    unique_customer_count=len(customer_ids) if isinstance(customer_ids, set) else 0,
                    estimated_cost=Decimal(str(counts["estimated_cost"])),
                    hour_bucket=hour_bucket,
                )
            )
        for key, counts in fact_aggregates.items():
            (
                aggregated_account_id,
                stat_date,
                conversation_id,
                customer_id,
                waba_id,
                phone_number_id,
                conversation_origin_type,
                conversation_category,
                pricing_model,
                billable,
                billable_key,
                hour_bucket,
            ) = key
            self._session.add(
                WhatsAppConversationStat(
                    date=stat_date,
                    account_id=aggregated_account_id,
                    conversation_id=conversation_id,
                    customer_id=customer_id,
                    waba_id=waba_id,
                    phone_number_id=phone_number_id,
                    conversation_origin_type=conversation_origin_type,
                    conversation_category=conversation_category,
                    pricing_model=pricing_model,
                    billable=billable,
                    billable_key=billable_key,
                    inbound_message_count=int(counts["inbound_message_count"]),
                    outbound_message_count=int(counts["outbound_message_count"]),
                    delivered_count=int(counts["delivered_count"]),
                    read_count=int(counts["read_count"]),
                    failed_count=int(counts["failed_count"]),
                    billable_count=int(counts["billable_count"]),
                    estimated_cost=Decimal(str(counts["estimated_cost"])),
                    hour_bucket=hour_bucket,
                )
            )
        self._session.commit()
        return datetime.now(UTC).replace(tzinfo=None)

    def _build_summary_from_source(
        self,
        *,
        account_id: str | None,
        waba_id: str | None,
        phone_number_id: str | None,
        conversation_origin_type: str | None,
        conversation_category: str | None,
        pricing_model: str | None,
        billable: bool | None,
        hour_bucket: int | None,
        date_from: date | None,
        date_to: date | None,
        allowed_account_ids: set[str] | None,
    ) -> WhatsAppStatsSummary:
        messages, events = self._load_source_records(
            account_id=account_id,
            waba_id=waba_id,
            phone_number_id=phone_number_id,
            allowed_account_ids=allowed_account_ids,
            start_date=date_from,
            end_date=date_to,
        )
        conversation_ids: set[str] = set()
        customer_ids: set[str] = set()
        inbound_message_count = 0
        outbound_message_count = 0
        delivered_count = 0
        read_count = 0
        failed_count = 0
        billable_count = 0
        estimated_cost = 0.0
        billable_keys_seen: set[str] = set()
        costed_billable_keys_seen: set[str] = set()

        for message in messages:
            conversation = message.conversation
            if conversation is None:
                continue
            occurred_at = message.created_at
            occurred_date = occurred_at.date()
            if date_from is not None and occurred_date < date_from:
                continue
            if date_to is not None and occurred_date > date_to:
                continue
            message_origin_type, message_category, message_pricing_model, message_billable = (
                self._extract_dimensions(payload=message.payload)
            )
            event_scope_waba_id, event_scope_phone_number_id = self._extract_message_event_scope_identifiers(
                message
            )
            row_waba_id, row_phone_number_id = self._resolve_scope_identifiers(
                payload=message.payload if isinstance(message.payload, dict) else None,
                phone_number=message.phone_number,
                event_waba_id=event_scope_waba_id,
                event_phone_number_id=event_scope_phone_number_id,
                allow_waba_phone_relation_fallback=False,
                allow_phone_number_relation_fallback=False,
            )
            if row_waba_id is None and row_phone_number_id is None:
                continue
            if not self._matches_source_filters(
                waba_id=waba_id,
                row_waba_id=row_waba_id,
                phone_number_id=phone_number_id,
                row_phone_number_id=row_phone_number_id,
                conversation_origin_type=conversation_origin_type,
                row_conversation_origin_type=message_origin_type,
                conversation_category=conversation_category,
                row_conversation_category=message_category,
                pricing_model=pricing_model,
                row_pricing_model=message_pricing_model,
                billable=billable,
                row_billable=message_billable,
                hour_bucket=hour_bucket,
                row_hour_bucket=occurred_at.hour,
            ):
                continue
            if message.direction == "inbound":
                inbound_message_count += 1
            else:
                outbound_message_count += 1
            conversation_ids.add(conversation.id)
            customer_ids.add(conversation.customer_id)

        for event in events:
            if not event.event_type.startswith("whatsapp_status_"):
                continue
            message = event.message
            conversation = event.conversation or (message.conversation if message is not None else None)
            if conversation is None:
                continue
            occurred_at = self._resolve_event_occurred_at(event)
            occurred_date = occurred_at.date()
            if date_from is not None and occurred_date < date_from:
                continue
            if date_to is not None and occurred_date > date_to:
                continue
            event_origin_type, event_category, event_pricing_model, event_billable = self._extract_dimensions(
                payload=event.payload,
            )
            row_waba_id, row_phone_number_id = self._resolve_scope_identifiers(
                payload=event.payload if isinstance(event.payload, dict) else None,
                phone_number=message.phone_number if message is not None else None,
                event_waba_id=event.waba_id,
                event_phone_number_id=event.phone_number_id,
                allow_waba_phone_relation_fallback=False,
            )
            if row_waba_id is None and row_phone_number_id is None:
                continue
            if not self._matches_source_filters(
                waba_id=waba_id,
                row_waba_id=row_waba_id,
                phone_number_id=phone_number_id,
                row_phone_number_id=row_phone_number_id,
                conversation_origin_type=conversation_origin_type,
                row_conversation_origin_type=event_origin_type,
                conversation_category=conversation_category,
                row_conversation_category=event_category,
                pricing_model=pricing_model,
                row_pricing_model=event_pricing_model,
                billable=billable,
                row_billable=event_billable,
                hour_bucket=hour_bucket,
                row_hour_bucket=occurred_at.hour,
            ):
                continue
            if event.event_type.endswith("delivered"):
                delivered_count += 1
            elif event.event_type.endswith("read"):
                read_count += 1
            elif event.event_type.endswith("failed"):
                failed_count += 1
            if event_billable:
                billing_key = self._build_billing_key(event=event, message=message, conversation=conversation)
                if billing_key not in billable_keys_seen:
                    billable_keys_seen.add(billing_key)
                    billable_count += 1
                event_cost = self._extract_estimated_cost(event.payload)
                if event_cost > 0 and billing_key not in costed_billable_keys_seen:
                    costed_billable_keys_seen.add(billing_key)
                    estimated_cost += event_cost
            conversation_ids.add(conversation.id)
            customer_ids.add(conversation.customer_id)

        estimated_cost_status, estimated_cost_note = self._describe_estimated_cost(
            billable_count=billable_count,
            estimated_cost=estimated_cost,
            costed_billable_count=len(costed_billable_keys_seen),
        )
        return WhatsAppStatsSummary(
            conversation_count=len(conversation_ids),
            unique_customer_count=len(customer_ids),
            inbound_message_count=inbound_message_count,
            outbound_message_count=outbound_message_count,
            delivered_count=delivered_count,
            read_count=read_count,
            failed_count=failed_count,
            billable_count=billable_count,
            estimated_cost=estimated_cost,
            estimated_cost_status=estimated_cost_status,
            estimated_cost_note=estimated_cost_note,
        )

    def _build_summary_from_facts(
        self,
        rows: list[WhatsAppConversationStat],
    ) -> WhatsAppStatsSummary:
        conversation_ids = {item.conversation_id for item in rows}
        customer_ids = {item.customer_id for item in rows}
        inbound_message_count = sum(item.inbound_message_count for item in rows)
        outbound_message_count = sum(item.outbound_message_count for item in rows)
        delivered_count = sum(item.delivered_count for item in rows)
        read_count = sum(item.read_count for item in rows)
        failed_count = sum(item.failed_count for item in rows)
        billable_keys = {
            item.billable_key or f"conversation:{item.conversation_id}"
            for item in rows
            if item.billable_count > 0
        }
        estimated_cost_by_key: dict[str, float] = {}
        for item in rows:
            if item.billable_count <= 0:
                continue
            key = item.billable_key or f"conversation:{item.conversation_id}"
            estimated_cost_by_key[key] = max(
                estimated_cost_by_key.get(key, 0.0),
                float(item.estimated_cost or 0),
            )
        costed_billable_keys = {
            item.billable_key or f"conversation:{item.conversation_id}"
            for item in rows
            if item.billable_count > 0 and float(item.estimated_cost or 0) > 0
        }
        billable_count = len(billable_keys)
        costed_billable_count = len(costed_billable_keys)
        estimated_cost = sum(estimated_cost_by_key.values())
        estimated_cost_status, estimated_cost_note = self._describe_estimated_cost(
            billable_count=billable_count,
            estimated_cost=estimated_cost,
            costed_billable_count=costed_billable_count,
        )
        return WhatsAppStatsSummary(
            conversation_count=len(conversation_ids),
            unique_customer_count=len(customer_ids),
            inbound_message_count=inbound_message_count,
            outbound_message_count=outbound_message_count,
            delivered_count=delivered_count,
            read_count=read_count,
            failed_count=failed_count,
            billable_count=billable_count,
            estimated_cost=estimated_cost,
            estimated_cost_status=estimated_cost_status,
            estimated_cost_note=estimated_cost_note,
        )

    def _load_source_records(
        self,
        *,
        account_id: str | None,
        waba_id: str | None,
        phone_number_id: str | None,
        allowed_account_ids: set[str] | None,
        start_date: date | None,
        end_date: date | None,
    ) -> tuple[list[Message], list[MessageEvent]]:
        messages_query = (
            select(Message)
            .options(
                selectinload(Message.conversation)
                .selectinload(Conversation.phone_number)
                .selectinload(WhatsAppPhoneNumber.waba_account),
                selectinload(Message.phone_number).selectinload(WhatsAppPhoneNumber.waba_account),
                selectinload(Message.events),
            )
            .order_by(Message.created_at.desc(), Message.id.desc())
        )
        events_query = (
            select(MessageEvent)
            .options(
                selectinload(MessageEvent.conversation)
                .selectinload(Conversation.phone_number)
                .selectinload(WhatsAppPhoneNumber.waba_account),
                selectinload(MessageEvent.message)
                .selectinload(Message.phone_number)
                .selectinload(WhatsAppPhoneNumber.waba_account),
            )
            .order_by(MessageEvent.created_at.desc(), MessageEvent.id.desc())
        )
        if account_id is not None:
            messages_query = messages_query.where(Message.account_id == account_id)
            events_query = events_query.where(MessageEvent.account_id == account_id)
        elif allowed_account_ids is not None:
            messages_query = messages_query.where(Message.account_id.in_(allowed_account_ids))
            events_query = events_query.where(MessageEvent.account_id.in_(allowed_account_ids))
        if start_date is not None:
            messages_query = messages_query.where(Message.created_at >= datetime.combine(start_date, time.min))
        if end_date is not None:
            messages_query = messages_query.where(Message.created_at <= datetime.combine(end_date, time.max))
        events_query = events_query.where(MessageEvent.event_type.like("whatsapp_status_%"))
        start_at = datetime.combine(start_date, time.min) if start_date is not None else None
        end_at = datetime.combine(end_date, time.max) if end_date is not None else None
        if start_at is not None or end_at is not None:
            events_query = events_query.where(
                self._build_event_time_window_clause(start_at=start_at, end_at=end_at)
            )
        if waba_id is not None:
            events_query = events_query.where(
                or_(MessageEvent.waba_id == waba_id, MessageEvent.waba_id.is_(None))
            )
        if phone_number_id is not None:
            events_query = events_query.where(
                or_(
                    MessageEvent.phone_number_id == phone_number_id,
                    MessageEvent.phone_number_id.is_(None),
                )
            )

        return self._session.scalars(messages_query).all(), self._session.scalars(events_query).all()

    @staticmethod
    def _build_event_time_window_clause(
        *,
        start_at: datetime | None,
        end_at: datetime | None,
    ) -> ColumnElement[bool]:
        occurred_window_clauses: list[ColumnElement[bool]] = [MessageEvent.occurred_at.is_not(None)]
        if start_at is not None:
            occurred_window_clauses.append(MessageEvent.occurred_at >= start_at)
        if end_at is not None:
            occurred_window_clauses.append(MessageEvent.occurred_at <= end_at)
        occurred_window = and_(*occurred_window_clauses)
        return or_(MessageEvent.occurred_at.is_(None), occurred_window)

    @staticmethod
    def _resolve_event_occurred_at(event: MessageEvent) -> datetime:
        return event.occurred_at or WhatsAppAnalyticsService._parse_event_occurred_at(event.payload) or event.created_at

    @staticmethod
    def _resolve_generated_at(rows: list[WhatsAppDailyStat]) -> datetime:
        if not rows:
            return datetime.now(UTC).replace(tzinfo=None)
        return max(item.updated_at for item in rows)

    @staticmethod
    def _empty_counter() -> dict[str, int | float | Decimal | set[str]]:
        return {
            "conversation_ids": set(),
            "customer_ids": set(),
            "billable_keys": set(),
            "costed_billable_keys": set(),
            "inbound_message_count": 0,
            "outbound_message_count": 0,
            "delivered_count": 0,
            "read_count": 0,
            "failed_count": 0,
            "billable_count": 0,
            "estimated_cost": 0.0,
        }

    @staticmethod
    def _empty_fact_counter() -> dict[str, int | float | Decimal | set[str]]:
        return {
            "billable_keys": set(),
            "costed_billable_keys": set(),
            "inbound_message_count": 0,
            "outbound_message_count": 0,
            "delivered_count": 0,
            "read_count": 0,
            "failed_count": 0,
            "billable_count": 0,
            "estimated_cost": 0.0,
        }

    @staticmethod
    def _build_billing_key(
        *,
        event: MessageEvent,
        message: Message | None,
        conversation: Conversation | None,
    ) -> str:
        if isinstance(event.payload, dict):
            provider_payload = event.payload.get("provider_payload")
            if isinstance(provider_payload, dict):
                provider_conversation_id = provider_payload.get("conversation_id")
                if isinstance(provider_conversation_id, str) and provider_conversation_id:
                    return f"conversation:{provider_conversation_id}"
                provider_conversation = provider_payload.get("conversation")
                if isinstance(provider_conversation, dict):
                    nested_provider_conversation_id = provider_conversation.get("id")
                    if (
                        isinstance(nested_provider_conversation_id, str)
                        and nested_provider_conversation_id
                    ):
                        return f"conversation:{nested_provider_conversation_id}"
            conversation_id = event.payload.get("conversation_id")
            if isinstance(conversation_id, str) and conversation_id:
                return f"conversation:{conversation_id}"
        if message is not None and message.provider_message_id:
            return f"provider_message:{message.provider_message_id}"
        if message is not None:
            return f"message:{message.id}"
        if conversation is not None:
            return f"conversation_local:{conversation.id}"
        return f"event:{event.id}"

    @staticmethod
    def _register_billable_occurrence(
        *,
        counter: dict[str, int | float | Decimal | set[str]],
        billing_key: str,
        estimated_cost: float,
    ) -> None:
        billable_keys = counter["billable_keys"]
        if isinstance(billable_keys, set) and billing_key not in billable_keys:
            billable_keys.add(billing_key)
            counter["billable_count"] = int(counter["billable_count"]) + 1

        costed_billable_keys = counter["costed_billable_keys"]
        if (
            estimated_cost > 0
            and isinstance(costed_billable_keys, set)
            and billing_key not in costed_billable_keys
        ):
            costed_billable_keys.add(billing_key)
            counter["estimated_cost"] = float(counter["estimated_cost"]) + estimated_cost

    @staticmethod
    def _extract_dimensions(
        *,
        payload: dict[str, object] | None,
    ) -> tuple[str | None, str | None, str | None, bool]:
        if not isinstance(payload, dict):
            return ("unknown", "unknown", "unknown", False)
        conversation_payload = payload.get("conversation")
        pricing_payload = payload.get("pricing")
        conversation = conversation_payload if isinstance(conversation_payload, dict) else {}
        pricing = pricing_payload if isinstance(pricing_payload, dict) else {}
        return (
            str(
                conversation.get("origin", {}).get("type")
                if isinstance(conversation.get("origin"), dict)
                else payload.get("conversation_origin_type") or "unknown"
            ),
            str(
                pricing.get("category")
                or conversation.get("category")
                or payload.get("conversation_category")
                or "unknown"
            ),
            str(pricing.get("pricing_model") or payload.get("pricing_model") or "unknown"),
            bool(pricing.get("billable") or payload.get("billable") or False),
        )

    @staticmethod
    def _parse_event_occurred_at(payload: dict[str, object] | None) -> datetime | None:
        if not isinstance(payload, dict):
            return None
        raw_value = payload.get("occurred_at") or payload.get("timestamp")
        if not isinstance(raw_value, str) or not raw_value:
            return None
        try:
            if raw_value.isdigit():
                return datetime.fromtimestamp(int(raw_value), UTC).replace(tzinfo=None)
            return datetime.fromisoformat(raw_value.replace("Z", "+00:00")).astimezone(UTC).replace(
                tzinfo=None
            )
        except ValueError:
            return None

    @staticmethod
    def _normalize_date_window(
        *,
        date_from: str | None,
        date_to: str | None,
    ) -> tuple[date | None, date | None]:
        start_date = datetime.fromisoformat(date_from).date() if date_from else None
        end_date = datetime.fromisoformat(date_to).date() if date_to else None
        if start_date is not None and end_date is not None and start_date > end_date:
            raise ValueError("date_from must be less than or equal to date_to.")
        return start_date, end_date

    def _serialize_row(self, row: WhatsAppDailyStat) -> WhatsAppStatsDailyRow:
        estimated_cost = float(row.estimated_cost or 0)
        estimated_cost_status, estimated_cost_note = self._describe_estimated_cost(
            billable_count=row.billable_count,
            estimated_cost=estimated_cost,
        )
        return WhatsAppStatsDailyRow(
            date=row.date.isoformat(),
            hour_bucket=row.hour_bucket,
            account_id=row.account_id,
            waba_id=row.waba_id,
            phone_number_id=row.phone_number_id,
            conversation_origin_type=row.conversation_origin_type,
            conversation_category=row.conversation_category,
            pricing_model=row.pricing_model,
            billable=row.billable,
            conversation_count=row.conversation_count,
            unique_customer_count=row.unique_customer_count,
            inbound_message_count=row.inbound_message_count,
            outbound_message_count=row.outbound_message_count,
            delivered_count=row.delivered_count,
            read_count=row.read_count,
            failed_count=row.failed_count,
            billable_count=row.billable_count,
            estimated_cost=estimated_cost,
            estimated_cost_status=estimated_cost_status,
            estimated_cost_note=estimated_cost_note,
        )

    @staticmethod
    def _matches_source_filters(
        *,
        waba_id: str | None,
        row_waba_id: str | None,
        phone_number_id: str | None,
        row_phone_number_id: str | None,
        conversation_origin_type: str | None,
        row_conversation_origin_type: str | None,
        conversation_category: str | None,
        row_conversation_category: str | None,
        pricing_model: str | None,
        row_pricing_model: str | None,
        billable: bool | None,
        row_billable: bool,
        hour_bucket: int | None,
        row_hour_bucket: int | None,
    ) -> bool:
        if waba_id is not None and row_waba_id != waba_id:
            return False
        if phone_number_id is not None and row_phone_number_id != phone_number_id:
            return False
        if conversation_origin_type is not None and row_conversation_origin_type != conversation_origin_type:
            return False
        if conversation_category is not None and row_conversation_category != conversation_category:
            return False
        if pricing_model is not None and row_pricing_model != pricing_model:
            return False
        if billable is not None and row_billable != billable:
            return False
        if hour_bucket is not None and row_hour_bucket != hour_bucket:
            return False
        return True

    @staticmethod
    def _matches_source_scope_filters(
        *,
        waba_id: str | None,
        row_waba_id: str | None,
        phone_number_id: str | None,
        row_phone_number_id: str | None,
    ) -> bool:
        if waba_id is not None and row_waba_id != waba_id:
            return False
        if phone_number_id is not None and row_phone_number_id != phone_number_id:
            return False
        return True

    @staticmethod
    def _resolve_phone_waba_id(phone_number: object | None) -> str | None:
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

    @classmethod
    def _extract_message_event_scope_identifiers(
        cls,
        message: Message,
    ) -> tuple[str | None, str | None]:
        for event in message.events:
            event_payload = event.payload if isinstance(event.payload, dict) else None
            row_waba_id = cls._first_non_empty_str(
                event.waba_id,
                cls._extract_nested_payload_string(event_payload, "waba_id"),
            )
            row_phone_number_id = cls._first_non_empty_str(
                event.phone_number_id,
                cls._extract_payload_phone_number_id(event_payload),
            )
            if row_waba_id is not None or row_phone_number_id is not None:
                return row_waba_id, row_phone_number_id
        return None, None

    @classmethod
    def _resolve_scope_identifiers(
        cls,
        *,
        payload: dict[str, object] | None,
        phone_number: object | None,
        event_waba_id: str | None = None,
        event_phone_number_id: str | None = None,
        allow_waba_phone_relation_fallback: bool = True,
        allow_phone_number_relation_fallback: bool = True,
    ) -> tuple[str | None, str | None]:
        row_waba_id = cls._first_non_empty_str(
            event_waba_id,
            cls._extract_nested_payload_string(payload, "waba_id"),
            cls._resolve_phone_waba_id(phone_number)
            if allow_waba_phone_relation_fallback
            else None,
        )
        row_phone_number_id = cls._first_non_empty_str(
            event_phone_number_id,
            cls._extract_payload_phone_number_id(payload),
            getattr(phone_number, "phone_number_id", None)
            if allow_phone_number_relation_fallback
            else None,
        )
        return row_waba_id, row_phone_number_id

    @staticmethod
    def _extract_payload_phone_number_id(payload: dict[str, object] | None) -> str | None:
        direct_phone_number_id = WhatsAppAnalyticsService._extract_nested_payload_string(
            payload,
            "phone_number_id",
        )
        if direct_phone_number_id is not None:
            return direct_phone_number_id
        if not isinstance(payload, dict):
            return None
        metadata = payload.get("metadata")
        if not isinstance(metadata, dict):
            return None
        return WhatsAppAnalyticsService._extract_payload_string(metadata, "phone_number_id")

    @staticmethod
    def _extract_payload_string(
        payload: dict[str, object] | None,
        key: str,
    ) -> str | None:
        if not isinstance(payload, dict):
            return None
        raw_value = payload.get(key)
        if isinstance(raw_value, str) and raw_value:
            return raw_value
        return None

    @classmethod
    def _extract_nested_payload_string(
        cls,
        payload: dict[str, object] | None,
        key: str,
    ) -> str | None:
        if not isinstance(payload, dict):
            return None
        direct_value = cls._extract_payload_string(payload, key)
        if direct_value is not None:
            return direct_value
        nested_candidates = (
            payload.get("metadata"),
            payload.get("provider_payload"),
            payload.get("raw_payload"),
        )
        for candidate in nested_candidates:
            if not isinstance(candidate, dict):
                continue
            nested_value = cls._extract_nested_payload_string(candidate, key)
            if nested_value is not None:
                return nested_value
        return None

    @staticmethod
    def _first_non_empty_str(*values: object | None) -> str | None:
        for value in values:
            if isinstance(value, str) and value:
                return value
        return None

    @staticmethod
    def _extract_estimated_cost(payload: dict[str, object] | None) -> float:
        if not isinstance(payload, dict):
            return 0.0
        raw_value = payload.get("estimated_cost")
        if isinstance(raw_value, (int, float)):
            return float(raw_value)
        if isinstance(raw_value, str):
            try:
                return float(raw_value)
            except ValueError:
                return 0.0
        return 0.0

    @staticmethod
    def _describe_estimated_cost(
        *,
        billable_count: int,
        estimated_cost: float,
        costed_billable_count: int | None = None,
    ) -> tuple[str, str | None]:
        if billable_count <= 0:
            return (
                "not_applicable",
                "当前筛选范围内没有 billable 会话，预估成本不适用。",
            )
        if estimated_cost <= 0:
            return (
                "missing_provider_cost",
                "存在 billable 会话，但 provider 没有返回 estimated_cost；当前 0 仅表示缺少费用回执。",
            )
        if costed_billable_count is not None and 0 < costed_billable_count < billable_count:
            return (
                "partial_provider_estimated",
                "仅部分 billable 会话带有 provider estimated_cost，当前成本为部分覆盖结果。",
            )
        return (
            "provider_estimated",
            "当前仅累计 provider 明确返回的 estimated_cost，不代表最终结算账单。",
        )

    @staticmethod
    def _apply_row_filters(
        *,
        query,
        account_id: str | None,
        waba_id: str | None,
        phone_number_id: str | None,
        conversation_origin_type: str | None,
        conversation_category: str | None,
        pricing_model: str | None,
        billable: bool | None,
        hour_bucket: int | None,
        start_date: date | None,
        end_date: date | None,
        allowed_account_ids: set[str] | None,
    ):
        if account_id is not None:
            query = query.where(WhatsAppDailyStat.account_id == account_id)
        elif allowed_account_ids is not None:
            query = query.where(WhatsAppDailyStat.account_id.in_(allowed_account_ids))
        if waba_id is not None:
            query = query.where(WhatsAppDailyStat.waba_id == waba_id)
        if phone_number_id is not None:
            query = query.where(WhatsAppDailyStat.phone_number_id == phone_number_id)
        if conversation_origin_type is not None:
            query = query.where(WhatsAppDailyStat.conversation_origin_type == conversation_origin_type)
        if conversation_category is not None:
            query = query.where(WhatsAppDailyStat.conversation_category == conversation_category)
        if pricing_model is not None:
            query = query.where(WhatsAppDailyStat.pricing_model == pricing_model)
        if billable is not None:
            query = query.where(WhatsAppDailyStat.billable == billable)
        if hour_bucket is not None:
            query = query.where(WhatsAppDailyStat.hour_bucket == hour_bucket)
        if start_date is not None:
            query = query.where(WhatsAppDailyStat.date >= start_date)
        if end_date is not None:
            query = query.where(WhatsAppDailyStat.date <= end_date)
        return query

    @staticmethod
    def _apply_fact_filters(
        *,
        query,
        account_id: str | None,
        waba_id: str | None,
        phone_number_id: str | None,
        conversation_origin_type: str | None,
        conversation_category: str | None,
        pricing_model: str | None,
        billable: bool | None,
        hour_bucket: int | None,
        start_date: date | None,
        end_date: date | None,
        allowed_account_ids: set[str] | None,
    ):
        if account_id is not None:
            query = query.where(WhatsAppConversationStat.account_id == account_id)
        elif allowed_account_ids is not None:
            query = query.where(WhatsAppConversationStat.account_id.in_(allowed_account_ids))
        if waba_id is not None:
            query = query.where(WhatsAppConversationStat.waba_id == waba_id)
        if phone_number_id is not None:
            query = query.where(WhatsAppConversationStat.phone_number_id == phone_number_id)
        if conversation_origin_type is not None:
            query = query.where(
                WhatsAppConversationStat.conversation_origin_type == conversation_origin_type
            )
        if conversation_category is not None:
            query = query.where(
                WhatsAppConversationStat.conversation_category == conversation_category
            )
        if pricing_model is not None:
            query = query.where(WhatsAppConversationStat.pricing_model == pricing_model)
        if billable is not None:
            query = query.where(WhatsAppConversationStat.billable == billable)
        if hour_bucket is not None:
            query = query.where(WhatsAppConversationStat.hour_bucket == hour_bucket)
        if start_date is not None:
            query = query.where(WhatsAppConversationStat.date >= start_date)
        if end_date is not None:
            query = query.where(WhatsAppConversationStat.date <= end_date)
        return query
