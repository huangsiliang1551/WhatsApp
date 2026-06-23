"""Payment channel management service with Fernet encryption."""
import json
from datetime import datetime, timezone
from uuid import uuid4
from typing import Any

from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import PaymentChannel, AgentPaymentChannelSetting

_FERNET_KEY = Fernet.generate_key()  # In production, load from settings


def _encrypt(plain: str) -> str:
    return Fernet(_FERNET_KEY).encrypt(plain.encode()).decode()


def _decrypt(cipher: str) -> str:
    return Fernet(_FERNET_KEY).decrypt(cipher.encode()).decode()


class PaymentChannelService:
    def __init__(self, session: Session) -> None:
        self._session = session

    # ── CRUD Channels ──
    def create_channel(self, data: dict[str, Any]) -> dict:
        secret_plain = data.get("app_secret", "")
        enc_secret = _encrypt(secret_plain) if secret_plain else None
        ch = PaymentChannel(
            id=str(uuid4()),
            name=data["name"],
            channel_type=data["channel_type"],
            app_id=data.get("app_id"),
            app_secret_encrypted=enc_secret,
            callback_url=data.get("callback_url"),
            fee_rate=data.get("fee_rate", 0),
            min_amount=data.get("min_amount"),
            max_amount=data.get("max_amount"),
            status=data.get("status", "active"),
            is_sandbox=data.get("is_sandbox", False),
            callback_secret=data.get("callback_secret"),
            config_json=data.get("config_json"),
        )
        self._session.add(ch)
        self._session.flush()
        return self._channel_to_dict(ch)

    def update_channel(self, channel_id: str, data: dict[str, Any]) -> dict:
        ch = self._session.get(PaymentChannel, channel_id)
        if ch is None:
            raise LookupError("Channel not found")
        for key in ("name", "channel_type", "app_id", "callback_url", "status", "callback_secret", "config_json"):
            if key in data:
                setattr(ch, key, data[key])
        if "app_secret" in data and data["app_secret"]:
            ch.app_secret_encrypted = _encrypt(data["app_secret"])
        if "fee_rate" in data:
            ch.fee_rate = data["fee_rate"]
        if "min_amount" in data:
            ch.min_amount = data["min_amount"]
        if "max_amount" in data:
            ch.max_amount = data["max_amount"]
        if "is_sandbox" in data:
            ch.is_sandbox = data["is_sandbox"]
        ch.updated_at = datetime.now(timezone.utc)
        self._session.flush()
        return self._channel_to_dict(ch)

    def delete_channel(self, channel_id: str) -> None:
        ch = self._session.get(PaymentChannel, channel_id)
        if ch is None:
            raise LookupError("Channel not found")
        self._session.delete(ch)
        self._session.flush()

    def get_channel(self, channel_id: str) -> dict | None:
        ch = self._session.get(PaymentChannel, channel_id)
        return self._channel_to_dict(ch) if ch else None

    def list_channels(self) -> list[dict]:
        rows = self._session.execute(select(PaymentChannel)).scalars().all()
        return [self._channel_to_dict(r) for r in rows]

    # ── Agent channel settings ──
    def get_agent_channels(self, agency_id: str) -> list[dict]:
        settings = self._session.execute(
            select(AgentPaymentChannelSetting).where(AgentPaymentChannelSetting.agency_id == agency_id)
        ).scalars().all()
        results = []
        for s in settings:
            ch = self._session.get(PaymentChannel, s.channel_id) if s.channel_id else None
            results.append({
                "id": s.id,
                "agency_id": s.agency_id,
                "channel_id": s.channel_id,
                "channel_name": ch.name if ch else None,
                "is_enabled": s.is_enabled,
                "is_recharge_enabled": s.is_recharge_enabled,
                "is_withdraw_enabled": s.is_withdraw_enabled,
                "custom_merchant_id": s.custom_merchant_id,
            })
        return results

    def upsert_agent_channel(
        self, agency_id: str, channel_id: str, data: dict[str, Any]
    ) -> dict:
        existing = self._session.execute(
            select(AgentPaymentChannelSetting).where(
                AgentPaymentChannelSetting.agency_id == agency_id,
                AgentPaymentChannelSetting.channel_id == channel_id,
            )
        ).scalar_one_or_none()

        if existing:
            for key in ("is_enabled", "is_recharge_enabled", "is_withdraw_enabled", "custom_merchant_id"):
                if key in data:
                    setattr(existing, key, data[key])
            if "custom_secret" in data and data["custom_secret"]:
                existing.custom_secret_encrypted = _encrypt(data["custom_secret"])
            obj = existing
        else:
            secret_enc = _encrypt(data["custom_secret"]) if data.get("custom_secret") else None
            obj = AgentPaymentChannelSetting(
                id=str(uuid4()),
                agency_id=agency_id,
                channel_id=channel_id,
                is_enabled=data.get("is_enabled", True),
                is_recharge_enabled=data.get("is_recharge_enabled", True),
                is_withdraw_enabled=data.get("is_withdraw_enabled", True),
                custom_merchant_id=data.get("custom_merchant_id"),
                custom_secret_encrypted=secret_enc,
            )
            self._session.add(obj)
        self._session.flush()
        return {
            "agency_id": agency_id,
            "channel_id": channel_id,
            "is_enabled": obj.is_enabled,
            "is_recharge_enabled": obj.is_recharge_enabled,
            "is_withdraw_enabled": obj.is_withdraw_enabled,
        }

    def get_agent_active_channels(self, agency_id: str) -> list[dict]:
        settings = self._session.execute(
            select(AgentPaymentChannelSetting).where(
                AgentPaymentChannelSetting.agency_id == agency_id,
                AgentPaymentChannelSetting.is_enabled.is_(True),
            )
        ).scalars().all()
        results = []
        for s in settings:
            ch = self._session.get(PaymentChannel, s.channel_id) if s.channel_id else None
            if ch and ch.status == "active":
                results.append({
                    "channel_id": ch.id,
                    "name": ch.name,
                    "channel_type": ch.channel_type,
                    "fee_rate": float(ch.fee_rate),
                    "min_amount": float(ch.min_amount) if ch.min_amount else None,
                    "max_amount": float(ch.max_amount) if ch.max_amount else None,
                    "is_recharge_enabled": s.is_recharge_enabled,
                    "is_withdraw_enabled": s.is_withdraw_enabled,
                })
        return results

    def verify_callback_signature(self, channel_id: str, payload: dict, signature: str) -> bool:
        ch = self._session.get(PaymentChannel, channel_id)
        if ch is None or not ch.callback_secret:
            return False
        import hmac, hashlib
        expected = hmac.new(
            ch.callback_secret.encode(), json.dumps(payload, sort_keys=True).encode(), hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    def _channel_to_dict(self, ch: PaymentChannel) -> dict:
        return {
            "id": ch.id,
            "name": ch.name,
            "channel_type": ch.channel_type,
            "app_id": ch.app_id,
            "has_secret": bool(ch.app_secret_encrypted),
            "callback_url": ch.callback_url,
            "fee_rate": float(ch.fee_rate),
            "min_amount": float(ch.min_amount) if ch.min_amount else None,
            "max_amount": float(ch.max_amount) if ch.max_amount else None,
            "status": ch.status,
            "is_sandbox": ch.is_sandbox,
            "has_callback_secret": bool(ch.callback_secret),
            "config_json": ch.config_json,
            "created_at": ch.created_at.isoformat() if ch.created_at else None,
        }
