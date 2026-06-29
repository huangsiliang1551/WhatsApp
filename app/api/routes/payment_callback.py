"""Payment callback webhook with signature verification."""
import structlog

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.services.payment_callback_processor import PaymentCallbackProcessor

logger = structlog.get_logger()
router = APIRouter(prefix="/api/payment", tags=["payment"])


@router.post("/callback/{channel_id}")
async def payment_callback(
    channel_id: str,
    request: Request,
    session: Session = Depends(get_db_session),
) -> dict:
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    result = PaymentCallbackProcessor(session=session).process_callback(
        channel_id=channel_id,
        payload=payload,
        signature=request.headers.get("X-Signature", ""),
    )
    session.commit()
    logger.info(
        "payment_callback_processed",
        channel_id=channel_id,
        callback_id=result.callback_id,
        status=result.status,
        recharge_record_id=result.recharge_record_id,
    )
    response = {"status": result.status, "callback_id": result.callback_id}
    if result.recharge_record_id is not None:
        response["recharge_record_id"] = result.recharge_record_id
    return response
