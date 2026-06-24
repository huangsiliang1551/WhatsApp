"""AI Outbound Job 政策校验服务（spec 8.5 / 15.5）。

负责创建 AI 主动外发任务前对：
- 客服窗口（service window）：如果客户 24h 客服窗口内允许 service_window / free-form；
- Meta 模板：窗口外必须使用已审核 approved template；
- 用户 opt-in：未 opt-in 拒绝；
- 归属快照：必须携带当前 owner / AI assignment 快照；
- AI 不可用 / 永久迁移：必须 reject 或 skipped_policy。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    Conversation,
    HandoverLog,
    MemberProfile,
    Message,
    MessageTemplate,
    utc_now,
)
from app.db.ownership_models import AIOutboundJob, AIAgent


# Meta 客服窗口默认值：24 小时。
DEFAULT_SERVICE_WINDOW = timedelta(hours=24)


@dataclass
class OutboundPolicyDecision:
    allowed: bool
    reason: str
    message_policy: str
    template_required: bool
    snapshot: dict[str, Any] | None = None


class AIOutboundJobService:
    """AI 主动外发任务服务（政策校验 + 创建）。"""

    def __init__(self, session: Session, *, service_window: timedelta | None = None) -> None:
        self._session = session
        self._service_window = service_window or DEFAULT_SERVICE_WINDOW

    # ── 政策校验 ──
    def evaluate_policy(
        self,
        *,
        account_id: str,
        conversation_id: str | None = None,
        user_id: str | None = None,
        ai_agent_id: str,
        template_id: str | None = None,
        template_name: str | None = None,
        template_language: str | None = None,
        opt_in: bool = True,
    ) -> OutboundPolicyDecision:
        """返回 OutboundPolicyDecision；调用方根据 allowed 决定创建 / 跳过。"""
        if not opt_in:
            return OutboundPolicyDecision(
                allowed=False,
                reason="user_not_opted_in",
                message_policy="service_window",
                template_required=False,
            )

        agent = self._session.get(AIAgent, ai_agent_id)
        if agent is None:
            return OutboundPolicyDecision(
                allowed=False,
                reason="ai_agent_not_found",
                message_policy="service_window",
                template_required=False,
            )
        if agent.status not in {"active"}:
            return OutboundPolicyDecision(
                allowed=False,
                reason="ai_agent_not_active",
                message_policy="service_window",
                template_required=False,
            )

        in_service_window = self._in_service_window(
            account_id=account_id, conversation_id=conversation_id, user_id=user_id
        )
        if in_service_window:
            snapshot = self._build_snapshot(
                account_id=account_id, user_id=user_id, ai_agent_id=ai_agent_id
            )
            return OutboundPolicyDecision(
                allowed=True,
                reason="service_window",
                message_policy="service_window",
                template_required=False,
                snapshot=snapshot,
            )

        # 窗口外必须用 approved template
        if not template_id and not template_name:
            return OutboundPolicyDecision(
                allowed=False,
                reason="outside_window_template_required",
                message_policy="template_required",
                template_required=True,
            )
        template = self._resolve_template(
            account_id=account_id,
            template_id=template_id,
            template_name=template_name,
            template_language=template_language,
        )
        if template is None:
            return OutboundPolicyDecision(
                allowed=False,
                reason="template_not_found",
                message_policy="template_required",
                template_required=True,
            )
        if str(template.status).upper() != "APPROVED":
            return OutboundPolicyDecision(
                allowed=False,
                reason="template_not_approved",
                message_policy="template_required",
                template_required=True,
            )
        snapshot = self._build_snapshot(
            account_id=account_id, user_id=user_id, ai_agent_id=ai_agent_id
        )
        return OutboundPolicyDecision(
            allowed=True,
            reason="outside_window_template_approved",
            message_policy="template",
            template_required=True,
            snapshot=snapshot,
        )

    # ── 创建 ──
    def create_job(
        self,
        *,
        account_id: str,
        agency_id: str | None,
        site_id: str | None,
        ai_agent_id: str,
        user_id: str | None,
        member_profile_id: str | None,
        conversation_id: str | None,
        waba_id: str | None,
        phone_number_id: str | None,
        recipient_wa_id: str | None,
        trigger_type: str,
        generated_text: str | None,
        send_payload_json: dict[str, Any] | None = None,
        template_id: str | None = None,
        template_name: str | None = None,
        template_language: str | None = None,
        opt_in: bool = True,
        scheduled_at: Any = None,
        metadata_json: dict[str, Any] | None = None,
        source_entry_link_id: str | None = None,
    ) -> AIOutboundJob:
        decision = self.evaluate_policy(
            account_id=account_id,
            conversation_id=conversation_id,
            user_id=user_id,
            ai_agent_id=ai_agent_id,
            template_id=template_id,
            template_name=template_name,
            template_language=template_language,
            opt_in=opt_in,
        )
        snap = decision.snapshot or {}
        if not decision.allowed:
            skipped = AIOutboundJob(
                account_id=account_id,
                agency_id=agency_id,
                site_id=site_id,
                ai_agent_id=ai_agent_id,
                user_id=user_id,
                member_profile_id=member_profile_id,
                conversation_id=conversation_id,
                waba_id=waba_id,
                phone_number_id=phone_number_id,
                recipient_wa_id=recipient_wa_id,
                trigger_type=trigger_type,
                message_policy=decision.message_policy,
                template_id=template_id,
                template_name=template_name,
                template_language=template_language,
                generated_text=generated_text,
                send_payload_json=send_payload_json or {},
                source_entry_link_id=source_entry_link_id,
                owner_agency_id_snapshot=snap.get("owner_agency_id_snapshot"),
                owner_staff_user_id_snapshot=snap.get("owner_staff_user_id_snapshot"),
                owner_agency_member_id_snapshot=snap.get("owner_agency_member_id_snapshot"),
                owner_assignment_id_snapshot=snap.get("owner_assignment_id_snapshot"),
                ai_assignment_id_snapshot=snap.get("ai_assignment_id_snapshot"),
                status="skipped_policy",
                error_message=decision.reason,
                metadata_json=metadata_json or {"policy_reason": decision.reason},
            )
            self._session.add(skipped)
            self._session.commit()
            return skipped
        # 通过政策
        job = AIOutboundJob(
            account_id=account_id,
            agency_id=agency_id,
            site_id=site_id,
            ai_agent_id=ai_agent_id,
            user_id=user_id,
            member_profile_id=member_profile_id,
            conversation_id=conversation_id,
            waba_id=waba_id,
            phone_number_id=phone_number_id,
            recipient_wa_id=recipient_wa_id,
            trigger_type=trigger_type,
            message_policy=decision.message_policy,
            template_id=template_id,
            template_name=template_name,
            template_language=template_language,
            generated_text=generated_text,
            send_payload_json=send_payload_json or {},
            source_entry_link_id=source_entry_link_id,
            owner_agency_id_snapshot=snap.get("owner_agency_id_snapshot"),
            owner_staff_user_id_snapshot=snap.get("owner_staff_user_id_snapshot"),
            owner_agency_member_id_snapshot=snap.get("owner_agency_member_id_snapshot"),
            owner_assignment_id_snapshot=snap.get("owner_assignment_id_snapshot"),
            ai_assignment_id_snapshot=snap.get("ai_assignment_id_snapshot"),
            status="pending",
            scheduled_at=scheduled_at,
            metadata_json=metadata_json,
        )
        self._session.add(job)
        self._session.commit()
        return job

    # ── helpers ──
    def _in_service_window(
        self,
        *,
        account_id: str,
        conversation_id: str | None,
        user_id: str | None,
    ) -> bool:
        last_inbound_at: Any = None
        if conversation_id:
            conv = self._session.get(Conversation, conversation_id)
            if conv is not None:
                last_inbound_at = conv.last_customer_message_at or conv.last_message_at
        if last_inbound_at is None and user_id:
            row = self._session.execute(
                select(func.max(Message.created_at)).where(
                    Message.conversation_id.in_(
                        select(Conversation.id).where(
                            Conversation.account_id == account_id,
                            Conversation.customer_id == user_id,
                        )
                    ),
                    Message.direction == "inbound",
                )
            ).scalar()
            last_inbound_at = row
        if last_inbound_at is None:
            return False
        return (utc_now() - last_inbound_at) <= self._service_window

    def _resolve_template(
        self,
        *,
        account_id: str,
        template_id: str | None,
        template_name: str | None,
        template_language: str | None,
    ) -> MessageTemplate | None:
        stmt = select(MessageTemplate).where(MessageTemplate.account_id == account_id)
        if template_id:
            stmt = stmt.where(MessageTemplate.id == template_id)
        elif template_name:
            stmt = stmt.where(MessageTemplate.name == template_name)
        else:
            return None
        if template_language:
            stmt = stmt.where(MessageTemplate.language == template_language)
        return self._session.scalars(stmt).first()

    def _build_snapshot(
        self, *, account_id: str, user_id: str | None, ai_agent_id: str
    ) -> dict[str, Any]:
        snapshot: dict[str, Any] = {"ai_agent_id_snapshot": ai_agent_id}
        if not user_id:
            return snapshot
        member = self._session.scalar(
            select(MemberProfile).where(
                MemberProfile.account_id == account_id,
                MemberProfile.user_id == user_id,
            )
        )
        if member is not None:
            snapshot.update(
                {
                    "owner_agency_id_snapshot": member.current_owner_agency_id,
                    "owner_staff_user_id_snapshot": member.current_owner_staff_user_id,
                    "owner_agency_member_id_snapshot": member.current_owner_agency_member_id,
                    "owner_assignment_id_snapshot": member.current_owner_assignment_id,
                    "ai_assignment_id_snapshot": member.current_ai_assignment_id,
                }
            )
        return snapshot
