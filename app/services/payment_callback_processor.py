from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AppUser, PaymentCallback, RechargeRecord, WalletAccount, WalletRechargeOrder, utc_now
from app.services.payment_channel_service import PaymentChannelService
from app.services.wallet_ledger_service import WalletLedgerService


@dataclass(frozen=True, slots=True)
class PaymentCallbackProcessResult:
    status: str
    callback_id: str
    recharge_record_id: str | None = None


class PaymentCallbackProcessor:
    def __init__(self, *, session: Session) -> None:
        self._session = session
        self._channel_service = PaymentChannelService(session)
        self._wallet_ledger_service = WalletLedgerService(session=session)

    def process_callback(
        self,
        *,
        channel_id: str,
        payload: dict[str, object],
        signature: str,
    ) -> PaymentCallbackProcessResult:
        callback = PaymentCallback(
            id=str(uuid4()),
            channel_id=channel_id,
            raw_payload=payload,
            signature_valid=self._channel_service.verify_callback_signature(channel_id, payload, signature),
        )
        self._session.add(callback)
        self._session.flush()

        if not callback.signature_valid:
            self._mark_processed(callback=callback, recharge_record_id=None)
            self._session.flush()
            return PaymentCallbackProcessResult(status="signature_invalid", callback_id=callback.id)

        amount = Decimal(str(payload.get("amount", "0")))
        currency = str(payload.get("currency") or "USD")
        user_id = str(payload.get("user_id") or payload.get("customer_id") or "")
        channel_order_id = str(payload.get("order_id") or payload.get("transaction_id") or "").strip()

        existing_recharge = self._session.scalars(
            select(RechargeRecord).where(
                RechargeRecord.channel_id == channel_id,
                RechargeRecord.channel_order_id == channel_order_id,
            )
        ).first()
        if existing_recharge is not None:
            self._mark_processed(callback=callback, recharge_record_id=existing_recharge.id)
            self._session.flush()
            return PaymentCallbackProcessResult(
                status="duplicate",
                callback_id=callback.id,
                recharge_record_id=existing_recharge.id,
            )

        recharge = RechargeRecord(
            id=str(uuid4()),
            user_id=user_id or None,
            agency_id=None,
            channel_id=channel_id,
            amount=amount,
            currency=currency,
            status="completed",
            channel_order_id=channel_order_id or None,
            callback_data=payload,
            callback_verified=True,
        )
        self._session.add(recharge)
        self._session.flush()

        if user_id:
            app_user = self._session.get(AppUser, user_id)
            if app_user is not None:
                wallet = self._session.scalars(
                    select(WalletAccount).where(
                        WalletAccount.account_id == app_user.account_id,
                        WalletAccount.user_id == app_user.id,
                    )
                ).first()
                if wallet is None:
                    wallet = WalletAccount(
                        account_id=app_user.account_id,
                        user_id=app_user.id,
                        currency=currency,
                    )
                    self._session.add(wallet)
                    self._session.flush()
                recharge_order = WalletRechargeOrder(
                    account_id=app_user.account_id,
                    wallet_account_id=wallet.id,
                    user_id=app_user.id,
                    amount=amount,
                    currency=currency,
                    status="paid",
                    credited_at=utc_now(),
                )
                self._session.add(recharge_order)
                self._session.flush()
                self._wallet_ledger_service.credit_system_balance(
                    wallet=wallet,
                    account_id=app_user.account_id,
                    user_id=app_user.id,
                    amount=amount,
                    currency=currency,
                    transaction_type="recharge",
                    source_type="payment_callback",
                    note="Recharge credited from payment callback",
                    reference_type="wallet_recharge_order",
                    reference_id=recharge_order.id,
                    fund_type="cash",
                    is_real_recharge=True,
                    idempotency_key=f"payment_callback:{channel_id}:{channel_order_id}",
                )

        self._mark_processed(callback=callback, recharge_record_id=recharge.id)
        self._session.flush()
        return PaymentCallbackProcessResult(
            status="success",
            callback_id=callback.id,
            recharge_record_id=recharge.id,
        )

    @staticmethod
    def _mark_processed(*, callback: PaymentCallback, recharge_record_id: str | None) -> None:
        callback.processed = True
        callback.processed_at = datetime.now(timezone.utc)
        callback.recharge_record_id = recharge_record_id
