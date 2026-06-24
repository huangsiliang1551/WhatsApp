"""会话 AI 接待归属 + AI 兜底服务（spec 6.7, 6.8）。

入站优先级：
1. 识别客户身份。
2. 解析 entry_code / invite_code / wa.me text / referral metadata。
3. 客户已有 current AI binding 且可用 -> 优先用该 AI（sticky）。
4. 无 current AI -> 入口链接 AI。
5. 无入口链接 AI -> 站点默认 AI / AI pool。
6. AI 不可用 -> fallback chain。
7. 保存 ConversationAIAssignment + Conversation.current_*。

临时 failover 不更新 MemberProfile.current_ai_agent_id；永久迁移必须结束旧
MemberAIAssignment 并创建新 current assignment。
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.models import Conversation, MemberProfile, utc_now
from app.db.ownership_models import (
    AIAgent,
    AIFailoverEvent,
    ConversationAIAssignment,
    OwnershipAuditEvent,
)
from app.services.ai_agent_service import AIAgentService
from app.services.member_ownership_service import MemberAIOwnershipService

# AI 自动消息 delivery_mode 集合：这些模式的消息必须标记 ai_generated=true
# 并写 AI / 人力 / 链接快照（spec 8.4）。
AI_DELIVERY_MODES = {
    "ai_sync_reply",
    "ai_async_queued",
    "ai_generation_queued",
    "rule_auto_reply",
    "intent_auto_reply",
    "ai_outbound_job",
}


_WA_START_RE = re.compile(r"/start\s+([A-Za-z0-9\-_]+)")


def parse_entry_code_from_text(text: str | None) -> str | None:
    """从 wa.me text 或消息文本中解析 /start CODE。"""
    if not text:
        return None
    match = _WA_START_RE.search(text)
    return match.group(1) if match else None


class ConversationAIAssignmentService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def resolve_entry_context_from_inbound_message(
        self,
        *,
        account_id: str,
        conversation_id: str,
        text: str | None,
        waba_id: str | None = None,
        phone_number_id: str | None = None,
        customer_wa_id: str | None = None,
        user_id: str | None = None,
        entry_code: str | None = None,
        referral_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """解析入站 entry 上下文。

        返回 dict: entry_code, entry_link, resolved_user_id, member_profile_id。
        重复 webhook 不应重复消耗 EntryLink usage（由调用方传 idempotency_key）。
        """
        from app.services.entry_link_service import (
            EntryLinkNotFoundError,
            EntryLinkService,
        )

        resolved_code = entry_code or parse_entry_code_from_text(text)
        if not resolved_code and referral_metadata:
            resolved_code = referral_metadata.get("entry_code") or referral_metadata.get("ref")

        entry_link = None
        if resolved_code:
            svc = EntryLinkService(self._session)
            try:
                entry_link = svc.resolve_code(resolved_code, account_id=account_id)
            except EntryLinkNotFoundError:
                entry_link = None

        member_profile_id: str | None = None
        if user_id:
            member = self._session.scalar(
                select(MemberProfile).where(
                    MemberProfile.account_id == account_id,
                    MemberProfile.user_id == user_id,
                )
            )
            if member is not None:
                member_profile_id = member.id

        return {
            "entry_code": resolved_code,
            "entry_link": entry_link,
            "user_id": user_id,
            "member_profile_id": member_profile_id,
            "waba_id": waba_id,
            "phone_number_id": phone_number_id,
            "customer_wa_id": customer_wa_id,
        }

    def ensure_conversation_ai_assignment(
        self,
        *,
        account_id: str,
        conversation_id: str,
        entry_context: dict[str, Any],
        site_id: str | None = None,
        actor_id: str | None = None,
    ) -> ConversationAIAssignment:
        """按 sticky 规则解析本次会话实际接待 AI 并落库。

        优先级：客户 current AI（sticky）-> 入口链接 AI -> 站点默认 AI。
        """
        from app.db.models import H5Site

        user_id = entry_context.get("user_id")
        member_profile_id = entry_context.get("member_profile_id")
        entry_link = entry_context.get("entry_link")
        waba_id = entry_context.get("waba_id")
        phone_number_id = entry_context.get("phone_number_id")
        customer_wa_id = entry_context.get("customer_wa_id")

        agent_svc = AIAgentService(self._session)
        bound_ai_agent_id: str | None = None
        actual_ai_agent: AIAgent | None = None
        source_type: str = ""
        source_entry_link_id: str | None = entry_link.id if entry_link else None
        failover_from: str | None = None
        failover_reason: str | None = None

        # 1. sticky: 客户 current AI
        if user_id and account_id:
            member = self._session.scalar(
                select(MemberProfile).where(
                    MemberProfile.account_id == account_id,
                    MemberProfile.user_id == user_id,
                )
            )
            if member is not None and member.current_ai_agent_id:
                bound_ai_agent_id = member.current_ai_agent_id
                agent = agent_svc.require(member.current_ai_agent_id)
                if agent_svc.is_agent_available(agent, channel_context="whatsapp" if waba_id else None):
                    actual_ai_agent = agent
                    source_type = "member_current_ai"
                else:
                    # sticky agent 不可用：优先走它的 fallback chain（临时 failover）
                    fb = agent_svc.resolve_fallback_chain(
                        agent, site_id=site_id, account_id=account_id, reason="agent_unavailable",
                        channel_context="whatsapp" if waba_id else None,
                    )
                    if fb is not None:
                        actual_ai_agent = fb
                        failover_from = bound_ai_agent_id
                        failover_reason = "temporary_failover_agent_unavailable"
                        source_type = "temporary_failover"
                        self._session.add(
                            AIFailoverEvent(
                                account_id=account_id,
                                site_id=site_id,
                                event_type="temporary_failover",
                                from_ai_agent_id=failover_from,
                                to_ai_agent_id=fb.id,
                                conversation_id=conversation_id,
                                member_profile_id=member_profile_id,
                                user_id=user_id,
                                reason="agent_unavailable",
                            )
                        )

        # 2. 入口链接 AI
        if actual_ai_agent is None and entry_link is not None and entry_link.target_ai_agent_id:
            bound_ai_agent_id = entry_link.target_ai_agent_id
            agent = agent_svc.require(entry_link.target_ai_agent_id)
            if agent_svc.is_agent_available(agent, channel_context="whatsapp" if waba_id else None):
                actual_ai_agent = agent
                source_type = "ai_link"

        # 3. 站点默认 AI / phone 默认 AI（不覆盖已绑定的 bound agent）
        if actual_ai_agent is None and site_id:
            default_agent = agent_svc.ensure_default_agent_for_site(site_id)
            if default_agent is not None and agent_svc.is_agent_available(
                default_agent, channel_context="whatsapp" if waba_id else None
            ):
                actual_ai_agent = default_agent
                if not bound_ai_agent_id:
                    bound_ai_agent_id = default_agent.id
                source_type = "default_phone_ai"

        # 4. fallback chain for entry-link-bound agent (entry link AI 不可用时)
        if actual_ai_agent is None and bound_ai_agent_id and not failover_from:
            original = agent_svc.require(bound_ai_agent_id)
            fb = agent_svc.resolve_fallback_chain(
                original, site_id=site_id, account_id=account_id, reason="agent_unavailable",
                channel_context="whatsapp" if waba_id else None,
            )
            if fb is not None:
                actual_ai_agent = fb
                failover_from = bound_ai_agent_id
                failover_reason = "temporary_failover_agent_unavailable"
                source_type = "temporary_failover"
                self._session.add(
                    AIFailoverEvent(
                        account_id=account_id,
                        site_id=site_id,
                        event_type="temporary_failover",
                        from_ai_agent_id=failover_from,
                        to_ai_agent_id=fb.id,
                        conversation_id=conversation_id,
                        member_profile_id=member_profile_id,
                        user_id=user_id,
                        reason="agent_unavailable",
                    )
                )

        if actual_ai_agent is None:
            # 无可用 AI：标记待人工
            source_type = "rule_router"
            # 不创建 assignment，仅返回占位
            raise AttributionError(
                "无可用 AI Agent，且无 fallback；请配置站点默认 AI 或兜底客服。"
            )

        # 结束旧 current assignment
        self._session.execute(
            update(ConversationAIAssignment)
            .where(
                ConversationAIAssignment.account_id == account_id,
                ConversationAIAssignment.conversation_id == conversation_id,
                ConversationAIAssignment.is_current.is_(True),
            )
            .values(is_current=False, ended_at=utc_now())
        )
        assignment = ConversationAIAssignment(
            account_id=account_id,
            conversation_id=conversation_id,
            waba_id=waba_id,
            phone_number_id=phone_number_id,
            customer_wa_id=customer_wa_id,
            user_id=user_id,
            member_profile_id=member_profile_id,
            bound_ai_agent_id=bound_ai_agent_id,
            actual_ai_agent_id=actual_ai_agent.id,
            source_type=source_type,
            source_entry_link_id=source_entry_link_id,
            failover_from_ai_agent_id=failover_from,
            failover_reason=failover_reason,
            is_current=True,
            changed_by_actor_id=actor_id,
        )
        self._session.add(assignment)
        self._session.flush()

        # 同步 Conversation.current_*
        conv = self._session.get(Conversation, conversation_id)
        if conv is not None:
            conv.current_ai_agent_id = actual_ai_agent.id
            conv.current_ai_assignment_id = assignment.id
            if source_entry_link_id:
                conv.current_entry_link_id = source_entry_link_id
            conv.ai_failover_active = failover_from is not None
            conv.ai_failover_from_agent_id = failover_from
            conv.ai_failover_reason = failover_reason
            self._session.add(conv)
        return assignment

    def switch_conversation_ai(
        self,
        *,
        account_id: str,
        conversation_id: str,
        to_ai_agent_id: str,
        actor_id: str,
        reason: str | None = None,
    ) -> ConversationAIAssignment:
        """手动切换会话 AI。"""
        agent_svc = AIAgentService(self._session)
        new_agent = agent_svc.require(to_ai_agent_id)
        old = self._session.scalar(
            select(ConversationAIAssignment).where(
                ConversationAIAssignment.account_id == account_id,
                ConversationAIAssignment.conversation_id == conversation_id,
                ConversationAIAssignment.is_current.is_(True),
            )
        )
        if old is not None:
            old.is_current = False
            old.ended_at = utc_now()
            self._session.add(old)
        assignment = ConversationAIAssignment(
            account_id=account_id,
            conversation_id=conversation_id,
            user_id=old.user_id if old else None,
            member_profile_id=old.member_profile_id if old else None,
            bound_ai_agent_id=old.bound_ai_agent_id if old else to_ai_agent_id,
            actual_ai_agent_id=to_ai_agent_id,
            source_type="manual_switch",
            failover_from_ai_agent_id=old.actual_ai_agent_id if old else None,
            failover_reason=reason,
            is_current=True,
            changed_by_actor_id=actor_id,
            reason=reason,
        )
        self._session.add(assignment)
        self._session.flush()
        conv = self._session.get(Conversation, conversation_id)
        if conv is not None:
            conv.current_ai_agent_id = to_ai_agent_id
            conv.current_ai_assignment_id = assignment.id
            conv.ai_failover_active = False
            conv.ai_failover_from_agent_id = None
            self._session.add(conv)
        return assignment

    def get_current(self, *, account_id: str, conversation_id: str) -> ConversationAIAssignment | None:
        return self._session.scalar(
            select(ConversationAIAssignment).where(
                ConversationAIAssignment.account_id == account_id,
                ConversationAIAssignment.conversation_id == conversation_id,
                ConversationAIAssignment.is_current.is_(True),
            )
        )


class AttributionError(ValueError):
    pass


class AIFailoverService:
    """区分临时 failover 和永久迁移。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def temporary_failover(
        self,
        *,
        account_id: str,
        conversation_id: str,
        from_ai_agent_id: str,
        to_ai_agent_id: str,
        reason: str | None = None,
        actor_id: str | None = None,
    ) -> ConversationAIAssignment:
        """临时 failover：不更新 MemberProfile.current_ai_agent_id。

        创建/更新 ConversationAIAssignment，actual_ai_agent_id=to，failover_from=from。
        """
        svc = ConversationAIAssignmentService(self._session)
        old = svc.get_current(account_id=account_id, conversation_id=conversation_id)
        if old is not None:
            old.is_current = False
            old.ended_at = utc_now()
            self._session.add(old)
        assignment = ConversationAIAssignment(
            account_id=account_id,
            conversation_id=conversation_id,
            user_id=old.user_id if old else None,
            member_profile_id=old.member_profile_id if old else None,
            bound_ai_agent_id=from_ai_agent_id,
            actual_ai_agent_id=to_ai_agent_id,
            source_type="temporary_failover",
            failover_from_ai_agent_id=from_ai_agent_id,
            failover_reason=reason or "temporary_failover",
            is_current=True,
            changed_by_actor_id=actor_id,
        )
        self._session.add(assignment)
        self._session.flush()
        conv = self._session.get(Conversation, conversation_id)
        if conv is not None:
            conv.current_ai_agent_id = to_ai_agent_id
            conv.current_ai_assignment_id = assignment.id
            conv.ai_failover_active = True
            conv.ai_failover_from_agent_id = from_ai_agent_id
            conv.ai_failover_reason = reason
            self._session.add(conv)
        self._session.add(
            AIFailoverEvent(
                account_id=account_id,
                event_type="temporary_failover",
                from_ai_agent_id=from_ai_agent_id,
                to_ai_agent_id=to_ai_agent_id,
                conversation_id=conversation_id,
                reason=reason,
            )
        )
        self._session.add(
            OwnershipAuditEvent(
                account_id=account_id,
                action="ai_temporary_failover",
                target_type="conversation",
                target_id=conversation_id,
                actor_type="staff" if actor_id else "system",
                actor_id=actor_id,
                payload={"from": from_ai_agent_id, "to": to_ai_agent_id, "reason": reason},
            )
        )
        return assignment

    def permanent_migration(
        self,
        *,
        account_id: str,
        from_ai_agent_id: str,
        to_ai_agent_id: str,
        actor_id: str | None = None,
        reason: str | None = None,
    ) -> int:
        """永久迁移：结束旧 MemberAIAssignment，创建新 current，更新 MemberProfile。

        必要时更新打开会话的 ConversationAIAssignment。历史消息不变。
        """
        ai_svc = MemberAIOwnershipService(self._session)
        affected = ai_svc.auto_reassign_unavailable_ai(
            from_ai_agent_id=from_ai_agent_id,
            to_ai_agent_id=to_ai_agent_id,
            account_id=account_id,
            actor_id=actor_id,
            reason=reason,
        )
        # 更新打开会话的 current assignment
        open_convs = list(
            self._session.scalars(
                select(Conversation).where(
                    Conversation.account_id == account_id,
                    Conversation.current_ai_agent_id == from_ai_agent_id,
                    Conversation.status == "open",
                )
            ).all()
        )
        for conv in open_convs:
            conv.current_ai_agent_id = to_ai_agent_id
            conv.ai_failover_active = False
            conv.ai_failover_from_agent_id = None
            self._session.add(conv)
            old_assign = self._session.scalar(
                select(ConversationAIAssignment).where(
                    ConversationAIAssignment.conversation_id == conv.id,
                    ConversationAIAssignment.is_current.is_(True),
                )
            )
            if old_assign is not None:
                old_assign.is_current = False
                old_assign.ended_at = utc_now()
                self._session.add(old_assign)
            self._session.add(
                ConversationAIAssignment(
                    account_id=account_id,
                    conversation_id=conv.id,
                    actual_ai_agent_id=to_ai_agent_id,
                    source_type="auto_reassign",
                    failover_from_ai_agent_id=from_ai_agent_id,
                    failover_reason=reason or "permanent_migration",
                    is_current=True,
                    changed_by_actor_id=actor_id,
                )
            )
        self._session.add(
            AIFailoverEvent(
                account_id=account_id,
                event_type="permanent_migration",
                from_ai_agent_id=from_ai_agent_id,
                to_ai_agent_id=to_ai_agent_id,
                affected_count=affected,
                reason=reason,
                changed_by_actor_id=actor_id,
            )
        )
        self._session.add(
            OwnershipAuditEvent(
                account_id=account_id,
                action="ai_permanent_migration",
                target_type="ai_agent",
                target_id=from_ai_agent_id,
                actor_type="staff" if actor_id else "system",
                actor_id=actor_id,
                payload={"from": from_ai_agent_id, "to": to_ai_agent_id, "affected": affected, "reason": reason},
            )
        )
        return affected
