"""
CUS-002: Customer timeline service.

Merges events from multiple data sources (messages, tickets, verifications,
WhatsApp bindings, wallet ledger, withdrawals) sorted by created_at descending.
"""

from datetime import UTC, datetime

import structlog
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.db.models import (
    Conversation,
    MemberVerificationRequest,
    MemberWhatsAppBindingRequest,
    Message,
    Ticket,
    WalletLedgerEntry,
    WithdrawalRequest,
)
from app.schemas.platform import CustomerTimelineResponse, TimelineEvent

logger = structlog.get_logger()


class CustomerTimelineService:
    """Service for building a merged customer interaction timeline."""

    def __init__(self, session: Session) -> None:
        self._session = session

    async def get_timeline(
        self,
        customer_id: str,
        account_id: str | None = None,
        limit: int = 30,
    ) -> CustomerTimelineResponse:
        """Return merged timeline events sorted by time descending."""
        events: list[TimelineEvent] = []

        # 1. Messages
        msg_query = (
            select(Message)
            .join(Conversation, Message.conversation_id == Conversation.id)
            .where(Conversation.customer_id == customer_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        if account_id:
            msg_query = msg_query.where(Message.account_id == account_id)
        for msg in self._session.scalars(msg_query).all():
            direction_label = "入站" if msg.direction == "inbound" else "出站"
            preview = (msg.content_text or "")[:80]
            events.append(
                TimelineEvent(
                    type="message",
                    time=_fmt(msg.created_at),
                    summary=f"{direction_label}: {preview}",
                    metadata={
                        "message_id": msg.id,
                        "direction": msg.direction,
                        "conversation_id": msg.conversation_id,
                        "ai_generated": msg.ai_generated,
                    },
                )
            )

        # 2. Tickets
        ticket_query = (
            select(Ticket)
            .where(Ticket.user_id == customer_id)
            .order_by(Ticket.created_at.desc())
            .limit(limit)
        )
        if account_id:
            ticket_query = ticket_query.where(Ticket.account_id == account_id)
        for t in self._session.scalars(ticket_query).all():
            events.append(
                TimelineEvent(
                    type="ticket",
                    time=_fmt(t.created_at),
                    summary=f"工单 {t.ticket_no} 状态: {t.status}",
                    metadata={
                        "ticket_id": t.id,
                        "ticket_no": t.ticket_no,
                        "title": t.title,
                        "status": t.status,
                        "ticket_type": t.ticket_type,
                    },
                )
            )

        # 3. Member Verification Requests
        ver_query = (
            select(MemberVerificationRequest)
            .where(MemberVerificationRequest.member_profile_id == customer_id)
            .order_by(MemberVerificationRequest.created_at.desc())
            .limit(limit)
        )
        if account_id:
            ver_query = ver_query.where(MemberVerificationRequest.account_id == account_id)
        for v in self._session.scalars(ver_query).all():
            events.append(
                TimelineEvent(
                    type="verification",
                    time=_fmt(v.created_at),
                    summary=f"认证申请: {v.request_type} → {v.status}",
                    metadata={
                        "verification_id": v.id,
                        "request_type": v.request_type,
                        "status": v.status,
                    },
                )
            )

        # 4. WhatsApp Binding Requests
        wb_query = (
            select(MemberWhatsAppBindingRequest)
            .where(MemberWhatsAppBindingRequest.member_profile_id == customer_id)
            .order_by(MemberWhatsAppBindingRequest.created_at.desc())
            .limit(limit)
        )
        if account_id:
            wb_query = wb_query.where(MemberWhatsAppBindingRequest.account_id == account_id)
        for wb in self._session.scalars(wb_query).all():
            phone = wb.requested_phone_number or ""
            events.append(
                TimelineEvent(
                    type="whatsapp_binding",
                    time=_fmt(wb.created_at),
                    summary=f"WhatsApp 绑定申请: {phone} → {wb.status}",
                    metadata={
                        "binding_id": wb.id,
                        "phone_number": phone,
                        "status": wb.status,
                    },
                )
            )

        # 5. Wallet Ledger Entries
        wallet_query = (
            select(WalletLedgerEntry)
            .where(WalletLedgerEntry.user_id == customer_id)
            .order_by(WalletLedgerEntry.created_at.desc())
            .limit(limit)
        )
        if account_id:
            wallet_query = wallet_query.where(WalletLedgerEntry.account_id == account_id)
        for w in self._session.scalars(wallet_query).all():
            direction_sign = "+" if w.direction == "credit" else "-"
            events.append(
                TimelineEvent(
                    type="wallet",
                    time=_fmt(w.created_at),
                    summary=f"{w.ledger_type}: {direction_sign}{float(w.amount):.2f}",
                    metadata={
                        "ledger_id": w.id,
                        "ledger_type": w.ledger_type,
                        "amount": float(w.amount),
                        "direction": w.direction,
                        "note": w.note or "",
                    },
                )
            )

        # 6. Withdrawal Requests
        wd_query = (
            select(WithdrawalRequest)
            .where(WithdrawalRequest.user_id == customer_id)
            .order_by(WithdrawalRequest.created_at.desc())
            .limit(limit)
        )
        if account_id:
            wd_query = wd_query.where(WithdrawalRequest.account_id == account_id)
        for wd in self._session.scalars(wd_query).all():
            events.append(
                TimelineEvent(
                    type="withdrawal",
                    time=_fmt(wd.created_at),
                    summary=f"提现 {wd.request_no}: {float(wd.amount):.2f} → {wd.status}",
                    metadata={
                        "withdrawal_id": wd.id,
                        "request_no": wd.request_no,
                        "amount": float(wd.amount),
                        "status": wd.status,
                    },
                )
            )

        # 7. Sort all events by time descending
        events.sort(key=lambda e: e.time, reverse=True)

        # Apply limit after merge
        events = events[:limit]

        return CustomerTimelineResponse(events=events)


def _fmt(dt: datetime | None) -> str:
    """Format datetime to ISO string, or return empty string."""
    if dt is None:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.isoformat()
