"""
RT-001: Conversation polling endpoint
RT-003: SSE streaming endpoint for real-time events
"""

import asyncio
import json
import structlog

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, get_db_session_factory, get_request_actor, SessionFactory
from app.core.auth import RequestActor
from app.core.settings import get_settings
from app.db.models import Conversation, HandoverLog, Message
from app.services.admin_auth_service import AdminAuthService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/conversations", tags=["conversations"])

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _query_events(
    session: Session,
    since_dt: datetime,
    account_id: str | None,
    actor: RequestActor | None,
) -> list[dict]:
    """Query new messages and handover logs since `since_dt`.

    Returns events in chronological order, each with an ``event`` key
    (``"new_message"`` or ``"handover"``).
    """
    events: list[dict] = []

    # 1. New messages — join Conversation to get external ID (frontend uses external ID, not UUID)
    msg_query = (
        select(Message, Conversation.external_conversation_id)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .where(Message.created_at > since_dt)
        .order_by(Message.created_at.asc())
        .limit(50)
    )
    if account_id:
        msg_query = msg_query.where(Message.account_id == account_id)

    for msg, ext_conv_id in session.execute(msg_query).all():
        if actor is not None and not actor.can_access_account(msg.account_id):
            continue
        events.append({
            "event": "new_message",
            "account_id": msg.account_id,
            "conversation_id": ext_conv_id,
            "message_id": msg.id,
            "direction": msg.direction,
            "preview": (msg.content_text or "")[:100],
            "created_at": _format_dt(msg.created_at),
        })

    # 2. Handover logs
    ho_query = (
        select(HandoverLog)
        .where(HandoverLog.created_at > since_dt)
        .order_by(HandoverLog.created_at.asc())
        .limit(20)
    )
    if account_id:
        ho_query = ho_query.where(HandoverLog.account_id == account_id)

    for log in session.scalars(ho_query).all():
        if actor is not None and not actor.can_access_account(log.account_id):
            continue
        events.append({
            "event": "handover",
            "account_id": log.account_id,
            "conversation_id": log.conversation_id,
            "from_mode": log.from_mode,
            "to_mode": log.to_mode,
            "agent_id": log.triggered_by_id,
            "created_at": _format_dt(log.created_at),
        })

    events.sort(key=lambda e: e["created_at"])
    return events


def _format_dt(dt: datetime) -> str:
    """Format a datetime to ISO8601 string with Z suffix."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/poll")
async def poll_conversation_events(
    since: str = Query(..., description="ISO8601 timestamp"),
    account_id: str | None = Query(default=None),
    actor: RequestActor = Depends(get_request_actor),
    session: Session = Depends(get_db_session),
) -> dict:
    """Return events (new messages and handovers) that occurred after `since` timestamp.

    Used by frontend chatRealtime.ts for polling fallback when SSE is unavailable.
    """
    try:
        since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Invalid 'since' format: {exc}",
        ) from exc

    events = _query_events(session, since_dt, account_id, actor)
    return {
        "events": events,
        "server_time": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }


@router.get("/stream")
async def conversation_stream(
    request: Request,
    token: str = Query(..., description="JWT access token"),
    account_id: str | None = Query(default=None),
    session_factory: SessionFactory = Depends(get_db_session_factory),
) -> StreamingResponse:
    """SSE endpoint for real-time conversation events.

    Authenticates via JWT token in query string (EventSource does not
    support custom headers).  Streams ``new_message`` and ``handover``
    named events to connected clients.

    The frontend chatRealtime.ts connects here first; on failure it falls
    back to GET /api/conversations/poll every 5 seconds.
    """
    # ---- JWT auth ----------------------------------------------------------
    settings = get_settings()
    auth_service = AdminAuthService(
        jwt_secret=settings.admin_jwt_secret,
        access_token_ttl_minutes=settings.admin_access_token_ttl_minutes,
        refresh_token_ttl_days=settings.admin_refresh_token_ttl_days,
        default_username=settings.admin_default_username,
        default_password=settings.admin_default_password,
    )
    try:
        admin_user = auth_service.verify_token(token)
    except HTTPException:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
        )

    # ---- SSE event stream --------------------------------------------------
    POLL_INTERVAL = 2  # seconds between DB polls
    HEARTBEAT_INTERVAL = 15  # seconds between heartbeat comments

    async def event_generator():
        since = datetime.now(UTC)
        last_heartbeat = datetime.now(UTC)
        client_ip = request.client.host if request.client else "unknown"

        logger.info("sse_client_connected", client_ip=client_ip, user=admin_user.user_id)

        try:
            while True:
                # Honour client disconnect
                if await request.is_disconnected():
                    logger.info("sse_client_disconnected", client_ip=client_ip)
                    break

                # Poll DB for new events
                session = session_factory()
                try:
                    events = _query_events(session, since, account_id, actor=None)
                finally:
                    session.close()

                # Emit each event as a named SSE event
                for evt in events:
                    event_type = evt.pop("event")
                    data_json = json.dumps(evt, ensure_ascii=False, default=str)
                    yield f"event: {event_type}\ndata: {data_json}\n\n"

                    # Advance cursor past this event's timestamp
                    created_str = evt.get("created_at")
                    if created_str:
                        try:
                            ts = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                            if ts > since:
                                since = ts
                        except ValueError:
                            pass

                # Periodic heartbeat to keep proxy/load-balancer from closing
                now = datetime.now(UTC)
                if (now - last_heartbeat).total_seconds() >= HEARTBEAT_INTERVAL:
                    yield ": heartbeat\n\n"
                    last_heartbeat = now

                await asyncio.sleep(POLL_INTERVAL)

        except asyncio.CancelledError:
            logger.info("sse_stream_cancelled", client_ip=client_ip)
        except Exception:
            logger.exception("sse_stream_error", client_ip=client_ip)
        finally:
            logger.info("sse_stream_ended", client_ip=client_ip)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
