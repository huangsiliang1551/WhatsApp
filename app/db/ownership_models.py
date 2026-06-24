"""客户归属 / AI 接待归属 / 入口链接 数据模型。

按 whatsapp_attribution_ai_implementation_spec.md 第 5 节设计。为避免
``app/db/models.py`` 继续膨胀（spec P3-01），归属相关新表集中在本模块定义，
并通过 ``app/db/models.py`` 末尾的 import 注册到 ``Base.metadata``。

现有 MemberProfile / Conversation / Message / H5Site 的扩展字段直接在
``app/db/models.py`` 中以新增 nullable 列方式添加，保持单一表定义。
"""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models import TimestampMixin, new_id, utc_now


class EntryLink(Base, TimestampMixin):
    """统一入口链接表：客服注册链接 / AI H5 注册链接 / AI WhatsApp 对话链接 /
    会员邀请入口映射 / 站点总客服链接 / 站点总 AI 链接 / 二维码 / 广告链接。

    完整 URL 不作为唯一事实来源，由 ``EntryLink + Site + WABA/phone`` 派生。
    """

    __tablename__ = "entry_links"
    __table_args__ = (
        UniqueConstraint("code", name="uq_entry_links_code"),
        Index("ix_entry_links_site_type", "site_id", "link_type"),
        Index("ix_entry_links_target", "target_type", "target_staff_user_id", "target_ai_agent_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False, index=True)
    agency_id: Mapped[str | None] = mapped_column(ForeignKey("agencies.id"), index=True)
    site_id: Mapped[str | None] = mapped_column(ForeignKey("h5_sites.id"), index=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    link_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    # staff_register / ai_register / ai_chat / staff_ai_register / member_invite /
    # site_default_staff / site_default_ai / qr / ad
    channel: Mapped[str] = mapped_column(String(32), nullable=False, default="h5")
    # h5 / whatsapp / qr / ad / manual
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active", index=True)
    # active / disabled / revoked / expired / target_unavailable / usage_limit_reached

    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    # staff / ai_agent / member / site / staff_ai

    target_staff_user_id: Mapped[str | None] = mapped_column(String(128), index=True)
    target_agency_member_id: Mapped[str | None] = mapped_column(String(128), index=True)
    target_ai_agent_id: Mapped[str | None] = mapped_column(ForeignKey("ai_agents.id"), index=True)
    referrer_user_id: Mapped[str | None] = mapped_column(ForeignKey("app_users.id"), index=True)

    waba_id: Mapped[str | None] = mapped_column(String(128))
    phone_number_id: Mapped[str | None] = mapped_column(String(128))
    whatsapp_phone_number: Mapped[str | None] = mapped_column(String(64))

    usage_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    usage_limit: Mapped[int | None] = mapped_column(Integer)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    created_by_actor_id: Mapped[str | None] = mapped_column(String(128))
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class AIAgent(Base, TimestampMixin):
    """AI 作为一等主体。AI Agent 是独立主体，但可归属某个 staff 管理。

    不允许物理删除曾产生链接、客户绑定、消息或 job 的 AI Agent；
    删除 = status 改成 archived/deleted。
    """

    __tablename__ = "ai_agents"
    __table_args__ = (
        Index("ix_ai_agents_account_site", "account_id", "site_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False, index=True)
    agency_id: Mapped[str | None] = mapped_column(ForeignKey("agencies.id"), index=True)
    site_id: Mapped[str | None] = mapped_column(ForeignKey("h5_sites.id"), index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    # active / disabled / suspended / archived / deleted

    provider_name: Mapped[str] = mapped_column(String(64), nullable=False, default="openai")
    model_name: Mapped[str] = mapped_column(String(128), nullable=False, default="gpt-4o-mini")
    prompt_version: Mapped[str | None] = mapped_column(String(64))
    system_prompt: Mapped[str | None] = mapped_column(Text)

    waba_id: Mapped[str | None] = mapped_column(String(128))
    phone_number_id: Mapped[str | None] = mapped_column(String(128))

    owning_staff_user_id: Mapped[str | None] = mapped_column(String(128), index=True)
    owning_agency_member_id: Mapped[str | None] = mapped_column(String(128))
    fallback_staff_user_id: Mapped[str | None] = mapped_column(String(128), index=True)
    fallback_agency_member_id: Mapped[str | None] = mapped_column(String(128))
    fallback_ai_agent_id: Mapped[str | None] = mapped_column(ForeignKey("ai_agents.id"))

    default_entry_link_id: Mapped[str | None] = mapped_column(ForeignKey("entry_links.id"))
    auto_reply_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    proactive_send_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    health_status: Mapped[str] = mapped_column(String(32), nullable=False, default="healthy")
    # healthy / degraded / unavailable / disabled / suspended
    last_health_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    entry_links: Mapped[list["EntryLink"]] = relationship(
        foreign_keys="EntryLink.target_ai_agent_id",
        back_populates="ai_agent",
    )
    default_entry_link: Mapped["EntryLink | None"] = relationship(
        foreign_keys="AIAgent.default_entry_link_id",
        post_update=True,
    )


class MemberOwnerAssignment(Base, TimestampMixin):
    """会员人力归属历史。同一 account_id + user_id 只能有一个 is_current=true。"""

    __tablename__ = "member_owner_assignments"
    __table_args__ = (
        Index("ix_member_owner_assignments_current", "account_id", "user_id", "is_current"),
        Index("ix_member_owner_assignments_staff", "owner_staff_user_id", "is_current"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False, index=True)
    agency_id: Mapped[str | None] = mapped_column(ForeignKey("agencies.id"), index=True)
    site_id: Mapped[str | None] = mapped_column(ForeignKey("h5_sites.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), nullable=False, index=True)
    member_profile_id: Mapped[str] = mapped_column(ForeignKey("member_profiles.id"), nullable=False, index=True)
    owner_staff_user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    owner_agency_member_id: Mapped[str | None] = mapped_column(String(128))
    source_type: Mapped[str] = mapped_column(String(48), nullable=False)
    # staff_entry_link / ai_entry_link_fallback_staff / member_invite_inherited /
    # manual_transfer / migration / auto_reassign
    source_entry_link_id: Mapped[str | None] = mapped_column(ForeignKey("entry_links.id"))
    source_invite_code: Mapped[str | None] = mapped_column(String(64))
    source_referrer_user_id: Mapped[str | None] = mapped_column(ForeignKey("app_users.id"))
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, default=utc_now)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    changed_by_actor_id: Mapped[str | None] = mapped_column(String(128))
    transfer_batch_id: Mapped[str | None] = mapped_column(ForeignKey("member_owner_transfer_batches.id"))
    reason: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class MemberAIAssignment(Base, TimestampMixin):
    """会员 AI 归属历史。同一 account_id + user_id 只能有一个 is_current=true。"""

    __tablename__ = "member_ai_assignments"
    __table_args__ = (
        Index("ix_member_ai_assignments_current", "account_id", "user_id", "is_current"),
        Index("ix_member_ai_assignments_agent", "ai_agent_id", "is_current"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False, index=True)
    agency_id: Mapped[str | None] = mapped_column(ForeignKey("agencies.id"), index=True)
    site_id: Mapped[str | None] = mapped_column(ForeignKey("h5_sites.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), nullable=False, index=True)
    member_profile_id: Mapped[str] = mapped_column(ForeignKey("member_profiles.id"), nullable=False, index=True)
    ai_agent_id: Mapped[str] = mapped_column(ForeignKey("ai_agents.id"), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(48), nullable=False)
    # ai_entry_link / staff_link_default_ai / member_invite_inherited_ai /
    # manual_transfer / auto_failover_reassign / migration / waba_inbound
    source_entry_link_id: Mapped[str | None] = mapped_column(ForeignKey("entry_links.id"))
    source_invite_code: Mapped[str | None] = mapped_column(String(64))
    source_referrer_user_id: Mapped[str | None] = mapped_column(ForeignKey("app_users.id"))
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, default=utc_now)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    changed_by_actor_id: Mapped[str | None] = mapped_column(String(128))
    transfer_batch_id: Mapped[str | None] = mapped_column(ForeignKey("member_ai_transfer_batches.id"))
    reason: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class ConversationAIAssignment(Base, TimestampMixin):
    """会话实际 AI 接待归属。记录具体 WhatsApp 会话当前和历史由哪个 AI 实际接待。"""

    __tablename__ = "conversation_ai_assignments"
    __table_args__ = (
        Index("ix_conversation_ai_assignments_current", "account_id", "conversation_id", "is_current"),
        Index("ix_conversation_ai_assignments_agent", "actual_ai_agent_id", "is_current"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False, index=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), nullable=False, index=True)
    waba_id: Mapped[str | None] = mapped_column(String(128))
    phone_number_id: Mapped[str | None] = mapped_column(String(128))
    customer_wa_id: Mapped[str | None] = mapped_column(String(128))
    user_id: Mapped[str | None] = mapped_column(ForeignKey("app_users.id"), index=True)
    member_profile_id: Mapped[str | None] = mapped_column(ForeignKey("member_profiles.id"), index=True)
    bound_ai_agent_id: Mapped[str | None] = mapped_column(ForeignKey("ai_agents.id"))
    # 客户原本 sticky 绑定的 AI
    actual_ai_agent_id: Mapped[str] = mapped_column(ForeignKey("ai_agents.id"), nullable=False)
    # 本次实际接待的 AI，可能是兜底 AI
    source_type: Mapped[str] = mapped_column(String(48), nullable=False)
    # ai_link / default_phone_ai / member_current_ai / manual_switch /
    # temporary_failover / auto_reassign / rule_router
    source_entry_link_id: Mapped[str | None] = mapped_column(ForeignKey("entry_links.id"))
    source_invite_code: Mapped[str | None] = mapped_column(String(64))
    failover_from_ai_agent_id: Mapped[str | None] = mapped_column(ForeignKey("ai_agents.id"))
    failover_reason: Mapped[str | None] = mapped_column(String(128))
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, default=utc_now)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    changed_by_actor_id: Mapped[str | None] = mapped_column(String(128))
    reason: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class MemberOwnerTransferBatch(Base, TimestampMixin):
    __tablename__ = "member_owner_transfer_batches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False, index=True)
    agency_id: Mapped[str | None] = mapped_column(ForeignKey("agencies.id"))
    site_id: Mapped[str | None] = mapped_column(ForeignKey("h5_sites.id"))
    from_staff_user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    to_staff_user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="completed")
    total_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    dry_run: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reason: Mapped[str | None] = mapped_column(Text)
    changed_by_actor_id: Mapped[str | None] = mapped_column(String(128))
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class MemberOwnerTransferItem(Base, TimestampMixin):
    __tablename__ = "member_owner_transfer_items"
    __table_args__ = (
        Index("ix_member_owner_transfer_items_batch", "batch_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    batch_id: Mapped[str] = mapped_column(ForeignKey("member_owner_transfer_batches.id"), nullable=False)
    member_profile_id: Mapped[str] = mapped_column(ForeignKey("member_profiles.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), nullable=False, index=True)
    from_staff_user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    to_staff_user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="transferred")
    error_message: Mapped[str | None] = mapped_column(Text)


class MemberAITransferBatch(Base, TimestampMixin):
    __tablename__ = "member_ai_transfer_batches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False, index=True)
    agency_id: Mapped[str | None] = mapped_column(ForeignKey("agencies.id"))
    site_id: Mapped[str | None] = mapped_column(ForeignKey("h5_sites.id"))
    from_ai_agent_id: Mapped[str] = mapped_column(ForeignKey("ai_agents.id"), nullable=False)
    to_ai_agent_id: Mapped[str] = mapped_column(ForeignKey("ai_agents.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="completed")
    total_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    include_open_conversations: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    dry_run: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reason: Mapped[str | None] = mapped_column(Text)
    changed_by_actor_id: Mapped[str | None] = mapped_column(String(128))
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class MemberAITransferItem(Base, TimestampMixin):
    __tablename__ = "member_ai_transfer_items"
    __table_args__ = (
        Index("ix_member_ai_transfer_items_batch", "batch_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    batch_id: Mapped[str] = mapped_column(ForeignKey("member_ai_transfer_batches.id"), nullable=False)
    member_profile_id: Mapped[str] = mapped_column(ForeignKey("member_profiles.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), nullable=False, index=True)
    from_ai_agent_id: Mapped[str] = mapped_column(ForeignKey("ai_agents.id"), nullable=False)
    to_ai_agent_id: Mapped[str] = mapped_column(ForeignKey("ai_agents.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="transferred")
    error_message: Mapped[str | None] = mapped_column(Text)


class AIFailoverEvent(Base, TimestampMixin):
    __tablename__ = "ai_failover_events"
    __table_args__ = (
        Index("ix_ai_failover_events_agent", "from_ai_agent_id", "to_ai_agent_id", "event_type"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False, index=True)
    agency_id: Mapped[str | None] = mapped_column(ForeignKey("agencies.id"))
    site_id: Mapped[str | None] = mapped_column(ForeignKey("h5_sites.id"))
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    # temporary_failover / auto_reassign / permanent_migration / waba_unavailable
    from_ai_agent_id: Mapped[str | None] = mapped_column(ForeignKey("ai_agents.id"))
    to_ai_agent_id: Mapped[str | None] = mapped_column(ForeignKey("ai_agents.id"))
    conversation_id: Mapped[str | None] = mapped_column(ForeignKey("conversations.id"), index=True)
    member_profile_id: Mapped[str | None] = mapped_column(ForeignKey("member_profiles.id"), index=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("app_users.id"), index=True)
    reason: Mapped[str | None] = mapped_column(String(255))
    affected_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    changed_by_actor_id: Mapped[str | None] = mapped_column(String(128))
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class OwnershipAuditEvent(Base, TimestampMixin):
    __tablename__ = "ownership_audit_events"
    __table_args__ = (
        Index("ix_ownership_audit_events_target", "target_type", "target_id"),
        Index("ix_ownership_audit_events_action", "action", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str | None] = mapped_column(ForeignKey("accounts.account_id"), index=True)
    agency_id: Mapped[str | None] = mapped_column(ForeignKey("agencies.id"))
    site_id: Mapped[str | None] = mapped_column(ForeignKey("h5_sites.id"))
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    # entry_link_created / entry_link_revoked / entry_link_rotated /
    # ai_agent_created / ai_agent_disabled / ai_agent_archived /
    # site_registration_policy_changed / site_default_ai_changed /
    # site_default_staff_link_changed / member_owner_transferred /
    # member_ai_transferred / ai_temporary_failover / ai_permanent_migration /
    # waba_unavailable_migration / transfer_unauthorized_attempt
    target_type: Mapped[str] = mapped_column(String(48), nullable=False)
    target_id: Mapped[str] = mapped_column(String(128), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(32), nullable=False, default="system")
    actor_id: Mapped[str | None] = mapped_column(String(128))
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, default=utc_now)


class AIOutboundJob(Base, TimestampMixin):
    """AI 主动发送任务：后续主动触达、任务提醒、复访、营销、系统事件触发。

    客服窗口外必须使用已审核 template，并校验用户 opt-in；不满足政策时
    status=skipped_policy，不能静默发送。
    """

    __tablename__ = "ai_outbound_jobs"
    __table_args__ = (
        Index("ix_ai_outbound_jobs_status", "status", "scheduled_at"),
        Index("ix_ai_outbound_jobs_agent", "ai_agent_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False, index=True)
    agency_id: Mapped[str | None] = mapped_column(ForeignKey("agencies.id"))
    site_id: Mapped[str | None] = mapped_column(ForeignKey("h5_sites.id"))
    ai_agent_id: Mapped[str] = mapped_column(ForeignKey("ai_agents.id"), nullable=False, index=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("app_users.id"), index=True)
    member_profile_id: Mapped[str | None] = mapped_column(ForeignKey("member_profiles.id"), index=True)
    conversation_id: Mapped[str | None] = mapped_column(ForeignKey("conversations.id"), index=True)
    waba_id: Mapped[str | None] = mapped_column(String(128))
    phone_number_id: Mapped[str | None] = mapped_column(String(128))
    recipient_wa_id: Mapped[str | None] = mapped_column(String(128))
    trigger_type: Mapped[str] = mapped_column(String(48), nullable=False)
    message_policy: Mapped[str] = mapped_column(String(32), nullable=False, default="service_window")
    # service_window / template_required / template
    template_id: Mapped[str | None] = mapped_column(ForeignKey("message_templates.id"))
    template_name: Mapped[str | None] = mapped_column(String(255))
    template_language: Mapped[str | None] = mapped_column(String(32))
    generated_text: Mapped[str | None] = mapped_column(Text)
    send_payload_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    source_entry_link_id: Mapped[str | None] = mapped_column(ForeignKey("entry_links.id"))
    # 归属快照（创建时写入，划转不更新）
    owner_agency_id_snapshot: Mapped[str | None] = mapped_column(String(128))
    owner_staff_user_id_snapshot: Mapped[str | None] = mapped_column(String(128))
    owner_agency_member_id_snapshot: Mapped[str | None] = mapped_column(String(128))
    owner_assignment_id_snapshot: Mapped[str | None] = mapped_column(String(36))
    ai_assignment_id_snapshot: Mapped[str | None] = mapped_column(String(36))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    # pending / scheduled / sent / failed / cancelled / skipped_policy
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    provider_message_id: Mapped[str | None] = mapped_column(String(255))
    error_message: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)


# 关系回填：EntryLink.ai_agent
EntryLink.ai_agent = relationship(
    "AIAgent",
    foreign_keys=[EntryLink.target_ai_agent_id],
    back_populates="entry_links",
)
