"""Payment callback webhook with signature verification."""
import json
import structlog
from uuid import uuid4
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.db.models import AppUser, PaymentCallback, RechargeRecord, WalletAccount, WalletRechargeOrder, utc_now
from app.services.payment_channel_service import PaymentChannelService
from app.services.wallet_ledger_service import WalletLedgerService

logger = structlog.get_logger()
router = APIRouter(prefix="/api/payment", tags=["payment"])


@router.post("/callback/{channel_id}")
async def payment_callback(
    channel_id: str,
    request: Request,
    session: Session = Depends(get_db_session),
) -> dict:
    svc = PaymentChannelService(session)
    wallet_ledger_service = WalletLedgerService(session=session)

    # Get raw payload
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    signature = request.headers.get("X-Signature", "")
    signature_valid = svc.verify_callback_signature(channel_id, payload, signature)

    # Record callback
    cb = PaymentCallback(
        id=str(uuid4()),
        channel_id=channel_id,
        raw_payload=payload,
        signature_valid=signature_valid,
    )
    session.add(cb)
    session.flush()

    if not signature_valid:
        logger.warning("payment_callback_signature_invalid", channel_id=channel_id)
        # Record but don't process
        session.commit()
        return {"status": "signature_invalid", "callback_id": cb.id}

    # Process: create/update recharge record
    amount = Decimal(str(payload.get("amount", 0)))
    user_id = payload.get("user_id") or payload.get("customer_id", "")
    channel_order_id = payload.get("order_id") or payload.get("transaction_id", "")

    existing_recharge = session.query(RechargeRecord).filter(
        RechargeRecord.channel_order_id == channel_order_id,
        RechargeRecord.channel_id == channel_id,
    ).first()
    if existing_recharge is not None:
        cb.processed = True
        cb.processed_at = datetime.now(timezone.utc)
        cb.recharge_record_id = existing_recharge.id
        session.commit()
        logger.info("payment_callback_duplicate_ignored", channel_id=channel_id, order_id=channel_order_id)
        return {"status": "duplicate", "callback_id": cb.id, "recharge_record_id": existing_recharge.id}

    recharge = RechargeRecord(
        id=str(uuid4()),
        user_id=user_id,
        channel_id=channel_id,
        amount=amount,
        currency=payload.get("currency", "CNY"),
        status="completed",
        channel_order_id=channel_order_id,
        callback_data=payload,
        callback_verified=True,
    )
    session.add(recharge)
    session.flush()

    app_user = session.get(AppUser, user_id) if user_id else None
    if app_user is not None:
        wallet = session.query(WalletAccount).filter(
            WalletAccount.account_id == app_user.account_id,
            WalletAccount.user_id == app_user.id,
        ).first()
        if wallet is None:
            wallet = WalletAccount(
                account_id=app_user.account_id,
                user_id=app_user.id,
                currency=payload.get("currency", "CNY"),
            )
            session.add(wallet)
            session.flush()
        recharge_order = WalletRechargeOrder(
            account_id=app_user.account_id,
            wallet_account_id=wallet.id,
            user_id=app_user.id,
            amount=amount,
            currency=payload.get("currency", "CNY"),
            status="paid",
            credited_at=utc_now(),
        )
        session.add(recharge_order)
        session.flush()
        wallet_ledger_service.credit_system_balance(
            wallet=wallet,
            account_id=app_user.account_id,
            user_id=app_user.id,
            amount=amount,
            currency=payload.get("currency", "CNY"),
            transaction_type="recharge",
            source_type="payment_callback",
            note="Recharge credited from payment callback",
            reference_type="wallet_recharge_order",
            reference_id=recharge_order.id,
            fund_type="cash",
            is_real_recharge=True,
        )

    # Mark callback as processed
    cb.processed = True
    cb.processed_at = datetime.now(timezone.utc)
    cb.recharge_record_id = recharge.id

    session.commit()
    logger.info("payment_callback_processed", channel_id=channel_id, amount=str(amount), user_id=user_id)
    return {"status": "success", "callback_id": cb.id, "recharge_record_id": recharge.id}
