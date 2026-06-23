"""Payment callback webhook with signature verification."""
import json
import structlog
from uuid import uuid4
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.db.models import PaymentCallback, RechargeRecord
from app.services.payment_channel_service import PaymentChannelService

logger = structlog.get_logger()
router = APIRouter(prefix="/api/payment", tags=["payment"])


@router.post("/callback/{channel_id}")
async def payment_callback(
    channel_id: str,
    request: Request,
    session: Session = Depends(get_db_session),
) -> dict:
    svc = PaymentChannelService(session)

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
        return {"status": "signature_invalid", "callback_id": cb.id}

    # Process: create/update recharge record
    amount = Decimal(str(payload.get("amount", 0)))
    user_id = payload.get("user_id") or payload.get("customer_id", "")
    channel_order_id = payload.get("order_id") or payload.get("transaction_id", "")

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

    # Mark callback as processed
    cb.processed = True
    cb.processed_at = datetime.now(timezone.utc)
    cb.recharge_record_id = recharge.id

    session.flush()

    # Auto-retry: update on duplicate order
    existing_recharge = session.query(RechargeRecord).filter(
        RechargeRecord.channel_order_id == channel_order_id,
        RechargeRecord.channel_id == channel_id,
    ).first()
    if existing_recharge and existing_recharge.id != recharge.id:
        # Duplicate callback, use existing record
        session.delete(recharge)
        session.flush()

    logger.info("payment_callback_processed", channel_id=channel_id, amount=str(amount), user_id=user_id)
    return {"status": "success", "callback_id": cb.id}
