from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import structlog
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    AppUser,
    Conversation,
    MemberVerificationRequest,
    MemberWhatsAppBindingRequest,
    Ticket,
    UserIdentity,
    WalletAccount,
    WalletLedgerEntry,
    WithdrawalRequest,
)

logger = structlog.get_logger()


class CustomerSummaryService:
    def __init__(self, session: Session) -> None:
        self._session = session

    async def get_summary(
        self,
        customer_id: str,
        account_id: str | None = None,
    ) -> dict:
        customer, conversations, tickets, wallet, member_status = await asyncio.gather(
            self._get_customer(customer_id, account_id),
            self._get_conversations(customer_id, account_id),
            self._get_tickets(customer_id, account_id),
            self._get_wallet(customer_id, account_id),
            self._get_member_status(customer_id, account_id),
        )
        return {
            "customer": customer,
            "member_status": member_status,
            "conversations": conversations,
            "tickets": tickets,
            "wallet": wallet,
            "tags": self._collect_tags(conversations, customer),
        }

    async def _get_customer(self, customer_id: str, account_id: str | None = None) -> dict:
        query = select(AppUser).where(AppUser.id == customer_id)
        if account_id:
            query = query.where(AppUser.account_id == account_id)
        user = self._session.execute(query).scalar_one_or_none()
        if user is None:
            return {}

        # Detect multi-IP registration for the same phone number
        registration_ips: list[str] = []
        multi_ip = False
        if user.has_phone:
            phone_identity = self._session.scalars(
                select(UserIdentity).where(
                    UserIdentity.user_id == user.id,
                    UserIdentity.identity_type == "phone",
                )
            ).first()
            if phone_identity:
                same_phone_users = self._session.scalars(
                    select(AppUser).join(UserIdentity, UserIdentity.user_id == AppUser.id).where(
                        UserIdentity.identity_type == "phone",
                        UserIdentity.identity_value == phone_identity.identity_value,
                        AppUser.id != user.id,
                    )
                ).all()
                all_users = [user] + list(same_phone_users)
                ips = {u.registration_ip for u in all_users if u.registration_ip}
                registration_ips = sorted(ips)
                multi_ip = len(registration_ips) > 1

        return {
            "id": user.id,
            "public_user_id": user.public_user_id,
            "display_name": user.display_name,
            "language": user.language_code,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "lifecycle_status": user.lifecycle_status,
            "registration_ip": user.registration_ip,
            "registration_ips": registration_ips,
            "multi_ip": multi_ip,
        }

    async def _get_conversations(self, customer_id: str, account_id: str | None = None) -> dict:
        query = select(Conversation).where(Conversation.customer_id == customer_id)
        if account_id:
            query = query.where(Conversation.account_id == account_id)
        rows = self._session.execute(query).scalars().all()
        total = len(rows)
        open_count = sum(1 for c in rows if c.status == "open")
        items = []
        for c in rows[:10]:
            items.append({
                "conversation_id": c.external_conversation_id,
                "account_id": c.account_id,
                "management_mode": c.management_mode,
                "last_message_at": c.last_message_at.isoformat() if c.last_message_at else None,
                "last_message_preview": None,
            })
        return {"total": total, "open": open_count, "items": items}

    async def _get_tickets(self, customer_id: str, account_id: str | None = None) -> dict:
        query = select(Ticket).where(Ticket.user_id == customer_id)
        if account_id:
            query = query.where(Ticket.account_id == account_id)
        rows = self._session.execute(query).scalars().all()
        total = len(rows)
        open_count = sum(1 for t in rows if t.status in ("open", "in_progress"))
        items = []
        for t in rows[:10]:
            items.append({
                "ticket_no": t.ticket_no,
                "title": t.title,
                "status": t.status,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            })
        return {"total": total, "open": open_count, "items": items}

    async def _get_wallet(self, customer_id: str, account_id: str | None = None) -> dict:
        query = select(WalletAccount).where(WalletAccount.user_id == customer_id)
        if account_id:
            query = query.where(WalletAccount.account_id == account_id)
        wallet = self._session.execute(query).scalar_one_or_none()
        if wallet is None:
            return {"balance": 0, "total_recharged": 0, "total_withdrawn": 0, "recent_transactions": []}

        wa_id = wallet.id
        ledger_query = select(WalletLedgerEntry).where(
            WalletLedgerEntry.wallet_account_id == wa_id,
        ).order_by(WalletLedgerEntry.created_at.desc()).limit(10)
        entries = self._session.execute(ledger_query).scalars().all()

        total_recharged = sum(
            float(e.amount) for e in entries
            if e.direction == "credit" and e.ledger_type in ("recharge", "reward", "task")
        ) if entries else 0

        withdrawal_query = select(func.coalesce(func.sum(WithdrawalRequest.amount), 0)).where(
            WithdrawalRequest.wallet_account_id == wa_id,
            WithdrawalRequest.status.in_(["paid", "processing"]),
        )
        total_withdrawn = float(self._session.scalar(withdrawal_query) or 0)

        recent = []
        for e in entries[:5]:
            recent.append({
                "type": e.ledger_type,
                "amount": float(e.amount),
                "direction": e.direction,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            })

        return {
            "balance": float(wallet.system_balance + wallet.task_balance),
            "total_recharged": round(total_recharged, 2) if entries else 0,
            "total_withdrawn": round(total_withdrawn, 2),
            "recent_transactions": recent,
        }

    async def _get_member_status(self, customer_id: str, account_id: str | None = None) -> dict:
        verification = {}
        whatsapp_binding = {}

        v_query = select(MemberVerificationRequest).where(
            MemberVerificationRequest.member_profile_id == customer_id,
        ).order_by(MemberVerificationRequest.created_at.desc()).limit(1)
        if account_id:
            v_query = v_query.where(MemberVerificationRequest.account_id == account_id)
        v_row = self._session.execute(v_query).scalar_one_or_none()
        if v_row:
            verification = {
                "status": v_row.status,
                "request_type": v_row.request_type,
                "updated_at": v_row.created_at.isoformat() if v_row.created_at else None,
            }

        wb_query = select(MemberWhatsAppBindingRequest).where(
            MemberWhatsAppBindingRequest.member_profile_id == customer_id,
        ).order_by(MemberWhatsAppBindingRequest.created_at.desc()).limit(1)
        if account_id:
            wb_query = wb_query.where(MemberWhatsAppBindingRequest.account_id == account_id)
        wb_row = self._session.execute(wb_query).scalar_one_or_none()
        if wb_row:
            phone = wb_row.requested_phone_number or ""
            if len(phone) > 4:
                phone = phone[:3] + "****" + phone[-4:]
            whatsapp_binding = {
                "status": "bound" if wb_row.status == "approved" else wb_row.status,
                "phone_number": phone,
                "updated_at": wb_row.created_at.isoformat() if wb_row.created_at else None,
            }

        return {"verification": verification, "whatsapp_binding": whatsapp_binding}

    def _collect_tags(self, conversations: dict, customer: dict) -> list[str]:
        tags: set[str] = set()
        for c in conversations.get("items", []):
            if c.get("tags"):
                tags.update(c["tags"])
        return sorted(tags)
