"""P0/P1 集成修复回归测试（spec 第 16 节）。

覆盖：
- Chat/WABA 出站消息写入 AI / owner / entry link 快照（spec 5.9 / 8.4）。
- RuntimeStateStore.record_outbound_message 接受新快照参数并向下兼容。
- AIOutboundJobService 创建前政策校验：service window / template / opt-in。
- OwnershipReportService 报表聚合。
"""

from __future__ import annotations

from datetime import timedelta
import os
import sys
from typing import Any

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

# 让 conftest / 项目 root 可被 import
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.core.settings import get_settings  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.models import (  # noqa: E402
    Account,
    AppUser,
    Conversation,
    H5Site,
    MemberProfile,
    Message,
    MessageTemplate,
    utc_now,
)
from app.db.ownership_models import (  # noqa: E402
    AIAgent,
    AIOutboundJob,
    MemberOwnerAssignment,
)
from app.services.ai_outbound_job_service import AIOutboundJobService  # noqa: E402
from app.services.ownership_report_service import OwnershipReportService  # noqa: E402
from app.services.runtime_state import RuntimeStateStore  # noqa: E402


@pytest.fixture
def session() -> Any:
    get_settings.cache_clear()
    os.environ.setdefault("TEST_MODE", "true")
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    sess = factory()
    try:
        yield sess
    finally:
        sess.close()
        engine.dispose()


def _seed_basic(session: Session) -> tuple[Account, H5Site]:
    account = Account(
        account_id="acc-test",
        display_name="Test Account",
        provider_type="mock",
        is_active=True,
    )
    session.add(account)
    site = H5Site(
        account_id=account.account_id,
        site_key="test-site",
        domain="test.example.com",
        brand_name="Test Site",
        default_language="zh-CN",
        status="active",
    )
    session.add(site)
    session.flush()
    return account, site


def _seed_user_member(
    session: Session, *, account_id: str, phone: str = "13800000001", member_no: str = "00000001"
) -> tuple[AppUser, MemberProfile]:
    user = AppUser(
        account_id=account_id,
        public_user_id=f"u-{phone}",
        registration_site_id=None,
        display_name=f"User {phone}",
        has_phone=True,
        is_anonymous=False,
        lifecycle_status="active",
    )
    session.add(user)
    session.flush()
    member = MemberProfile(
        account_id=account_id,
        user_id=user.id,
        member_no=member_no,
        password_hash="x" * 64,
        password_salt="s" * 32,
        password_updated_at=utc_now(),
    )
    session.add(member)
    session.flush()
    return user, member


# ────────────────────── RuntimeStateStore.record_outbound_message 快照写入 ──────────────────────


@pytest.mark.asyncio
async def test_record_outbound_message_writes_ai_snapshot_when_ai_generated(session: Session) -> None:
    account, site = _seed_basic(session)
    user, _ = _seed_user_member(session, account_id=account.account_id)

    conversation = Conversation(
        account_id=account.account_id,
        external_conversation_id="wa:pn-1:u-1",
        customer_id=user.public_user_id,
        status="open",
        current_ai_agent_id="ai-agent-1",
        current_ai_assignment_id="ai-asg-1",
        current_entry_link_id="entry-link-1",
        current_owner_staff_user_id_snapshot="staff-1",
        current_owner_agency_id_snapshot="agency-1",
        current_owner_assignment_id_snapshot="owner-asg-1",
    )
    session.add(conversation)
    session.commit()

    store = RuntimeStateStore(session)
    message = await store.record_outbound_message(
        account_id=account.account_id,
        conversation_id=conversation.external_conversation_id,
        recipient_id=user.public_user_id,
        text="hello",
        language_code="zh-CN",
        translated_text=None,
        translated_language_code=None,
        delivery_mode="ai_sync_reply",
        ai_generated=True,
        payload={"provider": "mock"},
        actor_type="ai_agent",
        actor_id="ai-agent-1",
        ai_agent_id="ai-agent-1",
        ai_assignment_id_snapshot="ai-asg-1",
        source_entry_link_id_snapshot="entry-link-1",
        owner_agency_id_snapshot="agency-1",
        owner_staff_user_id_snapshot="staff-1",
        owner_assignment_id_snapshot="owner-asg-1",
        ai_provider="openai",
        ai_model="gpt-4o-mini",
    )
    assert message.ai_generated is True
    assert message.actor_type == "ai_agent"
    assert message.ai_agent_id == "ai-agent-1"
    assert message.ai_assignment_id_snapshot == "ai-asg-1"
    assert message.source_entry_link_id_snapshot == "entry-link-1"
    assert message.owner_staff_user_id_snapshot == "staff-1"
    assert message.owner_agency_id_snapshot == "agency-1"
    assert message.owner_assignment_id_snapshot == "owner-asg-1"
    assert message.delivery_mode == "ai_sync_reply"
    assert message.ai_provider == "openai"
    assert message.ai_model == "gpt-4o-mini"


@pytest.mark.asyncio
async def test_record_outbound_message_backward_compatible(session: Session) -> None:
    """旧调用不传新字段时仍能成功，且 ai_generated=False 时不写 AI 字段。"""
    account, site = _seed_basic(session)
    user, _ = _seed_user_member(session, account_id=account.account_id, member_no="00000002")
    conversation = Conversation(
        account_id=account.account_id,
        external_conversation_id="wa:pn-2:u-1",
        customer_id=user.public_user_id,
        status="open",
    )
    session.add(conversation)
    session.commit()

    store = RuntimeStateStore(session)
    message = await store.record_outbound_message(
        account_id=account.account_id,
        conversation_id=conversation.external_conversation_id,
        recipient_id=user.public_user_id,
        text="echo",
        language_code="zh-CN",
        translated_text=None,
        translated_language_code=None,
        delivery_mode="echo",
        ai_generated=False,
        payload={"provider": "mock"},
    )
    assert message.ai_generated is False
    assert message.actor_type == "system"
    assert message.delivery_mode == "echo"
    # 没有传 snapshot 参数时使用会话默认
    assert message.ai_agent_id is None


# ────────────────────── AIOutboundJobService 政策校验 ──────────────────────


def _seed_ai_agent(session: Session, account_id: str) -> AIAgent:
    agent = AIAgent(
        account_id=account_id,
        name="test-agent",
        display_name="Test AI",
        status="active",
        provider_name="openai",
        model_name="gpt-4o-mini",
        health_status="healthy",
    )
    session.add(agent)
    session.commit()
    return agent


def test_outbound_policy_blocks_without_optin(session: Session) -> None:
    account, _ = _seed_basic(session)
    agent = _seed_ai_agent(session, account.account_id)
    svc = AIOutboundJobService(session)
    decision = svc.evaluate_policy(
        account_id=account.account_id,
        ai_agent_id=agent.id,
        opt_in=False,
    )
    assert decision.allowed is False
    assert decision.reason == "user_not_opted_in"


def test_outbound_policy_blocks_when_ai_not_active(session: Session) -> None:
    account, _ = _seed_basic(session)
    agent = _seed_ai_agent(session, account.account_id)
    agent.status = "disabled"
    session.add(agent)
    session.commit()
    svc = AIOutboundJobService(session)
    decision = svc.evaluate_policy(
        account_id=account.account_id, ai_agent_id=agent.id, opt_in=True
    )
    assert decision.allowed is False
    assert decision.reason == "ai_agent_not_active"


def test_outbound_policy_outside_window_requires_template(session: Session) -> None:
    account, _ = _seed_basic(session)
    user, _ = _seed_user_member(session, account_id=account.account_id)
    # 没有 inbound 消息 → 不在 service window
    agent = _seed_ai_agent(session, account.account_id)
    svc = AIOutboundJobService(session)
    decision = svc.evaluate_policy(
        account_id=account.account_id,
        user_id=user.id,
        ai_agent_id=agent.id,
        opt_in=True,
    )
    assert decision.allowed is False
    assert decision.template_required is True
    assert decision.reason == "outside_window_template_required"


def test_outbound_policy_outside_window_with_unapproved_template(session: Session) -> None:
    account, _ = _seed_basic(session)
    user, _ = _seed_user_member(session, account_id=account.account_id)
    agent = _seed_ai_agent(session, account.account_id)
    tpl = MessageTemplate(
        account_id=account.account_id,
        name="promo",
        language="zh-CN",
        category="marketing",
        status="PENDING",
    )
    session.add(tpl)
    session.commit()
    svc = AIOutboundJobService(session)
    decision = svc.evaluate_policy(
        account_id=account.account_id,
        user_id=user.id,
        ai_agent_id=agent.id,
        opt_in=True,
        template_id=tpl.id,
    )
    assert decision.allowed is False
    assert decision.reason == "template_not_approved"


def test_outbound_policy_outside_window_with_approved_template(session: Session) -> None:
    account, _ = _seed_basic(session)
    user, _ = _seed_user_member(session, account_id=account.account_id)
    agent = _seed_ai_agent(session, account.account_id)
    tpl = MessageTemplate(
        account_id=account.account_id,
        name="promo",
        language="zh-CN",
        category="marketing",
        status="APPROVED",
    )
    session.add(tpl)
    session.commit()
    svc = AIOutboundJobService(session)
    decision = svc.evaluate_policy(
        account_id=account.account_id,
        user_id=user.id,
        ai_agent_id=agent.id,
        opt_in=True,
        template_id=tpl.id,
    )
    assert decision.allowed is True
    assert decision.message_policy == "template"
    assert decision.template_required is True


def test_outbound_create_job_skipped_when_no_optin(session: Session) -> None:
    account, _ = _seed_basic(session)
    agent = _seed_ai_agent(session, account.account_id)
    svc = AIOutboundJobService(session)
    job = svc.create_job(
        account_id=account.account_id,
        agency_id=None,
        site_id=None,
        ai_agent_id=agent.id,
        user_id=None,
        member_profile_id=None,
        conversation_id=None,
        waba_id=None,
        phone_number_id=None,
        recipient_wa_id=None,
        trigger_type="marketing_blast",
        generated_text="hi",
        opt_in=False,
    )
    assert job.status == "skipped_policy"
    assert job.error_message == "user_not_opted_in"


# ────────────────────── OwnershipReportService ──────────────────────


def test_ownership_report_basic_aggregations(session: Session) -> None:
    account, site = _seed_basic(session)
    user_a, member_a = _seed_user_member(session, account_id=account.account_id, phone="13800000010", member_no="00000010")
    user_b, member_b = _seed_user_member(session, account_id=account.account_id, phone="13800000011", member_no="00000011")
    member_a.current_owner_staff_user_id = "staff-1"
    member_a.current_ai_agent_id = "ai-1"
    member_a.attribution_status = "owned"
    member_b.current_owner_staff_user_id = "staff-1"
    member_b.attribution_status = "owned"
    session.add_all([member_a, member_b])
    session.commit()
    svc = OwnershipReportService(session)
    report = svc.ownership_report(account_id=account.account_id)
    owner_breakdown = report["current"]["owner"]
    assert owner_breakdown["unattributed"] == 0
    by_owner = {row["owner_staff_user_id"]: row["member_count"] for row in owner_breakdown["by_owner"]}
    assert by_owner.get("staff-1") == 2
    ai_breakdown = report["current"]["ai"]
    assert ai_breakdown["no_ai_assignment"] == 1
    by_ai = {row["ai_agent_id"]: row["member_count"] for row in ai_breakdown["by_ai_agent"]}
    assert by_ai.get("ai-1") == 1


def test_ownership_report_anomalies_detect_no_ai_and_no_owner(session: Session) -> None:
    account, _ = _seed_basic(session)
    _seed_user_member(session, account_id=account.account_id, phone="13800000020", member_no="00000020")
    svc = OwnershipReportService(session)
    report = svc.anomalies(account_id=account.account_id)
    assert report["no_owner_member_count"] >= 1
    assert report["no_ai_member_count"] >= 1
