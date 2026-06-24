"""归属 / AI 接待 / 入口链接 报表服务（spec 第 13 节）。

提供：
- 当前归属（current_*）
- 历史快照（*_snapshot）
- AI 接待
- EntryLink 转化
- 异常
- AI outbound jobs 政策校验

所有统计查询均直接走 ORM；不缓存，不在内存中聚合全表。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.db.models import (
    Conversation,
    H5Site,
    MemberProfile,
    Message,
    utc_now,
)
from app.db.ownership_models import (
    AIAgent,
    AIOutboundJob,
    AIFailoverEvent,
    ConversationAIAssignment,
    EntryLink,
    MemberAIAssignment,
    MemberOwnerAssignment,
)


class OwnershipReportService:
    """只读报表聚合服务。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    # ── 1. 当前归属 ──
    def current_owner_breakdown(
        self, *, account_id: str | None = None
    ) -> dict[str, Any]:
        """当前每个客服名下会员数 + 未归属数。"""
        stmt = select(
            MemberProfile.current_owner_staff_user_id,
            func.count(MemberProfile.id).label("member_count"),
        ).group_by(MemberProfile.current_owner_staff_user_id)
        if account_id:
            stmt = stmt.where(MemberProfile.account_id == account_id)
        rows = self._session.execute(stmt).all()
        result = {
            "by_owner": [
                {
                    "owner_staff_user_id": r.current_owner_staff_user_id,
                    "member_count": int(r.member_count or 0),
                }
                for r in rows
                if r.current_owner_staff_user_id
            ],
            "unattributed": sum(
                int(r.member_count or 0)
                for r in rows
                if not r.current_owner_staff_user_id
            ),
        }
        return result

    def current_ai_breakdown(
        self, *, account_id: str | None = None
    ) -> dict[str, Any]:
        """当前每个 AI 绑定会员数 + 无 AI 会员数。"""
        stmt = select(
            MemberProfile.current_ai_agent_id,
            func.count(MemberProfile.id).label("member_count"),
        ).group_by(MemberProfile.current_ai_agent_id)
        if account_id:
            stmt = stmt.where(MemberProfile.account_id == account_id)
        rows = self._session.execute(stmt).all()
        result = {
            "by_ai_agent": [
                {
                    "ai_agent_id": r.current_ai_agent_id,
                    "member_count": int(r.member_count or 0),
                }
                for r in rows
                if r.current_ai_agent_id
            ],
            "no_ai_assignment": sum(
                int(r.member_count or 0)
                for r in rows
                if not r.current_ai_agent_id
            ),
        }
        return result

    # ── 2. 历史快照（按 owner / ai / source entry link 统计 messages） ──
    def history_owner_breakdown(
        self, *, account_id: str | None = None
    ) -> list[dict[str, Any]]:
        stmt = select(
            Message.owner_staff_user_id_snapshot,
            Message.direction,
            func.count(Message.id).label("message_count"),
        ).where(
            Message.owner_staff_user_id_snapshot.is_not(None),
        ).group_by(
            Message.owner_staff_user_id_snapshot, Message.direction
        )
        if account_id:
            stmt = stmt.where(Message.account_id == account_id)
        rows = self._session.execute(stmt).all()
        return [
            {
                "owner_staff_user_id": r.owner_staff_user_id_snapshot,
                "direction": r.direction,
                "message_count": int(r.message_count or 0),
            }
            for r in rows
        ]

    def history_ai_breakdown(
        self, *, account_id: str | None = None
    ) -> list[dict[str, Any]]:
        stmt = select(
            Message.ai_agent_id,
            func.count(Message.id).label("ai_message_count"),
        ).where(
            Message.ai_generated.is_(True),
            Message.ai_agent_id.is_not(None),
        ).group_by(Message.ai_agent_id)
        if account_id:
            stmt = stmt.where(Message.account_id == account_id)
        rows = self._session.execute(stmt).all()
        return [
            {
                "ai_agent_id": r.ai_agent_id,
                "ai_message_count": int(r.ai_message_count or 0),
            }
            for r in rows
        ]

    def history_entry_link_breakdown(
        self, *, account_id: str | None = None
    ) -> list[dict[str, Any]]:
        stmt = select(
            Message.source_entry_link_id_snapshot,
            func.count(Message.id).label("message_count"),
        ).where(
            Message.source_entry_link_id_snapshot.is_not(None),
        ).group_by(Message.source_entry_link_id_snapshot)
        if account_id:
            stmt = stmt.where(Message.account_id == account_id)
        rows = self._session.execute(stmt).all()
        return [
            {
                "entry_link_id": r.source_entry_link_id_snapshot,
                "message_count": int(r.message_count or 0),
            }
            for r in rows
        ]

    # ── 3. AI 接待报表 ──
    def ai_reception_summary(
        self,
        *,
        account_id: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> dict[str, Any]:
        """AI 自动消息 / 会话 / failover / handover。"""
        base = select(func.count(Message.id)).where(Message.ai_generated.is_(True))
        if account_id:
            base = base.where(Message.account_id == account_id)
        if since:
            base = base.where(Message.created_at >= since)
        if until:
            base = base.where(Message.created_at <= until)
        ai_message_count = int(self._session.execute(base).scalar() or 0)

        # conversations
        conv_stmt = select(func.count(Conversation.id))
        if account_id:
            conv_stmt = conv_stmt.where(Conversation.account_id == account_id)
        conversation_count = int(self._session.execute(conv_stmt).scalar() or 0)

        # failover events
        fo_stmt = select(func.count(AIFailoverEvent.id))
        if account_id:
            fo_stmt = fo_stmt.where(AIFailoverEvent.account_id == account_id)
        if since:
            fo_stmt = fo_stmt.where(AIFailoverEvent.created_at >= since)
        if until:
            fo_stmt = fo_stmt.where(AIFailoverEvent.created_at <= until)
        failover_count = int(self._session.execute(fo_stmt).scalar() or 0)

        # handover_logs
        from app.db.models import HandoverLog  # 延迟引入避免循环

        ho_stmt = select(func.count(HandoverLog.id))
        if account_id:
            ho_stmt = ho_stmt.where(HandoverLog.account_id == account_id)
        if since:
            ho_stmt = ho_stmt.where(HandoverLog.created_at >= since)
        if until:
            ho_stmt = ho_stmt.where(HandoverLog.created_at <= until)
        handover_count = int(self._session.execute(ho_stmt).scalar() or 0)

        return {
            "ai_message_count": ai_message_count,
            "conversation_count": conversation_count,
            "failover_event_count": failover_count,
            "handover_log_count": handover_count,
            "since": since.isoformat() if since else None,
            "until": until.isoformat() if until else None,
        }

    # ── 4. EntryLink 转化 ──
    def entry_link_conversion(
        self, *, account_id: str | None = None
    ) -> list[dict[str, Any]]:
        stmt = select(
            EntryLink.id,
            EntryLink.code,
            EntryLink.link_type,
            EntryLink.status,
            EntryLink.usage_count,
            EntryLink.last_used_at,
        )
        if account_id:
            stmt = stmt.where(EntryLink.account_id == account_id)
        links = list(self._session.scalars(stmt).all())
        results: list[dict[str, Any]] = []
        for link in links:
            # member_owners referencing this link
            members_registered = int(
                self._session.execute(
                    select(func.count(MemberOwnerAssignment.id)).where(
                        MemberOwnerAssignment.source_entry_link_id == link.id
                    )
                ).scalar()
                or 0
            )
            ai_assigned = int(
                self._session.execute(
                    select(func.count(MemberAIAssignment.id)).where(
                        MemberAIAssignment.source_entry_link_id == link.id
                    )
                ).scalar()
                or 0
            )
            conversations = int(
                self._session.execute(
                    select(func.count(ConversationAIAssignment.id)).where(
                        ConversationAIAssignment.source_entry_link_id == link.id
                    )
                ).scalar()
                or 0
            )
            ai_messages = int(
                self._session.execute(
                    select(func.count(Message.id)).where(
                        Message.source_entry_link_id_snapshot == link.id
                    )
                ).scalar()
                or 0
            )
            results.append(
                {
                    "entry_link_id": link.id,
                    "code": link.code,
                    "link_type": link.link_type,
                    "status": link.status,
                    "usage_count": int(link.usage_count or 0),
                    "last_used_at": link.last_used_at.isoformat() if link.last_used_at else None,
                    "members_registered": members_registered,
                    "ai_assigned": ai_assigned,
                    "conversations": conversations,
                    "ai_messages": ai_messages,
                }
            )
        return results

    # ── 5. 异常报表 ──
    def anomalies(
        self, *, account_id: str | None = None
    ) -> dict[str, Any]:
        # 无归属会员
        stmt_no_owner = select(func.count(MemberProfile.id)).where(
            MemberProfile.current_owner_staff_user_id.is_(None)
        )
        if account_id:
            stmt_no_owner = stmt_no_owner.where(MemberProfile.account_id == account_id)
        no_owner = int(self._session.execute(stmt_no_owner).scalar() or 0)

        # 无 AI 会员
        stmt_no_ai = select(func.count(MemberProfile.id)).where(
            MemberProfile.current_ai_agent_id.is_(None)
        )
        if account_id:
            stmt_no_ai = stmt_no_ai.where(MemberProfile.account_id == account_id)
        no_ai = int(self._session.execute(stmt_no_ai).scalar() or 0)

        # EntryLink 指向 disabled/archived AI
        bad_ai_link_stmt = select(func.count(EntryLink.id)).where(
            EntryLink.target_ai_agent_id.is_not(None),
            EntryLink.status == "active",
        )
        if account_id:
            bad_ai_link_stmt = bad_ai_link_stmt.where(EntryLink.account_id == account_id)
        all_active_ai_links = list(self._session.execute(bad_ai_link_stmt).all())
        bad_ai_link_count = 0
        for (link_id,) in all_active_ai_links:
            link = self._session.get(EntryLink, link_id)
            if link is None or link.target_ai_agent_id is None:
                continue
            agent = self._session.get(AIAgent, link.target_ai_agent_id)
            if agent is None or agent.status in {"disabled", "suspended", "archived", "deleted"}:
                bad_ai_link_count += 1

        # AI 无 fallback staff
        no_fallback_stmt = select(func.count(AIAgent.id)).where(
            AIAgent.fallback_staff_user_id.is_(None),
            AIAgent.status == "active",
        )
        if account_id:
            no_fallback_stmt = no_fallback_stmt.where(AIAgent.account_id == account_id)
        no_fallback_ai = int(self._session.execute(no_fallback_stmt).scalar() or 0)

        return {
            "no_owner_member_count": no_owner,
            "no_ai_member_count": no_ai,
            "entry_link_pointing_disabled_ai": bad_ai_link_count,
            "ai_without_fallback_staff": no_fallback_ai,
            "generated_at": utc_now().isoformat(),
        }

    # ── 综合入口 ──
    def ownership_report(
        self, *, account_id: str | None = None
    ) -> dict[str, Any]:
        return {
            "current": {
                "owner": self.current_owner_breakdown(account_id=account_id),
                "ai": self.current_ai_breakdown(account_id=account_id),
            },
            "history": {
                "owner": self.history_owner_breakdown(account_id=account_id),
                "ai": self.history_ai_breakdown(account_id=account_id),
                "entry_link": self.history_entry_link_breakdown(account_id=account_id),
            },
            "ai_reception": self.ai_reception_summary(account_id=account_id),
            "entry_links": self.entry_link_conversion(account_id=account_id),
            "anomalies": self.anomalies(account_id=account_id),
        }
