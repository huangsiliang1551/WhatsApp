"""归属快照服务（spec 6.4）。

所有创建业务记录的地方必须调用本服务获取快照，不允许各 service 自己拼 snapshot。
划转会员 / AI 时绝不更新旧业务记录 snapshot；报表按 snapshot 统计历史。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Conversation, MemberProfile
from app.db.ownership_models import (
    ConversationAIAssignment,
    MemberAIAssignment,
    MemberOwnerAssignment,
)


@dataclass(frozen=True)
class OwnerSnapshot:
    """归属快照值对象，写入业务记录的 owner_*_snapshot / ai_*_snapshot 字段。"""

    owner_agency_id_snapshot: str | None
    owner_staff_user_id_snapshot: str | None
    owner_agency_member_id_snapshot: str | None
    owner_assignment_id_snapshot: str | None
    ai_agent_id_snapshot: str | None
    ai_assignment_id_snapshot: str | None
    source_entry_link_id_snapshot: str | None
    snapshot_source: str = "live"
    # live / migration_default / inferred / unknown
    snapshot_confidence: str = "high"
    # high / medium / low

    def as_dict(self) -> dict[str, Any]:
        return {
            "owner_agency_id_snapshot": self.owner_agency_id_snapshot,
            "owner_staff_user_id_snapshot": self.owner_staff_user_id_snapshot,
            "owner_agency_member_id_snapshot": self.owner_agency_member_id_snapshot,
            "owner_assignment_id_snapshot": self.owner_assignment_id_snapshot,
            "ai_agent_id_snapshot": self.ai_agent_id_snapshot,
            "ai_assignment_id_snapshot": self.ai_assignment_id_snapshot,
            "source_entry_link_id_snapshot": self.source_entry_link_id_snapshot,
            "snapshot_source": self.snapshot_source,
            "snapshot_confidence": self.snapshot_confidence,
        }

    @classmethod
    def empty(cls, *, source: str = "unknown", confidence: str = "low") -> OwnerSnapshot:
        return cls(
            owner_agency_id_snapshot=None,
            owner_staff_user_id_snapshot=None,
            owner_agency_member_id_snapshot=None,
            owner_assignment_id_snapshot=None,
            ai_agent_id_snapshot=None,
            ai_assignment_id_snapshot=None,
            source_entry_link_id_snapshot=None,
            snapshot_source=source,
            snapshot_confidence=confidence,
        )


class OwnershipSnapshotService:
    """构建归属快照的核心服务。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def build_snapshot_for_user(self, account_id: str, user_id: str) -> OwnerSnapshot:
        """按 account_id + user_id 构建当前归属快照。

        优先读 MemberProfile.current_*；若会员不存在或无归属，返回 unknown 快照。
        """
        member = self._session.scalar(
            select(MemberProfile).where(
                MemberProfile.account_id == account_id,
                MemberProfile.user_id == user_id,
            )
        )
        if member is None:
            return OwnerSnapshot.empty()
        return self._snapshot_from_member(member)

    def build_snapshot_for_member_profile(
        self, account_id: str, member_profile_id: str
    ) -> OwnerSnapshot:
        member = self._session.get(MemberProfile, member_profile_id)
        if member is None or member.account_id != account_id:
            return OwnerSnapshot.empty()
        return self._snapshot_from_member(member)

    def build_snapshot_for_conversation(
        self, account_id: str, conversation_id: str
    ) -> OwnerSnapshot:
        """按会话构建快照：优先用会话当前归属快照，回退到会员归属。"""
        conv = self._session.scalar(
            select(Conversation).where(
                Conversation.account_id == account_id,
                Conversation.id == conversation_id,
            )
        )
        if conv is None:
            return OwnerSnapshot.empty()
        # 若会话已有 current owner snapshot（人工归属），用它
        if conv.current_owner_staff_user_id_snapshot is not None:
            return OwnerSnapshot(
                owner_agency_id_snapshot=conv.current_owner_agency_id_snapshot,
                owner_staff_user_id_snapshot=conv.current_owner_staff_user_id_snapshot,
                owner_agency_member_id_snapshot=conv.current_owner_agency_member_id_snapshot,
                owner_assignment_id_snapshot=conv.current_owner_assignment_id_snapshot,
                ai_agent_id_snapshot=conv.current_ai_agent_id,
                ai_assignment_id_snapshot=conv.current_ai_assignment_id,
                source_entry_link_id_snapshot=conv.current_entry_link_id,
            )
        # 回退到客户/会员归属
        if conv.customer_id:
            snap = self.build_snapshot_for_user(account_id, conv.customer_id)
            if snap.snapshot_source != "unknown":
                return snap
        return OwnerSnapshot.empty()

    def build_snapshot_for_ai_message(
        self,
        account_id: str,
        conversation_id: str,
        ai_agent_id: str | None,
        entry_link_id: str | None = None,
    ) -> OwnerSnapshot:
        """AI 消息快照：会话 owner snapshot + AI agent + entry link。"""
        snap = self.build_snapshot_for_conversation(account_id, conversation_id)
        return OwnerSnapshot(
            owner_agency_id_snapshot=snap.owner_agency_id_snapshot,
            owner_staff_user_id_snapshot=snap.owner_staff_user_id_snapshot,
            owner_agency_member_id_snapshot=snap.owner_agency_member_id_snapshot,
            owner_assignment_id_snapshot=snap.owner_assignment_id_snapshot,
            ai_agent_id_snapshot=ai_agent_id or snap.ai_agent_id_snapshot,
            ai_assignment_id_snapshot=snap.ai_assignment_id_snapshot,
            source_entry_link_id_snapshot=entry_link_id or snap.source_entry_link_id_snapshot,
            snapshot_source=snap.snapshot_source if snap.snapshot_source != "unknown" else "inferred",
            snapshot_confidence=snap.snapshot_confidence if snap.snapshot_confidence != "low" else "medium",
        )

    def apply_snapshot_to_model(self, model: Any, snapshot: OwnerSnapshot) -> None:
        """把快照字段写到任意业务模型上（模型需有对应 nullable 列）。"""
        for key, value in snapshot.as_dict().items():
            if hasattr(model, key):
                setattr(model, key, value)

    def _snapshot_from_member(self, member: MemberProfile) -> OwnerSnapshot:
        if (
            member.current_owner_staff_user_id is None
            and member.current_ai_agent_id is None
        ):
            return OwnerSnapshot.empty()
        return OwnerSnapshot(
            owner_agency_id_snapshot=member.current_owner_agency_id,
            owner_staff_user_id_snapshot=member.current_owner_staff_user_id,
            owner_agency_member_id_snapshot=member.current_owner_agency_member_id,
            owner_assignment_id_snapshot=member.current_owner_assignment_id,
            ai_agent_id_snapshot=member.current_ai_agent_id,
            ai_assignment_id_snapshot=member.current_ai_assignment_id,
            source_entry_link_id_snapshot=member.registration_entry_link_id,
        )
