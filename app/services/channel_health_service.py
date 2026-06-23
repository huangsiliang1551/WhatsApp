"""Channel health monitoring service."""
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.db.models import PaymentChannel, RechargeRecord, PaymentCallback


class ChannelHealthService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_channel_health(self, channel_id: str) -> dict:
        ch = self._session.get(PaymentChannel, channel_id)
        if ch is None:
            raise LookupError("Channel not found")

        since_24h = datetime.now(timezone.utc) - timedelta(hours=24)

        # Total transactions in last 24h
        total_tx = self._session.scalar(
            select(func.count()).select_from(RechargeRecord).where(
                RechargeRecord.channel_id == channel_id,
                RechargeRecord.created_at >= since_24h,
            )
        ) or 0

        # Successful transactions
        success_tx = self._session.scalar(
            select(func.count()).select_from(RechargeRecord).where(
                RechargeRecord.channel_id == channel_id,
                RechargeRecord.created_at >= since_24h,
                RechargeRecord.status == "completed",
            )
        ) or 0

        # Total amount
        total_amount = self._session.scalar(
            select(func.sum(RechargeRecord.amount)).where(
                RechargeRecord.channel_id == channel_id,
                RechargeRecord.created_at >= since_24h,
                RechargeRecord.status == "completed",
            )
        ) or 0

        # Failed callbacks
        failed_cb = self._session.scalar(
            select(func.count()).select_from(PaymentCallback).where(
                PaymentCallback.channel_id == channel_id,
                PaymentCallback.created_at >= since_24h,
                PaymentCallback.signature_valid.is_(False),
            )
        ) or 0

        success_rate = round(success_tx / total_tx * 100, 2) if total_tx > 0 else 100.0

        return {
            "channel_id": channel_id,
            "channel_name": ch.name,
            "status": ch.status,
            "total_transactions_24h": total_tx,
            "successful_transactions_24h": success_tx,
            "failed_callbacks_24h": failed_cb,
            "success_rate_24h": success_rate,
            "total_amount_24h": float(total_amount),
        }

    def get_all_channels_health(self) -> list[dict]:
        channels = self._session.execute(select(PaymentChannel)).scalars().all()
        results = []
        for ch in channels:
            try:
                health = self.get_channel_health(ch.id)
                results.append(health)
            except LookupError:
                continue
        return results
