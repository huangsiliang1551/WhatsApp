from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import structlog
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    AppUser,
    Conversation,
    MemberProfile,
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
        customer, conversations, tickets, wallet, member_status, member_profile = await asyncio.gather(
            self._get_customer(customer_id, account_id),
            self._get_conversations(customer_id, account_id),
            self._get_tickets(customer_id, account_id),
            self._get_wallet(customer_id, account_id),
            self._get_member_status(customer_id, account_id),
            self._get_member_profile(customer_id, account_id),
        )
        return {
            "customer": customer,
            "member_status": member_status,
            "member_profile": member_profile,
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
        same_ip_user_count = 0
        registration_location = self._format_registration_location(user.registration_ip)
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

        if user.registration_ip:
            same_ip_user_count = int(
                self._session.scalar(
                    select(func.count(AppUser.id)).where(
                        AppUser.account_id == user.account_id,
                        AppUser.registration_ip == user.registration_ip,
                    )
                )
                or 0
            )

        return {
            "id": user.id,
            "public_user_id": user.public_user_id,
            "display_name": user.display_name,
            "language": user.language_code,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "lifecycle_status": user.lifecycle_status,
            "registration_ip": user.registration_ip,
            "registration_ips": registration_ips,
            "registration_location": registration_location,
            "same_ip_user_count": same_ip_user_count,
            "multi_ip": multi_ip,
        }

    @staticmethod
    def _format_registration_location(ip: str | None) -> str:
        if not ip:
            return "-"
        normalized = ip.strip().lower()
        if normalized in {"127.0.0.1", "::1", "localhost"}:
            return "本机"
        return "-"

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
            return {
                "balance": 0,
                "system_balance": 0,
                "task_balance": 0,
                "total_recharged": 0,
                "total_withdrawn": 0,
                "recent_transactions": [],
            }

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
            "system_balance": float(wallet.system_balance),
            "task_balance": float(wallet.task_balance),
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

    async def _get_member_profile(
        self, customer_id: str, account_id: str | None = None
    ) -> dict:
        """返回当前 MemberProfile 的归属快照（spec 5.7）。

        customer_id 既可能是 AppUser.id，也可能是 public_user_id。
        同一 account 下两者都能命中（spec 5.7 唯一约束 (account_id, user_id)）。
        """
        from sqlalchemy import or_

        # Step 1: 先用 AppUser.id 找到 user 行（兼容 customer_id 直接传 id）
        user_query = select(AppUser).where(AppUser.id == customer_id)
        if account_id:
            user_query = user_query.where(AppUser.account_id == account_id)
        user = self._session.execute(user_query).scalar_one_or_none()
        if user is None:
            # Step 2: fallback 到 public_user_id
            user_query = select(AppUser).where(AppUser.public_user_id == customer_id)
            if account_id:
                user_query = user_query.where(AppUser.account_id == account_id)
            user = self._session.execute(user_query).scalar_one_or_none()
        if user is None:
            return self._empty_member_profile()

        profile_query = select(MemberProfile).where(MemberProfile.user_id == user.id)
        if account_id:
            profile_query = profile_query.where(MemberProfile.account_id == account_id)
        member = self._session.execute(profile_query).scalar_one_or_none()
        if member is None:
            return self._empty_member_profile()

        return {
            "member_profile_id": member.id,
            "member_no": member.member_no,
            "current_owner_agency_id": member.current_owner_agency_id,
            "current_owner_staff_user_id": member.current_owner_staff_user_id,
            "current_owner_agency_member_id": member.current_owner_agency_member_id,
            "current_owner_assignment_id": member.current_owner_assignment_id,
            "owner_assigned_at": (
                member.owner_assigned_at.isoformat() if member.owner_assigned_at else None
            ),
            "current_ai_agent_id": member.current_ai_agent_id,
            "current_ai_assignment_id": member.current_ai_assignment_id,
            "ai_assigned_at": (
                member.ai_assigned_at.isoformat() if member.ai_assigned_at else None
            ),
            "registration_entry_link_id": member.registration_entry_link_id,
            "registration_ai_agent_id": member.registration_ai_agent_id,
            "registration_staff_user_id": member.registration_staff_user_id,
            "registration_channel": member.registration_channel,
            "registration_source_type": member.registration_source_type,
            "attribution_status": member.attribution_status,
        }

    @staticmethod
    def _empty_member_profile() -> dict:
        return {
            "member_profile_id": None,
            "member_no": None,
            "current_owner_agency_id": None,
            "current_owner_staff_user_id": None,
            "current_owner_agency_member_id": None,
            "current_owner_assignment_id": None,
            "owner_assigned_at": None,
            "current_ai_agent_id": None,
            "current_ai_assignment_id": None,
            "ai_assigned_at": None,
            "registration_entry_link_id": None,
            "registration_ai_agent_id": None,
            "registration_staff_user_id": None,
            "registration_channel": None,
            "registration_source_type": None,
            "attribution_status": "unattributed",
        }
