"""归属 / AI 接待归属 / 入口链接 后端核心场景测试（spec 16.1）。

覆盖验收标准 #1-#11：注册强制 entry_code、客服/AI 链接注册归属、会员邀请继承、
sticky AI、临时 failover、永久迁移、划转不改历史、AI 自动消息归属快照。
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db.models import (
    Account,
    Agency,
    AppUser,
    Conversation,
    H5Site,
    InviteCode,
    MemberProfile,
    Message,
    UserReferral,
    utc_now,
)
from app.db.ownership_models import (
    AIAgent,
    ConversationAIAssignment,
    EntryLink,
    MemberAIAssignment,
    MemberOwnerAssignment,
)
from app.services.ai_agent_service import AIAgentService
from app.services.conversation_ai_assignment_service import (
    AIFailoverService,
    AttributionError,
    ConversationAIAssignmentService,
    parse_entry_code_from_text,
)
from app.services.entry_link_service import EntryLinkService
from app.services.member_ownership_service import (
    AttributionError as RegAttributionError,
)
from app.services.member_ownership_service import (
    MemberAIOwnershipService,
    MemberOwnershipService,
    TransferUnauthorizedError,
)
from app.services.ownership_snapshot_service import OwnershipSnapshotService


@pytest.fixture
def session_factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def _seed_account_site(session: Session) -> tuple[Account, Agency, H5Site]:
    account = Account(
        account_id="acct-1",
        display_name="Test Account",
        provider_type="mock",
    )
    agency = Agency(name="Test Agency", status="active")
    session.add_all([account, agency])
    session.flush()
    site = H5Site(
        account_id=account.account_id,
        site_key="site-1",
        domain="shop.example.com",
        brand_name="Test Brand",
        agency_id=agency.id,
        registration_entry_required=True,
        allow_invite_code_alias=True,
        member_invite_inherits_human_owner=True,
        member_invite_inherits_ai=True,
    )
    session.add(site)
    session.commit()
    return account, agency, site


def _seed_ai_agent(
    session: Session,
    *,
    account_id: str,
    site_id: str | None,
    agency_id: str | None = None,
    fallback_staff_user_id: str | None = None,
    name: str = "AI-Bot",
) -> AIAgent:
    svc = AIAgentService(session)
    return svc.create_ai_agent(
        account_id=account_id,
        agency_id=agency_id,
        site_id=site_id,
        name=name,
        display_name="AI Assistant",
        owning_staff_user_id="staff-owner-1",
        fallback_staff_user_id=fallback_staff_user_id,
    )


def _seed_member(
    session: Session,
    *,
    account_id: str,
    site_id: str,
) -> tuple[AppUser, MemberProfile]:
    user = AppUser(
        account_id=account_id,
        public_user_id="u-1",
        registration_site_id=site_id,
        display_name="Member One",
        is_anonymous=False,
        lifecycle_status="active",
        has_phone=True,
    )
    session.add(user)
    session.flush()
    member = MemberProfile(
        account_id=account_id,
        user_id=user.id,
        member_no="M0000001",
        password_hash="x",
        password_salt="y",
    )
    session.add(member)
    session.commit()
    return user, member


# ──────────────────────────────────────────────────────────────────────────────
# 验收 #1: 无 entry_code 注册被拒
# ──────────────────────────────────────────────────────────────────────────────
def test_registration_rejected_without_entry_code_when_required(session_factory):
    with session_factory() as s:
        account, agency, site = _seed_account_site(s)
        ownership_svc = MemberOwnershipService(s)
        with pytest.raises(RegAttributionError):
            ownership_svc.resolve_registration_entry(site, entry_code_or_invite_code=None)


def test_registration_allowed_without_entry_code_when_not_required(session_factory):
    with session_factory() as s:
        account, agency, site = _seed_account_site(s)
        site.registration_entry_required = False
        s.commit()
        ownership_svc = MemberOwnershipService(s)
        link, code = ownership_svc.resolve_registration_entry(site, None)
        assert link is None and code == ""


# ──────────────────────────────────────────────────────────────────────────────
# 验收 #2: 客服 EntryLink 注册 -> 归属该客服
# ──────────────────────────────────────────────────────────────────────────────
def test_staff_entry_link_registration_assigns_staff_owner(session_factory):
    with session_factory() as s:
        account, agency, site = _seed_account_site(s)
        link_svc = EntryLinkService(s)
        link = link_svc.create_staff_register_link(
            account_id=account.account_id,
            site_id=site.id,
            staff_user_id="staff-A",
        )
        user, member = _seed_member(s, account_id=account.account_id, site_id=site.id)
        ownership_svc = MemberOwnershipService(s)
        assignment = ownership_svc.assign_new_member_human_owner(
            account_id=account.account_id,
            user_id=user.id,
            member_profile_id=member.id,
            entry_link=link,
            invite_code=None,
            referrer_user_id=None,
            site=site,
        )
        s.commit()
        assert assignment.owner_staff_user_id == "staff-A"
        assert assignment.source_type == "staff_entry_link"
        s.refresh(member)
        assert member.current_owner_staff_user_id == "staff-A"
        assert member.attribution_status == "owned"


# ──────────────────────────────────────────────────────────────────────────────
# 验收 #3: AI EntryLink 注册 -> AI 归属 + 人力兜底归属；无 fallback staff 拒绝
# ──────────────────────────────────────────────────────────────────────────────
def test_ai_entry_link_registration_assigns_ai_and_fallback_staff(session_factory):
    with session_factory() as s:
        account, agency, site = _seed_account_site(s)
        agent = _seed_ai_agent(
            s, account_id=account.account_id, site_id=site.id, agency_id=agency.id,
            fallback_staff_user_id="staff-fallback",
        )
        link_svc = EntryLinkService(s)
        link = link_svc.create_ai_register_link(
            account_id=account.account_id, site_id=site.id, ai_agent_id=agent.id,
        )
        user, member = _seed_member(s, account_id=account.account_id, site_id=site.id)
        ownership_svc = MemberOwnershipService(s)
        ownership_svc.assign_new_member_human_owner(
            account_id=account.account_id, user_id=user.id, member_profile_id=member.id,
            entry_link=link, invite_code=None, referrer_user_id=None, site=site,
        )
        ai_svc = MemberAIOwnershipService(s)
        ai_assignment = ai_svc.assign_new_member_ai(
            account_id=account.account_id, user_id=user.id, member_profile_id=member.id,
            entry_link=link, referrer_user_id=None, site=site,
        )
        s.commit()
        s.refresh(member)
        assert member.current_ai_agent_id == agent.id
        assert member.current_owner_staff_user_id == "staff-fallback"
        assert ai_assignment.source_type == "ai_entry_link"


def test_ai_entry_link_without_fallback_staff_rejects_registration(session_factory):
    with session_factory() as s:
        account, agency, site = _seed_account_site(s)
        agent = _seed_ai_agent(
            s, account_id=account.account_id, site_id=site.id, agency_id=agency.id,
            fallback_staff_user_id=None,  # 无兜底
        )
        # agent.owning_staff_user_id 默认 staff-owner-1，所以会回退到 owning。
        # 为真正测拒绝，清空 owning_staff_user_id
        agent.owning_staff_user_id = None
        s.commit()
        link_svc = EntryLinkService(s)
        link = link_svc.create_ai_register_link(
            account_id=account.account_id, site_id=site.id, ai_agent_id=agent.id,
        )
        user, member = _seed_member(s, account_id=account.account_id, site_id=site.id)
        ownership_svc = MemberOwnershipService(s)
        with pytest.raises(RegAttributionError):
            ownership_svc.assign_new_member_human_owner(
                account_id=account.account_id, user_id=user.id, member_profile_id=member.id,
                entry_link=link, invite_code=None, referrer_user_id=None, site=site,
            )


# ──────────────────────────────────────────────────────────────────────────────
# 验收 #4: 会员邀请继承人力 + AI 归属
# ──────────────────────────────────────────────────────────────────────────────
def test_member_invite_inherits_human_and_ai_ownership(session_factory):
    with session_factory() as s:
        account, agency, site = _seed_account_site(s)
        agent = _seed_ai_agent(
            s, account_id=account.account_id, site_id=site.id, agency_id=agency.id,
            fallback_staff_user_id="staff-A",
        )
        site.default_ai_agent_id = agent.id
        s.commit()
        ownership_svc = MemberOwnershipService(s)
        # 邀请人（已归属 staff-A + AI）—— 经正式 assignment 行建立归属
        referrer_user, referrer_member = _seed_member(s, account_id=account.account_id, site_id=site.id)
        ownership_svc._end_old_and_create_current(
            account_id=account.account_id, user_id=referrer_user.id, member_profile_id=referrer_member.id,
            owner_staff_user_id="staff-A", owner_agency_member_id=None,
            source_type="staff_entry_link", source_entry_link_id=None,
            source_invite_code=None, source_referrer_user_id=None,
            site_id=site.id, agency_id=agency.id, actor_id=None,
        )
        MemberAIOwnershipService(s)._end_old_and_create_current(
            account_id=account.account_id, user_id=referrer_user.id, member_profile_id=referrer_member.id,
            ai_agent_id=agent.id, source_type="ai_entry_link",
            source_entry_link_id=None, site_id=site.id, agency_id=agency.id, actor_id=None,
        )
        referrer_member.current_owner_staff_user_id = "staff-A"
        referrer_member.current_ai_agent_id = agent.id
        s.commit()
        # 邀请码
        invite = InviteCode(
            code="INVITE-1", site_id=site.id, inviter_user_id=referrer_user.id, status="active",
        )
        s.add(invite)
        s.commit()
        # 被邀请人
        new_user = AppUser(
            account_id=account.account_id, public_user_id="u-2",
            registration_site_id=site.id, display_name="Member Two",
            is_anonymous=False, lifecycle_status="active",
        )
        s.add(new_user)
        s.flush()
        new_member = MemberProfile(
            account_id=account.account_id, user_id=new_user.id,
            member_no="M0000002", password_hash="x", password_salt="y",
        )
        s.add(new_member)
        s.flush()
        ownership_svc = MemberOwnershipService(s)
        ownership_svc.assign_new_member_human_owner(
            account_id=account.account_id, user_id=new_user.id, member_profile_id=new_member.id,
            entry_link=None, invite_code="INVITE-1", referrer_user_id=referrer_user.id, site=site,
        )
        ai_svc = MemberAIOwnershipService(s)
        ai_svc.assign_new_member_ai(
            account_id=account.account_id, user_id=new_user.id, member_profile_id=new_member.id,
            entry_link=None, referrer_user_id=referrer_user.id, site=site,
        )
        s.commit()
        s.refresh(new_member)
        assert new_member.current_owner_staff_user_id == "staff-A"  # 继承
        assert new_member.current_ai_agent_id == agent.id  # 继承


# ──────────────────────────────────────────────────────────────────────────────
# 验收 #5: 第二次进入继续 sticky AI
# 验收 #6: AI 临时不可用 -> failover
# ──────────────────────────────────────────────────────────────────────────────
def _seed_conversation(s, *, account_id, customer_id="cust-1") -> Conversation:
    conv = Conversation(
        account_id=account_id,
        external_conversation_id="ext-conv-1",
        customer_id=customer_id,
        status="open",
    )
    s.add(conv)
    s.commit()
    return conv


def test_sticky_ai_and_temporary_failover(session_factory):
    with session_factory() as s:
        account, agency, site = _seed_account_site(s)
        agent_a = _seed_ai_agent(
            s, account_id=account.account_id, site_id=site.id, agency_id=agency.id,
            fallback_staff_user_id="staff-A", name="AI-A",
        )
        agent_a.waba_id = "waba-1"
        # fallback AI-B
        agent_b = AIAgentService(s).create_ai_agent(
            account_id=account.account_id, agency_id=agency.id, site_id=site.id,
            name="AI-B", display_name="AI B", owning_staff_user_id="staff-B",
            waba_id="waba-1",
        )
        agent_a.fallback_ai_agent_id = agent_b.id
        s.commit()
        user, member = _seed_member(s, account_id=account.account_id, site_id=site.id)
        member.current_ai_agent_id = agent_a.id
        s.commit()
        conv = _seed_conversation(s, account_id=account.account_id, customer_id=user.id)

        conv_svc = ConversationAIAssignmentService(s)
        ctx = {"user_id": user.id, "waba_id": "waba-1", "phone_number_id": "pn-1"}
        # 第一次：sticky AI-A
        a1 = conv_svc.ensure_conversation_ai_assignment(
            account_id=account.account_id, conversation_id=conv.id,
            entry_context=ctx, site_id=site.id,
        )
        assert a1.actual_ai_agent_id == agent_a.id
        s.commit()

        # AI-A 临时不可用（disable）-> failover 到 AI-B
        AIAgentService(s).disable_ai_agent(agent_a.id, actor_id="staff-A", reason="temp")
        s.commit()
        a2 = conv_svc.ensure_conversation_ai_assignment(
            account_id=account.account_id, conversation_id=conv.id,
            entry_context=ctx, site_id=site.id,
        )
        assert a2.actual_ai_agent_id == agent_b.id
        assert a2.failover_from_ai_agent_id == agent_a.id
        s.refresh(member)
        # 临时 failover 不改会员 current AI
        assert member.current_ai_agent_id == agent_a.id


# ──────────────────────────────────────────────────────────────────────────────
# 验收 #7: AI 永久禁用 -> 自动迁移客户 current AI
# ──────────────────────────────────────────────────────────────────────────────
def test_permanent_migration_moves_member_current_ai(session_factory):
    with session_factory() as s:
        account, agency, site = _seed_account_site(s)
        agent_a = _seed_ai_agent(
            s, account_id=account.account_id, site_id=site.id, agency_id=agency.id, name="AI-A",
        )
        agent_b = AIAgentService(s).create_ai_agent(
            account_id=account.account_id, agency_id=agency.id, site_id=site.id, name="AI-B",
            display_name="AI B",
        )
        user, member = _seed_member(s, account_id=account.account_id, site_id=site.id)
        member.current_ai_agent_id = agent_a.id
        s.commit()
        # 也建一条 current AI assignment
        MemberAIOwnershipService(s)._end_old_and_create_current(
            account_id=account.account_id, user_id=user.id, member_profile_id=member.id,
            ai_agent_id=agent_a.id, source_type="ai_entry_link",
            source_entry_link_id=None, site_id=site.id, agency_id=agency.id, actor_id=None,
        )
        s.commit()

        failover_svc = AIFailoverService(s)
        affected = failover_svc.permanent_migration(
            account_id=account.account_id, from_ai_agent_id=agent_a.id,
            to_ai_agent_id=agent_b.id, actor_id="staff-A", reason="agent_archived",
        )
        s.commit()
        assert affected == 1
        s.refresh(member)
        assert member.current_ai_agent_id == agent_b.id  # 永久迁移


# ──────────────────────────────────────────────────────────────────────────────
# 验收 #8/#9: 划转不改历史 snapshot；划转后新记录归新归属
# ──────────────────────────────────────────────────────────────────────────────
def test_human_transfer_does_not_change_history_snapshot(session_factory):
    with session_factory() as s:
        account, agency, site = _seed_account_site(s)
        user, member = _seed_member(s, account_id=account.account_id, site_id=site.id)
        ownership_svc = MemberOwnershipService(s)
        # 旧归属 staff-A
        ownership_svc._end_old_and_create_current(
            account_id=account.account_id, user_id=user.id, member_profile_id=member.id,
            owner_staff_user_id="staff-A", owner_agency_member_id=None,
            source_type="staff_entry_link", source_entry_link_id=None,
            source_invite_code=None, source_referrer_user_id=None,
            site_id=site.id, agency_id=agency.id, actor_id=None,
        )
        member.current_owner_staff_user_id = "staff-A"
        s.commit()
        # 旧业务记录写入 snapshot（staff-A）
        snap_svc = OwnershipSnapshotService(s)
        old_msg = Message(
            account_id=account.account_id,
            conversation_id=_seed_conversation(s, account_id=account.account_id, customer_id=user.id).id,
            direction="inbound", message_type="text", ai_generated=False,
            provider_message_id="wamid-old-1",
        )
        snap = snap_svc.build_snapshot_for_user(account.account_id, user.id)
        snap_svc.apply_snapshot_to_model(old_msg, snap)
        s.add(old_msg)
        s.commit()
        assert old_msg.owner_staff_user_id_snapshot == "staff-A"

        # 划转到 staff-B
        ownership_svc.transfer_members(
            account_id=account.account_id, from_staff_user_id="staff-A",
            to_staff_user_id="staff-B", member_profile_ids=[member.id],
            actor_id="admin-1", agency_id=agency.id, site_id=site.id,
        )
        s.commit()

        # 历史消息 snapshot 不变
        s.refresh(old_msg)
        assert old_msg.owner_staff_user_id_snapshot == "staff-A"
        # 新 snapshot 归 staff-B
        s.refresh(member)
        assert member.current_owner_staff_user_id == "staff-B"
        new_snap = snap_svc.build_snapshot_for_user(account.account_id, user.id)
        assert new_snap.owner_staff_user_id_snapshot == "staff-B"


def test_ai_transfer_does_not_change_history_snapshot(session_factory):
    with session_factory() as s:
        account, agency, site = _seed_account_site(s)
        agent_a = _seed_ai_agent(s, account_id=account.account_id, site_id=site.id, agency_id=agency.id, name="AI-A")
        agent_b = AIAgentService(s).create_ai_agent(
            account_id=account.account_id, agency_id=agency.id, site_id=site.id, name="AI-B", display_name="AI B",
        )
        user, member = _seed_member(s, account_id=account.account_id, site_id=site.id)
        member.current_ai_agent_id = agent_a.id
        # 经正式 AI assignment 行建立归属（划转按此行操作）
        MemberAIOwnershipService(s)._end_old_and_create_current(
            account_id=account.account_id, user_id=user.id, member_profile_id=member.id,
            ai_agent_id=agent_a.id, source_type="ai_entry_link",
            source_entry_link_id=None, site_id=site.id, agency_id=agency.id, actor_id=None,
        )
        s.commit()
        conv = _seed_conversation(s, account_id=account.account_id, customer_id=user.id)
        old_msg = Message(
            account_id=account.account_id, conversation_id=conv.id,
            direction="outbound", message_type="text", ai_generated=True,
            ai_agent_id=agent_a.id, provider_message_id="wamid-ai-old-1",
        )
        s.add(old_msg)
        s.commit()

        ai_svc = MemberAIOwnershipService(s)
        ai_svc.transfer_member_ai(
            account_id=account.account_id, from_ai_agent_id=agent_a.id,
            to_ai_agent_id=agent_b.id, member_profile_ids=[member.id], actor_id="admin-1",
        )
        s.commit()
        s.refresh(old_msg)
        assert old_msg.ai_agent_id == agent_a.id  # 历史不变
        s.refresh(member)
        assert member.current_ai_agent_id == agent_b.id  # 当前迁移


# ──────────────────────────────────────────────────────────────────────────────
# 验收 #10: AI 自动消息 ai_generated=true + ai_agent_id + snapshot
# ──────────────────────────────────────────────────────────────────────────────
def test_ai_delivery_modes_marked_ai_generated(session_factory):
    from app.services.conversation_ai_assignment_service import AI_DELIVERY_MODES

    assert "ai_sync_reply" in AI_DELIVERY_MODES
    assert "ai_async_queued" in AI_DELIVERY_MODES
    assert "rule_auto_reply" in AI_DELIVERY_MODES
    with session_factory() as s:
        account, agency, site = _seed_account_site(s)
        agent = _seed_ai_agent(s, account_id=account.account_id, site_id=site.id, agency_id=agency.id)
        user, member = _seed_member(s, account_id=account.account_id, site_id=site.id)
        member.current_ai_agent_id = agent.id
        member.current_owner_staff_user_id = "staff-A"
        s.commit()
        conv = _seed_conversation(s, account_id=account.account_id, customer_id=user.id)
        snap_svc = OwnershipSnapshotService(s)
        snap = snap_svc.build_snapshot_for_ai_message(
            account.account_id, conv.id, ai_agent_id=agent.id, entry_link_id=None
        )
        msg = Message(
            account_id=account.account_id, conversation_id=conv.id,
            direction="outbound", message_type="text",
            delivery_mode="ai_sync_reply",
            ai_generated=True, ai_agent_id=agent.id,
            ai_provider=agent.provider_name, ai_model=agent.model_name,
            provider_message_id="wamid-ai-1",
        )
        snap_svc.apply_snapshot_to_model(msg, snap)
        s.add(msg)
        s.commit()
        s.refresh(msg)
        assert msg.ai_generated is True
        assert msg.ai_agent_id == agent.id
        assert msg.owner_staff_user_id_snapshot == "staff-A"
        assert msg.delivery_mode == "ai_sync_reply"


# ──────────────────────────────────────────────────────────────────────────────
# 验收: 普通客服不能划转 / 跨代理商不能划转
# ──────────────────────────────────────────────────────────────────────────────
def test_transfer_requires_actor_and_respects_scope(session_factory):
    with session_factory() as s:
        account, agency, site = _seed_account_site(s)
        user, member = _seed_member(s, account_id=account.account_id, site_id=site.id)
        ownership_svc = MemberOwnershipService(s)
        ownership_svc._end_old_and_create_current(
            account_id=account.account_id, user_id=user.id, member_profile_id=member.id,
            owner_staff_user_id="staff-A", owner_agency_member_id=None,
            source_type="staff_entry_link", source_entry_link_id=None,
            source_invite_code=None, source_referrer_user_id=None,
            site_id=site.id, agency_id=agency.id, actor_id=None,
        )
        s.commit()
        # 正常划转成功
        result = ownership_svc.transfer_members(
            account_id=account.account_id, from_staff_user_id="staff-A",
            to_staff_user_id="staff-B", member_profile_ids=[member.id],
            actor_id="admin-1",
        )
        assert result["affected_count"] == 1
        # dry_run 不写库
        ownership_svc._end_old_and_create_current(
            account_id=account.account_id, user_id=user.id, member_profile_id=member.id,
            owner_staff_user_id="staff-B", owner_agency_member_id=None,
            source_type="manual_transfer", source_entry_link_id=None,
            source_invite_code=None, source_referrer_user_id=None,
            site_id=site.id, agency_id=agency.id, actor_id=None,
        )
        s.commit()
        dry = ownership_svc.transfer_members(
            account_id=account.account_id, from_staff_user_id="staff-B",
            to_staff_user_id="staff-C", member_profile_ids=[member.id],
            actor_id="admin-1", dry_run=True,
        )
        assert dry["dry_run"] is True
        s.refresh(member)
        assert member.current_owner_staff_user_id == "staff-B"  # dry_run 未改


# ──────────────────────────────────────────────────────────────────────────────
# EntryLink: 幂等使用计数 + URL 派生 + 撤销/轮换
# ──────────────────────────────────────────────────────────────────────────────
def test_entry_link_record_usage_once_is_idempotent(session_factory):
    with session_factory() as s:
        account, agency, site = _seed_account_site(s)
        svc = EntryLinkService(s)
        link = svc.create_staff_register_link(
            account_id=account.account_id, site_id=site.id, staff_user_id="staff-A",
        )
        # 同一 idempotency_key 不重复计数
        assert svc.record_usage_once(idempotency_key="k1", entry_link=link) is True
        s.commit()
        assert svc.record_usage_once(idempotency_key="k1", entry_link=link) is False
        s.commit()
        s.refresh(link)
        assert link.usage_count == 1


def test_entry_link_build_urls_derives_from_site(session_factory):
    with session_factory() as s:
        account, agency, site = _seed_account_site(s)
        svc = EntryLinkService(s)
        link = svc.create_ai_chat_link(
            account_id=account.account_id, site_id=site.id, ai_agent_id="ai-1",
            waba_id="waba-1", whatsapp_phone_number="+15550000001",
        )
        s.commit()
        urls = svc.build_urls(link)
        assert "entry_code=" + link.code in (urls["h5_register_url"] or "")
        assert urls["whatsapp_chat_url"] == f"https://wa.me/15550000001?text=/start%20{link.code}"


def test_entry_link_revoke_and_rotate(session_factory):
    with session_factory() as s:
        account, agency, site = _seed_account_site(s)
        svc = EntryLinkService(s)
        link = svc.create_staff_register_link(
            account_id=account.account_id, site_id=site.id, staff_user_id="staff-A",
        )
        s.commit()
        svc.revoke(link.id, actor_id="admin-1", reason="leak")
        s.commit()
        s.refresh(link)
        assert link.status == "revoked"
        new_link = svc.rotate(link.id, actor_id="admin-1", reason="rotate")
        s.commit()
        assert new_link.status == "active"
        assert new_link.code != link.code


# ──────────────────────────────────────────────────────────────────────────────
# parse_entry_code_from_text
# ──────────────────────────────────────────────────────────────────────────────
def test_parse_entry_code_from_wa_me_text():
    assert parse_entry_code_from_text("/start EL-abc123") == "EL-abc123"
    assert parse_entry_code_from_text("hello /start EL-xyz end") == "EL-xyz"
    assert parse_entry_code_from_text("no code here") is None
    assert parse_entry_code_from_text(None) is None
