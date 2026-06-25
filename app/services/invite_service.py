from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from app.db.models import (
    AppUser,
    InviteLink,
    InviteRecord,
    SystemSetting,
    WalletAccount,
    WalletLedgerEntry,
)


class InviteLimitExceededError(ValueError):
    pass


class AntiFraudError(ValueError):
    pass


class InviteService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_or_create_link(self, user_id: str, account_id: str) -> InviteLink:
        link = self._session.execute(
            select(InviteLink).where(InviteLink.user_id == user_id)
        ).scalar_one_or_none()
        if link:
            return link

        code = self._generate_code(user_id)
        link = InviteLink(
            account_id=account_id,
            user_id=user_id,
            invite_code=code,
        )
        self._session.add(link)
        self._session.commit()
        self._session.refresh(link)
        return link

    def get_my_records(self, user_id: str, page: int = 1, size: int = 20) -> dict[str, Any]:
        query = (
            select(InviteRecord)
            .where(InviteRecord.inviter_user_id == user_id)
            .order_by(InviteRecord.created_at.desc())
        )
        total = self._session.execute(query).scalars().all()
        total_count = len(total)
        offset = (page - 1) * size
        items = self._session.execute(query.offset(offset).limit(size)).scalars().all()
        return {
            "items": [
                {
                    "id": r.id,
                    "inviter_user_id": r.inviter_user_id,
                    "invitee_user_id": r.invitee_user_id,
                    "invite_type": r.invite_type,
                    "reward_amount": r.reward_amount,
                    "is_rewarded": r.is_rewarded,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in items
            ],
            "total": total_count,
        }

    def list_records(
        self,
        *,
        account_id: str | None = None,
        inviter_user_id: str | None = None,
        invitee_user_id: str | None = None,
        invite_type: str | None = None,
        is_rewarded: bool | None = None,
        page: int = 1,
        size: int = 20,
    ) -> dict[str, Any]:
        inviter_user = aliased(AppUser)
        invitee_user = aliased(AppUser)

        query = (
            select(
                InviteRecord,
                inviter_user.public_user_id.label("inviter_public_user_id"),
                invitee_user.public_user_id.label("invitee_public_user_id"),
            )
            .join(inviter_user, inviter_user.id == InviteRecord.inviter_user_id)
            .join(invitee_user, invitee_user.id == InviteRecord.invitee_user_id)
        )

        if account_id:
            query = query.where(InviteRecord.account_id == account_id)
        if inviter_user_id:
            query = query.where(InviteRecord.inviter_user_id == inviter_user_id)
        if invitee_user_id:
            query = query.where(InviteRecord.invitee_user_id == invitee_user_id)
        if invite_type:
            query = query.where(InviteRecord.invite_type == invite_type)
        if is_rewarded is not None:
            query = query.where(InviteRecord.is_rewarded.is_(is_rewarded))

        ordered_query = query.order_by(InviteRecord.created_at.desc())
        total_count = len(self._session.execute(ordered_query).all())
        offset = (page - 1) * size
        rows = self._session.execute(ordered_query.offset(offset).limit(size)).all()

        return {
            "items": [
                {
                    "id": record.id,
                    "account_id": record.account_id,
                    "inviter_user_id": record.inviter_user_id,
                    "inviter_public_user_id": inviter_public_user_id,
                    "invitee_user_id": record.invitee_user_id,
                    "invitee_public_user_id": invitee_public_user_id,
                    "invite_type": record.invite_type,
                    "reward_amount": record.reward_amount,
                    "is_rewarded": record.is_rewarded,
                    "reward_fund_type": "task_balance",
                    "reward_transaction_type": f"invite_{record.invite_type}",
                    "invitee_ip": record.invitee_ip,
                    "invitee_device_id": record.invitee_device_id,
                    "created_at": record.created_at.isoformat() if record.created_at else None,
                }
                for record, inviter_public_user_id, invitee_public_user_id in rows
            ],
            "total": total_count,
            "page": page,
            "size": size,
        }

    def on_register_callback(
        self,
        inviter_code: str,
        invitee_user_id: str,
        invitee_ip: str | None = None,
        invitee_device_id: str | None = None,
    ) -> InviteRecord | None:
        link = self._session.execute(
            select(InviteLink).where(InviteLink.invite_code == inviter_code)
        ).scalar_one_or_none()
        if link is None:
            raise LookupError(f"Invalid invite code '{inviter_code}'.")
        if link.user_id == invitee_user_id:
            raise ValueError("Cannot invite yourself.")

        return self._process_invite(
            inviter_user_id=link.user_id,
            invitee_user_id=invitee_user_id,
            invite_type="register",
            reward_key="invite_register_reward",
            reward_default=Decimal("2.00"),
            account_id=link.account_id,
            invitee_ip=invitee_ip,
            invitee_device_id=invitee_device_id,
        )

    def on_recharge_callback(
        self,
        inviter_user_id: str,
        invitee_user_id: str,
        amount: Decimal,
        invitee_ip: str | None = None,
        invitee_device_id: str | None = None,
    ) -> InviteRecord | None:
        threshold = self._get_config_decimal("invite_recharge_threshold", Decimal("30"))
        if amount < threshold:
            return None

        # Find the link to get account_id
        link = self._session.execute(
            select(InviteLink).where(InviteLink.user_id == inviter_user_id)
        ).scalar_one_or_none()
        if link is None:
            raise LookupError(f"No invite link found for inviter '{inviter_user_id}'.")

        return self._process_invite(
            inviter_user_id=inviter_user_id,
            invitee_user_id=invitee_user_id,
            invite_type="recharge",
            reward_key="invite_recharge_reward",
            reward_default=Decimal("3.00"),
            account_id=link.account_id,
            invitee_ip=invitee_ip,
            invitee_device_id=invitee_device_id,
        )

    def get_config(self) -> dict[str, Any]:
        return {
            "register_reward": self._get_config_decimal("invite_register_reward", Decimal("2.00")),
            "recharge_threshold": self._get_config_decimal("invite_recharge_threshold", Decimal("30")),
            "recharge_reward": self._get_config_decimal("invite_recharge_reward", Decimal("3.00")),
            "max_count": self._get_config_int("invite_max_count", 20),
            "anti_fraud_same_ip_limit": self._get_config_int("anti_fraud_same_ip_limit", 3),
            "anti_fraud_same_device_limit": self._get_config_int("anti_fraud_same_device_limit", 2),
        }

    def update_config(self, payload: dict[str, Any]) -> None:
        config_map = {
            "register_reward": "invite_register_reward",
            "recharge_threshold": "invite_recharge_threshold",
            "recharge_reward": "invite_recharge_reward",
            "max_count": "invite_max_count",
            "anti_fraud_same_ip_limit": "anti_fraud_same_ip_limit",
            "anti_fraud_same_device_limit": "anti_fraud_same_device_limit",
        }
        for field, key in config_map.items():
            if field in payload and payload[field] is not None:
                self._set_config(key, payload[field])

    def _process_invite(
        self,
        inviter_user_id: str,
        invitee_user_id: str,
        invite_type: str,
        reward_key: str,
        reward_default: Decimal,
        account_id: str,
        invitee_ip: str | None = None,
        invitee_device_id: str | None = None,
    ) -> InviteRecord | None:
        # Duplicate check
        existing = self._session.execute(
            select(InviteRecord).where(
                InviteRecord.inviter_user_id == inviter_user_id,
                InviteRecord.invitee_user_id == invitee_user_id,
                InviteRecord.invite_type == invite_type,
            )
        ).scalar_one_or_none()
        if existing:
            return None

        # Validate fraud checks
        self._validate_invite(
            inviter_user_id=inviter_user_id,
            invitee_ip=invitee_ip,
            invitee_device_id=invitee_device_id,
            account_id=account_id,
        )

        reward_amount = self._get_config_decimal(reward_key, reward_default)

        record = InviteRecord(
            account_id=account_id,
            inviter_user_id=inviter_user_id,
            invitee_user_id=invitee_user_id,
            invite_type=invite_type,
            reward_amount=reward_amount,
            is_rewarded=False,
            invitee_ip=invitee_ip,
            invitee_device_id=invitee_device_id,
        )
        self._session.add(record)
        self._session.commit()
        self._session.refresh(record)

        # Credit reward to task_balance
        if reward_amount > Decimal("0"):
            wallet = self._session.execute(
                select(WalletAccount).where(
                    WalletAccount.user_id == inviter_user_id,
                    WalletAccount.account_id == account_id,
                )
            ).scalar_one_or_none()
            if wallet:
                wallet.task_balance += reward_amount
                record.is_rewarded = True
                self._session.add(WalletLedgerEntry(
                    account_id=account_id,
                    wallet_account_id=wallet.id,
                    user_id=inviter_user_id,
                    ledger_type="task_reward",
                    transaction_type=f"invite_{invite_type}",
                    direction="credit",
                    amount=reward_amount,
                    currency=wallet.currency,
                    status="paid",
                    note=f"Invite {invite_type} reward",
                    reference_type="invite_record",
                    reference_id=record.id,
                ))
                self._session.commit()

        return record

    def _validate_invite(
        self,
        inviter_user_id: str,
        invitee_ip: str | None,
        invitee_device_id: str | None,
        account_id: str,
    ) -> None:
        max_count = self._get_config_int("invite_max_count", 20)
        count = self._session.execute(
            select(func.count(InviteRecord.id)).where(
                InviteRecord.inviter_user_id == inviter_user_id,
            )
        ).scalar() or 0
        if count >= max_count:
            raise InviteLimitExceededError(f"Invite limit ({max_count}) exceeded.")

        if invitee_ip:
            ip_limit = self._get_config_int("anti_fraud_same_ip_limit", 3)
            if ip_limit > 0:
                ip_count = self._session.execute(
                    select(func.count(InviteRecord.id)).where(
                        InviteRecord.inviter_user_id == inviter_user_id,
                        InviteRecord.invitee_ip == invitee_ip,
                    )
                ).scalar() or 0
                if ip_count >= ip_limit:
                    raise AntiFraudError(f"Same IP limit ({ip_limit}) exceeded for IP {invitee_ip}")

        if invitee_device_id:
            device_limit = self._get_config_int("anti_fraud_same_device_limit", 2)
            if device_limit > 0:
                device_count = self._session.execute(
                    select(func.count(InviteRecord.id)).where(
                        InviteRecord.inviter_user_id == inviter_user_id,
                        InviteRecord.invitee_device_id == invitee_device_id,
                    )
                ).scalar() or 0
                if device_count >= device_limit:
                    raise AntiFraudError(f"Same device limit ({device_limit}) exceeded for device {invitee_device_id}")

    def _generate_code(self, user_id: str) -> str:
        raw = f"{user_id}-{datetime.now(UTC).isoformat()}"
        return hashlib.sha256(raw.encode()).hexdigest()[:12]

    def _get_config_decimal(self, key: str, default: Decimal) -> Decimal:
        setting = self._session.get(SystemSetting, key)
        if setting and setting.value_json is not None:
            return Decimal(str(setting.value_json.get("value", default)))
        return default

    def _get_config_int(self, key: str, default: int) -> int:
        setting = self._session.get(SystemSetting, key)
        if setting and setting.value_json is not None:
            return int(setting.value_json.get("value", default))
        return default

    def _set_config(self, key: str, value: Any) -> None:
        setting = self._session.get(SystemSetting, key)
        json_value = {"value": float(value) if isinstance(value, Decimal) else value}
        if setting:
            setting.value_json = json_value
        else:
            self._session.add(SystemSetting(key=key, value_json=json_value))
        self._session.commit()
