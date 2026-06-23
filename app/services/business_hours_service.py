from __future__ import annotations

from datetime import UTC, datetime, time as dt_time, timedelta
from uuid import uuid4

import structlog
import pytz
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import BusinessHours

logger = structlog.get_logger()


class BusinessHoursService:
    def __init__(self, session: Session) -> None:
        self._session = session

    async def get_hours(self, account_id: str) -> dict:
        row = self._session.execute(
            select(BusinessHours).where(BusinessHours.account_id == account_id)
        ).scalar_one_or_none()

        if row is None:
            return self._default_response(account_id)

        return {
            "account_id": row.account_id,
            "business_hours": {
                "weekdays": row.weekdays or [1, 2, 3, 4, 5],
                "start_time": row.start_time,
                "end_time": row.end_time,
                "timezone": row.timezone,
                "off_hours_behavior": row.off_hours_behavior,
                "off_hours_message": row.off_hours_message,
            },
            "is_currently_business_hours": self._is_business_hours(
                weekdays=row.weekdays or [1, 2, 3, 4, 5],
                start_time=row.start_time,
                end_time=row.end_time,
                timezone=row.timezone,
            ),
        }

    async def upsert_hours(
        self,
        account_id: str,
        *,
        weekdays: list[int] | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
        timezone: str | None = None,
        off_hours_behavior: str | None = None,
        off_hours_message: str | None = None,
    ) -> dict:
        row = self._session.execute(
            select(BusinessHours).where(BusinessHours.account_id == account_id)
        ).scalar_one_or_none()

        if row is None:
            row = BusinessHours(
                id=str(uuid4()),
                account_id=account_id,
                weekdays=weekdays or [1, 2, 3, 4, 5],
                start_time=start_time or "09:00",
                end_time=end_time or "18:00",
                timezone=timezone or "Asia/Shanghai",
                off_hours_behavior=off_hours_behavior or "ai_managed",
                off_hours_message=off_hours_message,
            )
            self._session.add(row)
        else:
            if weekdays is not None:
                row.weekdays = weekdays
            if start_time is not None:
                row.start_time = start_time
            if end_time is not None:
                row.end_time = end_time
            if timezone is not None:
                row.timezone = timezone
            if off_hours_behavior is not None:
                row.off_hours_behavior = off_hours_behavior
            if off_hours_message is not None:
                row.off_hours_message = off_hours_message

        self._session.commit()

        return {
            "account_id": row.account_id,
            "business_hours": {
                "weekdays": row.weekdays or [1, 2, 3, 4, 5],
                "start_time": row.start_time,
                "end_time": row.end_time,
                "timezone": row.timezone,
                "off_hours_behavior": row.off_hours_behavior,
                "off_hours_message": row.off_hours_message,
            },
            "is_currently_business_hours": self._is_business_hours(
                weekdays=row.weekdays or [1, 2, 3, 4, 5],
                start_time=row.start_time,
                end_time=row.end_time,
                timezone=row.timezone,
            ),
        }

    @staticmethod
    def _default_response(account_id: str) -> dict:
        weekdays = [1, 2, 3, 4, 5]
        return {
            "account_id": account_id,
            "business_hours": {
                "weekdays": weekdays,
                "start_time": "09:00",
                "end_time": "18:00",
                "timezone": "Asia/Shanghai",
                "off_hours_behavior": "ai_managed",
                "off_hours_message": None,
            },
            "is_currently_business_hours": BusinessHoursService._is_business_hours(
                weekdays=weekdays,
                start_time="09:00",
                end_time="18:00",
                timezone="Asia/Shanghai",
            ),
        }

    @staticmethod
    def _is_business_hours(
        *,
        weekdays: list[int],
        start_time: str,
        end_time: str,
        timezone: str,
    ) -> bool:
        try:
            tz = pytz.timezone(timezone)
        except Exception:
            tz = pytz.UTC

        now_utc = datetime.now(UTC)
        now_local = now_utc.astimezone(tz)
        weekday = now_local.isoweekday()

        if weekday not in weekdays:
            return False

        try:
            start_parts = start_time.split(":")
            end_parts = end_time.split(":")
            start_t = dt_time(int(start_parts[0]), int(start_parts[1]))
            end_t = dt_time(int(end_parts[0]), int(end_parts[1]))
        except (ValueError, IndexError):
            return False

        current_t = now_local.time()

        if start_t <= end_t:
            return start_t <= current_t <= end_t
        else:
            return current_t >= start_t or current_t <= end_t
