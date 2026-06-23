from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models import (
    Message,
    TemplateDailyStat,
    TemplateFailureStat,
    TemplateHourlyStat,
    TemplateSendLog,
    WhatsAppPhoneNumber,
)


@dataclass(slots=True)
class TemplateStatusTransitionSnapshot:
    had_delivered_at: bool
    had_read_at: bool
    had_failed_at: bool
    was_billable: bool
    estimated_cost: Decimal


class TemplateStatsAggregator:
    def __init__(self, session: Session) -> None:
        self._session = session

    def capture_transition_snapshot(
        self,
        send_log: TemplateSendLog,
    ) -> TemplateStatusTransitionSnapshot:
        return TemplateStatusTransitionSnapshot(
            had_delivered_at=send_log.delivered_at is not None,
            had_read_at=send_log.read_at is not None,
            had_failed_at=send_log.failed_at is not None,
            was_billable=bool(send_log.billable),
            estimated_cost=Decimal(send_log.estimated_cost or 0),
        )

    def record_send_log_created(self, send_log: TemplateSendLog) -> None:
        stats_rows = self._get_or_create_rows(send_log)
        if stats_rows is None:
            return
        daily_row, hourly_row, failure_row = stats_rows
        for row in (daily_row, hourly_row):
            row.send_count += 1
            if send_log.delivered_at is not None or send_log.status in {"DELIVERED", "READ"}:
                row.delivered_count += 1
            if send_log.read_at is not None or send_log.status == "READ":
                row.read_count += 1
            if send_log.failed_at is not None or send_log.status == "FAILED":
                row.failed_count += 1
            if send_log.billable:
                row.billable_count += 1
            row.estimated_cost = Decimal(row.estimated_cost or 0) + Decimal(send_log.estimated_cost or 0)
            self._session.add(row)
        if failure_row is not None:
            failure_row.failed_count += 1
            self._session.add(failure_row)

    def record_status_transition(
        self,
        send_log: TemplateSendLog,
        snapshot: TemplateStatusTransitionSnapshot,
    ) -> None:
        stats_rows = self._get_or_create_rows(send_log)
        if stats_rows is None:
            return
        daily_row, hourly_row, failure_row = stats_rows

        for row in (daily_row, hourly_row):
            if send_log.delivered_at is not None and not snapshot.had_delivered_at:
                row.delivered_count += 1
            if send_log.read_at is not None and not snapshot.had_read_at:
                row.read_count += 1
            if send_log.failed_at is not None and not snapshot.had_failed_at:
                row.failed_count += 1
            if send_log.billable and not snapshot.was_billable:
                row.billable_count += 1

            previous_cost = snapshot.estimated_cost
            current_cost = Decimal(send_log.estimated_cost or 0)
            if current_cost > previous_cost:
                row.estimated_cost = Decimal(row.estimated_cost or 0) + (current_cost - previous_cost)
            self._session.add(row)
        if send_log.failed_at is not None and not snapshot.had_failed_at and failure_row is not None:
            failure_row.failed_count += 1
            self._session.add(failure_row)

    def _get_or_create_rows(
        self,
        send_log: TemplateSendLog,
    ) -> tuple[TemplateDailyStat, TemplateHourlyStat, TemplateFailureStat | None] | None:
        if (
            send_log.template_name is None
            or send_log.template_language is None
            or send_log.template_category is None
        ):
            return None

        occurred_at = self._resolve_occurred_at(send_log)
        resolved_waba_id = self._resolve_waba_id(send_log)
        provider_phone_number_id = self._resolve_provider_phone_number_id(send_log)
        stat_date = occurred_at.date()
        daily_row = self._session.scalars(
            select(TemplateDailyStat).where(
                TemplateDailyStat.date == stat_date,
                TemplateDailyStat.account_id == send_log.account_id,
                TemplateDailyStat.template_id == send_log.template_id,
                TemplateDailyStat.waba_id == resolved_waba_id,
                TemplateDailyStat.phone_number_id == provider_phone_number_id,
                TemplateDailyStat.template_name == send_log.template_name,
                TemplateDailyStat.template_language == send_log.template_language,
            )
        ).first()
        if daily_row is None:
            daily_row = TemplateDailyStat(
                date=stat_date,
                account_id=send_log.account_id,
                template_id=send_log.template_id,
                waba_id=resolved_waba_id,
                phone_number_id=provider_phone_number_id,
                template_name=send_log.template_name,
                template_code=send_log.template_code,
                template_category=send_log.template_category,
                template_language=send_log.template_language,
                send_count=0,
                delivered_count=0,
                read_count=0,
                failed_count=0,
                billable_count=0,
                estimated_cost=Decimal("0"),
            )
            self._session.add(daily_row)

        hourly_row = self._session.scalars(
            select(TemplateHourlyStat).where(
                TemplateHourlyStat.date == stat_date,
                TemplateHourlyStat.hour_bucket == occurred_at.hour,
                TemplateHourlyStat.account_id == send_log.account_id,
                TemplateHourlyStat.template_id == send_log.template_id,
                TemplateHourlyStat.waba_id == resolved_waba_id,
                TemplateHourlyStat.phone_number_id == provider_phone_number_id,
                TemplateHourlyStat.template_name == send_log.template_name,
                TemplateHourlyStat.template_language == send_log.template_language,
            )
        ).first()
        if hourly_row is None:
            hourly_row = TemplateHourlyStat(
                date=stat_date,
                hour_bucket=occurred_at.hour,
                account_id=send_log.account_id,
                template_id=send_log.template_id,
                waba_id=resolved_waba_id,
                phone_number_id=provider_phone_number_id,
                template_name=send_log.template_name,
                template_code=send_log.template_code,
                template_category=send_log.template_category,
                template_language=send_log.template_language,
                send_count=0,
                delivered_count=0,
                read_count=0,
                failed_count=0,
                billable_count=0,
                estimated_cost=Decimal("0"),
            )
            self._session.add(hourly_row)

        failure_row: TemplateFailureStat | None = None
        if send_log.failed_at is not None or send_log.status == "FAILED":
            error_code = send_log.error_code or "unknown"
            failure_row = self._session.scalars(
                select(TemplateFailureStat).where(
                    TemplateFailureStat.date == stat_date,
                    TemplateFailureStat.account_id == send_log.account_id,
                    TemplateFailureStat.template_id == send_log.template_id,
                    TemplateFailureStat.waba_id == resolved_waba_id,
                    TemplateFailureStat.phone_number_id == provider_phone_number_id,
                    TemplateFailureStat.template_name == send_log.template_name,
                    TemplateFailureStat.template_language == send_log.template_language,
                    TemplateFailureStat.error_code == error_code,
                )
            ).first()
            if failure_row is None:
                failure_row = TemplateFailureStat(
                    date=stat_date,
                    account_id=send_log.account_id,
                    template_id=send_log.template_id,
                    waba_id=resolved_waba_id,
                    phone_number_id=provider_phone_number_id,
                    template_name=send_log.template_name,
                    template_code=send_log.template_code,
                    template_category=send_log.template_category,
                    template_language=send_log.template_language,
                    error_code=error_code,
                    failed_count=0,
                )
                self._session.add(failure_row)

        self._session.flush()
        return daily_row, hourly_row, failure_row

    @staticmethod
    def _resolve_occurred_at(send_log: TemplateSendLog) -> datetime:
        return send_log.sent_at or send_log.created_at or send_log.failed_at or send_log.last_status_at

    def _resolve_provider_phone_number_id(self, send_log: TemplateSendLog) -> str | None:
        snapshot_phone_number_id = self._load_message_scope_phone_number_id(send_log)
        if snapshot_phone_number_id is not None:
            return snapshot_phone_number_id
        if send_log.phone_number is not None and send_log.phone_number_id == send_log.phone_number.id:
            return send_log.phone_number.phone_number_id
        if send_log.phone_number is not None:
            return send_log.phone_number.phone_number_id
        if send_log.phone_number_id is None:
            return None
        phone_number = self._resolve_phone_number_by_local_or_provider_id(send_log)
        if phone_number is not None and phone_number.id == send_log.phone_number_id:
            return phone_number.phone_number_id
        return send_log.phone_number_id

    def _resolve_waba_id(self, send_log: TemplateSendLog) -> str | None:
        snapshot_waba_id = self._load_message_scope_waba_id(send_log)
        if snapshot_waba_id is not None:
            return snapshot_waba_id
        if send_log.waba_id is not None:
            return send_log.waba_id
        if send_log.phone_number is not None and send_log.phone_number.waba_id:
            return send_log.phone_number.waba_id
        if send_log.phone_number is not None and send_log.phone_number.waba_account is not None:
            return send_log.phone_number.waba_account.waba_id
        if send_log.phone_number_id is None:
            return None
        phone_number = self._resolve_phone_number_by_local_or_provider_id(send_log)
        if phone_number is not None and phone_number.waba_id:
            return phone_number.waba_id
        if phone_number is not None and phone_number.waba_account is not None:
            return phone_number.waba_account.waba_id
        return None

    def _load_message_scope_waba_id(self, send_log: TemplateSendLog) -> str | None:
        if send_log.message_id is None:
            return None
        message = self._session.scalars(
            select(Message).where(
                Message.account_id == send_log.account_id,
                or_(
                    Message.id == send_log.message_id,
                    Message.provider_message_id == send_log.message_id,
                ),
            )
        ).first()
        if message is None or not isinstance(message.payload, dict):
            return None
        return self._pick_nested_payload_string(message.payload, "waba_id")

    def _load_message_scope_phone_number_id(self, send_log: TemplateSendLog) -> str | None:
        if send_log.message_id is None:
            return None
        message = self._session.scalars(
            select(Message).where(
                Message.account_id == send_log.account_id,
                or_(
                    Message.id == send_log.message_id,
                    Message.provider_message_id == send_log.message_id,
                ),
            )
        ).first()
        if message is None or not isinstance(message.payload, dict):
            return None
        return self._pick_nested_payload_string(message.payload, "phone_number_id")

    @classmethod
    def _pick_nested_payload_string(
        cls,
        payload: dict[str, object] | None,
        key: str,
    ) -> str | None:
        if not isinstance(payload, dict):
            return None
        direct_value = cls._pick_payload_string(payload, key)
        if direct_value is not None:
            return direct_value
        metadata = payload.get("metadata")
        if isinstance(metadata, dict):
            metadata_value = cls._pick_payload_string(metadata, key)
            if metadata_value is not None:
                return metadata_value
        for candidate_key in ("provider_payload", "raw_payload"):
            candidate = payload.get(candidate_key)
            if not isinstance(candidate, dict):
                continue
            nested_value = cls._pick_nested_payload_string(candidate, key)
            if nested_value is not None:
                return nested_value
        return None

    @staticmethod
    def _pick_payload_string(
        payload: dict[str, object] | None,
        key: str,
    ) -> str | None:
        if not isinstance(payload, dict):
            return None
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
        return None

    def _resolve_phone_number_by_local_or_provider_id(
        self,
        send_log: TemplateSendLog,
    ) -> WhatsAppPhoneNumber | None:
        if send_log.phone_number_id is None:
            return None
        phone_number = self._session.get(WhatsAppPhoneNumber, send_log.phone_number_id)
        if phone_number is not None:
            return phone_number
        return self._session.scalars(
            select(WhatsAppPhoneNumber).where(
                WhatsAppPhoneNumber.account_id == send_log.account_id,
                WhatsAppPhoneNumber.phone_number_id == send_log.phone_number_id,
            )
        ).first()
