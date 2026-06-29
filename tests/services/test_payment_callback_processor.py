from __future__ import annotations

import hashlib
import hmac
import json
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Account, AppUser, PaymentChannel, RechargeRecord, WalletAccount, WalletLedgerEntry


def _sign(secret: str, payload: dict[str, object]) -> str:
    return hmac.new(secret.encode(), json.dumps(payload, sort_keys=True).encode(), hashlib.sha256).hexdigest()


def _seed_payment_context(session: Session) -> tuple[PaymentChannel, AppUser]:
    account = Account(account_id="acct-payment-processor", display_name="acct-payment-processor", provider_type="mock")
    user = AppUser(
        id="user-payment-processor",
        account_id=account.account_id,
        public_user_id="pub-user-payment-processor",
        registration_site_id=None,
        display_name="Payment Processor",
        has_phone=True,
        is_anonymous=False,
        lifecycle_status="active",
    )
    channel = PaymentChannel(
        id="channel-generic-hmac",
        name="Generic HMAC",
        channel_type="generic_hmac",
        callback_secret="generic-secret",
        status="active",
    )
    session.add_all([account, user, channel])
    session.flush()
    return channel, user


def test_payment_callback_processor_is_idempotent_for_duplicate_channel_order(
    db_session_factory: sessionmaker[Session],
) -> None:
    from app.services.payment_callback_processor import PaymentCallbackProcessor

    with db_session_factory() as session:
        channel, user = _seed_payment_context(session)
        payload = {
            "amount": "88.00",
            "currency": "USD",
            "user_id": user.id,
            "order_id": "PAY-ORDER-001",
        }
        signature = _sign("generic-secret", payload)
        processor = PaymentCallbackProcessor(session=session)

        first = processor.process_callback(channel_id=channel.id, payload=payload, signature=signature)
        second = processor.process_callback(channel_id=channel.id, payload=payload, signature=signature)
        session.flush()

        recharges = session.scalars(select(RechargeRecord)).all()
        ledgers = session.scalars(
            select(WalletLedgerEntry).where(WalletLedgerEntry.source_type == "payment_callback")
        ).all()
        wallet = session.scalars(select(WalletAccount).where(WalletAccount.user_id == user.id)).one()

        assert first.status == "success"
        assert second.status == "duplicate"
        assert len(recharges) == 1
        assert len(ledgers) == 1
        assert wallet.system_balance == Decimal("88.00")


def test_payment_callback_processor_rejects_invalid_signature(
    db_session_factory: sessionmaker[Session],
) -> None:
    from app.services.payment_callback_processor import PaymentCallbackProcessor

    with db_session_factory() as session:
        channel, user = _seed_payment_context(session)
        payload = {
            "amount": "18.00",
            "currency": "USD",
            "user_id": user.id,
            "order_id": "PAY-ORDER-INVALID",
        }

        result = PaymentCallbackProcessor(session=session).process_callback(
            channel_id=channel.id,
            payload=payload,
            signature="bad-signature",
        )
        session.flush()

        assert result.status == "signature_invalid"
        assert session.scalars(select(RechargeRecord)).all() == []
