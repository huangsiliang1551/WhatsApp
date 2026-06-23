from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    MktTaskInstance,
    SignInRecord,
    SystemSetting,
    WalletAccount,
    WalletLedgerEntry,
)
from app.schemas.marketing import SignInResultResponse, SignInStatusResponse


class AlreadySignedInError(ValueError):
    pass


class SignInTaskAlreadyCompletedError(ValueError):
    pass


class SignInService:
    def __init__(self, session: Session, redis_client: Any | None = None) -> None:
        self._session = session
        self._redis = redis_client

    def sign_in(self, user_id: str, account_id: str) -> SignInResultResponse:
        today = date.today()

        # Check Redis quick check
        if self._redis:
            redis_key = f"signin:{user_id}:{today.isoformat()}"
            if self._redis.get(redis_key):
                raise AlreadySignedInError("Already signed in today.")

        # Check DB
        existing = self._get_record(user_id, today)
        if existing:
            if self._redis:
                self._redis.set(f"signin:{user_id}:{today.isoformat()}", "1", ex=25 * 3600)
            raise AlreadySignedInError("Already signed in today.")

        # Check if sign-in task already completed this cycle
        if self._is_signin_task_completed(user_id, account_id):
            raise SignInTaskAlreadyCompletedError("Sign-in task already completed for this cycle.")

        # Calculate consecutive days
        yesterday = today - timedelta(days=1)
        yesterday_record = self._get_record(user_id, yesterday)
        consecutive = (yesterday_record.consecutive_days + 1) if yesterday_record else 1

        # Create record
        record = SignInRecord(
            account_id=account_id,
            user_id=user_id,
            sign_date=today,
            consecutive_days=consecutive,
        )
        self._session.add(record)

        # Check reward eligibility
        reward_amount = Decimal("0")
        config_days = self._get_config_int("sign_in_consecutive_days", 7)
        rewarded = consecutive >= config_days

        if rewarded:
            reward_amount = self._get_config_decimal("sign_in_reward_amount", Decimal("5.00"))
            self._reward_task_balance(user_id, account_id, reward_amount, "sign_in_completion")
            record.is_rewarded = True
            self._mark_signin_task_completed(user_id, account_id)

        self._session.commit()

        # Set Redis mark
        if self._redis:
            self._redis.set(redis_key, "1", ex=25 * 3600)

        return SignInResultResponse(
            consecutive_days=consecutive,
            rewarded=rewarded,
            reward_amount=reward_amount,
        )

    def get_status(self, user_id: str, account_id: str) -> SignInStatusResponse:
        today = date.today()
        signed_in_today = bool(self._get_record(user_id, today))

        yesterday = today - timedelta(days=1)
        yesterday_record = self._get_record(user_id, yesterday)
        consecutive = 0
        if signed_in_today:
            today_record = self._get_record(user_id, today)
            consecutive = today_record.consecutive_days if today_record else 1
        elif yesterday_record:
            consecutive = yesterday_record.consecutive_days

        config_days = self._get_config_int("sign_in_consecutive_days", 7)
        reward_amount = self._get_config_decimal("sign_in_reward_amount", Decimal("5.00"))

        return SignInStatusResponse(
            signed_in_today=signed_in_today,
            consecutive_days=consecutive,
            days_until_reward=max(0, config_days - consecutive),
            reward_amount=reward_amount,
        )

    def get_config(self) -> dict[str, Any]:
        return {
            "consecutive_days": self._get_config_int("sign_in_consecutive_days", 7),
            "reward_amount": self._get_config_decimal("sign_in_reward_amount", Decimal("5.00")),
        }

    def update_config(self, consecutive_days: int | None, reward_amount: Decimal | None) -> None:
        if consecutive_days is not None:
            self._set_config("sign_in_consecutive_days", consecutive_days)
        if reward_amount is not None:
            self._set_config("sign_in_reward_amount", str(reward_amount))

    def _get_record(self, user_id: str, d: date) -> SignInRecord | None:
        return self._session.execute(
            select(SignInRecord).where(
                SignInRecord.user_id == user_id,
                SignInRecord.sign_date == d,
            )
        ).scalar_one_or_none()

    def _is_signin_task_completed(self, user_id: str, account_id: str) -> bool:
        """Check if the user has completed their sign-in task in the current cycle."""
        today = date.today()
        existing = self._session.execute(
            select(MktTaskInstance).where(
                MktTaskInstance.user_id == user_id,
                MktTaskInstance.account_id == account_id,
                MktTaskInstance.task_type == "signin",
                MktTaskInstance.status == "completed",
                func.date(MktTaskInstance.completed_at) == today,
            )
        ).scalar_one_or_none()
        return existing is not None

    def _mark_signin_task_completed(self, user_id: str, account_id: str) -> None:
        """Mark the sign-in task as completed for the day."""
        today = date.today()
        existing = self._session.execute(
            select(MktTaskInstance).where(
                MktTaskInstance.user_id == user_id,
                MktTaskInstance.account_id == account_id,
                MktTaskInstance.task_type == "signin",
                MktTaskInstance.status == "running",
            )
        ).scalar_one_or_none()
        if existing:
            existing.status = "completed"
            existing.completed_at = datetime.now(UTC).replace(tzinfo=None)

    def _reward_task_balance(self, user_id: str, account_id: str, amount: Decimal, note: str) -> None:
        wallet = self._session.execute(
            select(WalletAccount).where(
                WalletAccount.user_id == user_id,
                WalletAccount.account_id == account_id,
            )
        ).scalar_one_or_none()
        if wallet:
            wallet.task_balance += amount
            self._session.add(WalletLedgerEntry(
                account_id=account_id,
                wallet_account_id=wallet.id,
                user_id=user_id,
                ledger_type="task_reward",
                transaction_type=note,
                direction="credit",
                amount=amount,
                currency=wallet.currency,
                status="paid",
                note=note,
                reference_type="sign_in",
                reference_id=None,
            ))

    def _get_config_int(self, key: str, default: int) -> int:
        setting = self._session.get(SystemSetting, key)
        if setting and setting.value_json is not None:
            return int(setting.value_json.get("value", default))
        return default

    def _get_config_decimal(self, key: str, default: Decimal) -> Decimal:
        setting = self._session.get(SystemSetting, key)
        if setting and setting.value_json is not None:
            return Decimal(str(setting.value_json.get("value", default)))
        return default

    def _set_config(self, key: str, value: Any) -> None:
        setting = self._session.get(SystemSetting, key)
        if setting:
            setting.value_json = {"value": value}
        else:
            self._session.add(SystemSetting(key=key, value_json={"value": value}))
        self._session.commit()
