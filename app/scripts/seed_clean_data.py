#!/usr/bin/env python3
"""
Data cleanup and seed script for development/testing.

Creates a complete test dataset with multi-tenant structure:
- 1 super admin + 2 agencies + 2 admins + 5 members
- 2 H5 templates + 3 sites + 3 WABAs
- 12 members + 7 conversations + ~35 messages
- 5 products + 3 packages + 3 rules + 6 task instances
- 12 wallets + ~20 ledger entries + 3 billing
- 6 notifications + 3 languages + 15 translations + 2 secrets

Usage: python -m app.scripts.seed_clean_data
"""

import secrets
import sys
import uuid
from datetime import UTC, datetime, timedelta, date
from decimal import Decimal

from sqlalchemy import text

from app.db.models import (
    Account,
    Agency,
    Agent,
    AgencyMember,
    H5Template,
    AgencyTemplate,
    H5Site,
    H5SiteConfig,
    WhatsAppBusinessAccount,
    WhatsAppPhoneNumber,
    SiteWABABinding,
    MetaBusinessPortfolio,
    WebhookSubscription,
    AppUser,
    MemberProfile,
    MemberAuthSession,
    WalletAccount,
    WalletLedgerEntry,
    Conversation,
    Message,
    MessageEvent,
    Ticket,
    TicketMessage,
    Product,
    ProductPackage,
    TaskRule,
    MktTaskInstance,
    SignInRecord,
    InviteRecord,
    InviteLink,
    Notification,
    AuditLog,
    H5Language,
    H5Translation,
    Secret,
    SitePermission,
    ConversationNote,
    DeployHistory,
    AgencyBilling,
)
from app.db.session import get_sessionmaker
from app.services.agency_service import hash_password as hash_agency_pw


def new_id() -> str:
    return str(uuid.uuid4())


def short_id() -> str:
    return uuid.uuid4().hex[:12]


def utc_now() -> datetime:
    return datetime.now(UTC)


def days_ago(n: int) -> datetime:
    return utc_now() - timedelta(days=n)


# ──────────────────────────────────────────────
# Deletion order: children before parents
# ──────────────────────────────────────────────
TABLES_TO_CLEAN = [
    # Auth / sessions
    "member_auth_sessions",
    "admin_refresh_tokens",
    # Notifications
    "member_notifications",
    "notifications",
    # Verifications / bindings
    "member_verification_documents",
    "member_verification_requests",
    "member_whatsapp_binding_requests",
    # Wallet / finance (children before parents)
    "wallet_ledger_entries",
    "wallet_transfer_requests",
    "wallet_recharge_orders",
    "withdrawal_audit_logs",
    "withdrawal_requests",
    "wallet_accounts",
    # Sign-in / invite
    "sign_in_records",
    "invite_records",
    "invite_links",
    # Handover
    "handover_logs",
    "provider_status_event_buffer",
    # Fragment system
    "fragment_drop_logs",
    "fragment_ledger_entries",
    "fragment_inventory",
    "fragment_exchange_requests",
    "mailing_requests",
    "fragment_definitions",
    # Promotions / task packages
    "promotion_task_instances",
    "promotion_task_templates",
    "task_package_instance_items",
    "task_package_instances",
    "task_package_template_items",
    "task_package_templates",
    "user_referrals",
    # Task system
    "task_submission_proofs",
    "task_submissions",
    "task_review_decisions",
    "task_proof_files",
    "task_instances",
    "task_templates",
    "audience_rule_sets",
    "user_identities",
    "invite_codes",
    "user_tag_assignments",
    "user_tags",
    "mkt_task_instances",
    "task_rules",
    # Products
    "product_packages",
    "products",
    # Messages / conversations
    "message_events",
    "messages",
    "conversation_notes",
    "conversations",
    # Media
    "media_asset_provider_syncs",
    "media_asset_events",
    "media_assets",
    # Tickets
    "ticket_messages",
    "tickets",
    # Templates
    "template_send_logs",
    "message_templates",
    "template_daily_stats",
    "template_hourly_stats",
    "template_failure_stats",
    # WhatsApp stats
    "whatsapp_daily_stats",
    "whatsapp_conversation_stats",
    # WABA bindings
    "site_waba_bindings",
    "agency_templates",
    "agency_billing",
    "agency_members",
    # Site-level
    "site_permissions",
    "deploy_history",
    "uptime_checks",
    "admin_users",
    "translation_provider_configs",
    "h5_site_configs",
    "h5_languages",
    "h5_translations",
    # Member profiles / users (must be before h5_sites due to FK)
    "member_profiles",
    "app_users",
    "h5_sites",
    # WABA / Meta
    "whatsapp_phone_numbers",
    "whatsapp_business_accounts",
    "webhook_subscriptions",
    "embedded_signup_sessions",
    "meta_business_portfolios",
    # (handover moved up)
    # (provider status buffer moved up)
    "account_ai_provider_overrides",
    "ai_provider_configs",
    # Agents / Agencies
    "agents",
    "agencies",
    "h5_templates",
    # Support
    "support_knowledge_entries",
    "canned_responses",
    "business_hours",
    # Security
    "secrets",
    "ip_blacklist",
    # Audit / Monitoring
    "audit_logs",
    "client_errors",
    # Accounts (multi-tenant)
    "accounts",
    "member_orders",
]


def clean_all(session) -> None:
    """Delete all business data in FK-safe order (children first)."""
    print("=" * 60)
    print("Step 1: Cleaning all business tables ...")
    print("=" * 60)
    count = 0
    for table in TABLES_TO_CLEAN:
        try:
            session.execute(text(f"DELETE FROM \"{table}\""))
            count += 1
        except Exception as exc:
            print(f"  ⚠  SKIP {table}: {exc}")
    session.commit()
    print(f"  ✅ Cleaned {count}/{len(TABLES_TO_CLEAN)} tables\n")


# ── Helper: create member user ─────────────────
def create_member_user(
    session, account_id: str, site_id: str, display_name: str, member_no: str,
    balance_initial: float = 0.0,
) -> tuple[AppUser, MemberProfile, WalletAccount]:
    """Create an AppUser + MemberProfile + WalletAccount."""
    user = AppUser(
        id=new_id(),
        account_id=account_id,
        public_user_id=f"pub-{short_id()}",
        registration_site_id=site_id,
        display_name=display_name,
        country_code="86",
        language_code="zh-CN",
        is_anonymous=False,
        has_phone=True,
        has_email=False,
        has_whatsapp=False,
        is_new_user=True,
        lifecycle_status="active",
        last_active_at=days_ago(1),
        created_at=days_ago(14),
    )
    session.add(user)
    session.flush()

    profile = MemberProfile(
        id=new_id(),
        account_id=account_id,
        user_id=user.id,
        member_no=member_no,
        password_hash=hash_agency_pw("Member@2026"),
        password_salt=secrets.token_hex(16),
        last_login_at=days_ago(1),
        created_at=days_ago(14),
    )
    session.add(profile)
    session.flush()

    wallet = WalletAccount(
        id=new_id(),
        account_id=account_id,
        user_id=user.id,
        system_balance=Decimal(str(balance_initial)),
        task_balance=Decimal("0.00"),
        currency="CNY",
        withdraw_threshold=Decimal("10.00"),
    )
    session.add(wallet)
    session.flush()

    return user, profile, wallet


# ── Seeds ─────────────────────────────────────

def seed_accounts(session) -> tuple[Account, Account]:
    """Create 2 accounts for multi-tenant data isolation."""
    print("=" * 60)
    print("Step 2: Creating accounts ...")
    print("=" * 60)
    acct_sh = Account(
        account_id="seed-acct-sh",
        display_name="上海锦囊",
        provider_type="mock",
        is_active=True,
        ai_enabled=True,
    )
    acct_sz = Account(
        account_id="seed-acct-sz",
        display_name="深圳启航",
        provider_type="mock",
        is_active=True,
        ai_enabled=True,
    )
    session.add_all([acct_sh, acct_sz])
    session.flush()
    print(f"  ✅ seed-acct-sh : 上海锦囊")
    print(f"  ✅ seed-acct-sz : 深圳启航\n")
    return acct_sh, acct_sz


def seed_super_admin(session) -> None:
    """Create super admin record in admin_users table."""
    print("=" * 60)
    print("Step 3: Creating super admin ...")
    print("=" * 60)
    pw_hash = hash_agency_pw("admin123")
    session.execute(
        text("""
            INSERT INTO admin_users (id, username, password_hash, role, is_active, created_at, updated_at)
            VALUES (:id, :username, :pw, :role, :active, :c, :c)
        """),
        {
            "id": new_id(),
            "username": "admin",
            "pw": pw_hash,
            "role": "super_admin",
            "active": True,
            "c": utc_now(),
        },
    )
    session.flush()
    print("  ✅ admin / admin123\n")


def seed_agent_member_passwords(session) -> None:
    """Store agent_member passwords in admin_users for workspace-auth login."""
    members = [
        ("finance_sh", "Finance@2026", "agent_member"),
        ("manager_sh", "Manager@2026", "agent_member"),
        ("support_sh", "Support@2026", "agent_member"),
        ("finance_sz", "Finance@2026", "agent_member"),
        ("support_sz", "Support@2026", "agent_member"),
    ]
    for username, pw, role in members:
        exists = session.execute(
            text("SELECT 1 FROM admin_users WHERE username = :u"), {"u": username}
        ).scalar()
        if not exists:
            pw_hash = hash_agency_pw(pw)
            session.execute(
                text("""
                    INSERT INTO admin_users (id, username, password_hash, role, is_active, created_at, updated_at)
                    VALUES (:id, :username, :pw, :role, :active, :c, :c)
                """),
                {
                    "id": new_id(),
                    "username": username,
                    "pw": pw_hash,
                    "role": role,
                    "active": True,
                    "c": utc_now(),
                },
            )
    session.flush()
    print("  ✅ 5 agent_member password records in admin_users\n")


def seed_templates(session) -> tuple[H5Template, H5Template]:
    """Create 2 H5 templates."""
    print("=" * 60)
    print("Step 4: Creating H5 templates ...")
    print("=" * 60)
    tpl1 = H5Template(
        id=new_id(),
        name="默认商城版",
        description="当前 H5 会员端标准模板，适用于商城类业务",
        preview_url="/preview/default.png",
        template_data={
            "version": "1.0.0",
            "frontend_build": "dist/",
            "theme": {"primaryColor": "#1677ff"},
            "pages": ["home", "tasks", "invite", "profile", "recharge", "withdraw"],
        },
    )
    tpl2 = H5Template(
        id=new_id(),
        name="简约商务版",
        description="简约商务风格模板，适用于企业展示与客服场景",
        preview_url="/preview/business.png",
        template_data={
            "version": "1.0.0",
            "frontend_build": "dist/business/",
            "theme": {"primaryColor": "#2f54eb"},
            "pages": ["home", "tasks", "invite", "profile", "recharge"],
        },
    )
    session.add_all([tpl1, tpl2])
    session.flush()
    print(f"  ✅ {tpl1.name} ({tpl1.id})")
    print(f"  ✅ {tpl2.name} ({tpl2.id})\n")
    return tpl1, tpl2


def seed_agency_a(session, acct_sh: Account, tpl1: H5Template) -> list:
    """
    Create Agency A: 上海锦囊
    - 1 admin (agent_sh), 3 members (finance, manager, support)
    - 2 sites (wechat-01, douyin-01) each with WABA
    - 8 users across both sites
    """
    print("=" * 60)
    print("Step 5: Creating Agency A — 上海锦囊 ...")
    print("=" * 60)

    # Agency
    agency = Agency(
        id=new_id(),
        name="上海锦囊",
        brand_name="锦囊科技",
        status="online",
        username="agent_sh",
        password_hash=hash_agency_pw("Agent@2026"),
        contact_name="张经理",
        contact_phone="021-6888-8888",
        contact_email="contact@jinnang.tech",
        created_at=days_ago(30),
    )
    session.add(agency)
    session.flush()

    # Admin agent
    admin_agent = Agent(
        id=new_id(),
        account_id=acct_sh.account_id,
        agency_id=agency.id,
        agent_key="agent_sh",
        display_name="上海锦囊管理员",
        email="admin@jinnang.tech",
        status="online",
        is_active=True,
        user_type="agent",
    )
    session.add(admin_agent)
    session.flush()

    # Agency member link
    session.add(AgencyMember(id=new_id(), agency_id=agency.id, user_id=admin_agent.id, role="admin"))

    # 3 subordinate agents
    subs = []
    for key, name, role in [
        ("finance_sh", "财务-锦囊", "finance"),
        ("manager_sh", "经理-锦囊", "manager"),
        ("support_sh", "客服-锦囊", "support"),
    ]:
        ag = Agent(
            id=new_id(),
            account_id=acct_sh.account_id,
            agency_id=agency.id,
            agent_key=key,
            display_name=name,
            status="online",
            is_active=True,
            user_type="agent_member",
        )
        session.add(ag)
        session.flush()
        session.add(AgencyMember(id=new_id(), agency_id=agency.id, user_id=ag.id, role=role))
        subs.append(ag)

    # ── Site 1: wechat-01 ──
    site1 = H5Site(
        id=new_id(),
        account_id=acct_sh.account_id,
        agency_id=agency.id,
        site_key="wechat-01",
        domain="h5-wechat.example.com",
        brand_name="锦囊微信商城",
        default_language="zh-CN",
        status="online",
        metadata_json={"channel": "wechat", "template_id": tpl1.id},
        created_at=days_ago(25),
    )
    session.add(site1)
    session.flush()
    session.add(H5SiteConfig(id=new_id(), site_id=site1.id, primary_color="#1677ff", ssl_enabled=True))
    session.add(SitePermission(id=new_id(), user_id=admin_agent.id, site_id=site1.id, role="admin"))

    # WABA + Phone for site1
    waba1 = WhatsAppBusinessAccount(
        id=new_id(),
        account_id=acct_sh.account_id,
        agency_id=agency.id,
        waba_id="waba-sh-01",
        onboarding_mode="manual",
        token_source="manual",
        is_active=True,
        ai_enabled=True,
        webhook_subscribed=False,
    )
    session.add(waba1)
    session.flush()
    pn1 = WhatsAppPhoneNumber(
        id=new_id(),
        account_id=acct_sh.account_id,
        waba_account_id=waba1.id,
        phone_number_id="phn-sh-01",
        display_phone_number="+86-138-0001",
        verified_name="锦囊科技",
        quality_rating="GREEN",
        is_registered=True,
        is_active=True,
        waba_id=waba1.waba_id,
    )
    session.add(pn1)
    session.flush()
    session.add(SiteWABABinding(id=new_id(), site_id=site1.id, waba_id=waba1.id, assigned_at=utc_now()))

    # 5 members for site1
    site1_users = []
    site1_convs = []
    for i in range(1, 6):
        bal = 0.0 if i <= 3 else 50.0 + i * 10.0
        u, prof, w = create_member_user(
            session, acct_sh.account_id, site1.id,
            f"微信用户{i:02d}", f"M{i:07d}", bal,
        )
        site1_users.append((u, prof, w))
        session.add(InviteLink(id=new_id(), account_id=acct_sh.account_id, user_id=u.id, invite_code=f"inv-{short_id()}"))

    # 3 conversations for site1 (user 1-3)
    for j in range(3):
        u, prof, w = site1_users[j]
        conv = Conversation(
            id=new_id(),
            account_id=acct_sh.account_id,
            external_conversation_id=f"ext-{short_id()}",
            phone_number_id=pn1.id,
            customer_id=u.public_user_id,
            customer_language="zh-CN",
            status="open",
            ai_enabled=True,
            management_mode="ai_managed",
            site_key=site1.site_key,
            last_message_at=days_ago(j),
            created_at=days_ago(10 - j),
        )
        session.add(conv)
        session.flush()
        site1_convs.append(conv)
        for k in range(5):
            direction = "inbound" if k % 2 == 0 else "outbound"
            sender = u.public_user_id if k % 2 == 0 else pn1.display_phone_number
            recipient = pn1.display_phone_number if k % 2 == 0 else u.public_user_id
            msg = Message(
                id=new_id(),
                account_id=acct_sh.account_id,
                conversation_id=conv.id,
                phone_number_id=pn1.id,
                provider_message_id=f"pm-{short_id()}",
                direction=direction,
                message_type="text",
                sender_id=sender,
                recipient_id=recipient,
                content_text=f"这是会话{j+1}的第{k+1}条消息" + ("（来自会员）" if k % 2 == 0 else "（来自客服）"),
                ai_generated=(k % 2 == 1),
                created_at=days_ago(10 - j) + timedelta(hours=k),
            )
            session.add(msg)

    # ── Site 2: douyin-01 ──
    site2 = H5Site(
        id=new_id(),
        account_id=acct_sh.account_id,
        agency_id=agency.id,
        site_key="douyin-01",
        domain="h5-douyin.example.com",
        brand_name="锦囊抖音小店",
        default_language="zh-CN",
        status="online",
        metadata_json={"channel": "douyin", "template_id": tpl1.id},
        created_at=days_ago(20),
    )
    session.add(site2)
    session.flush()
    session.add(H5SiteConfig(id=new_id(), site_id=site2.id, primary_color="#ff4d4f", ssl_enabled=True))
    session.add(SitePermission(id=new_id(), user_id=admin_agent.id, site_id=site2.id, role="admin"))

    waba2 = WhatsAppBusinessAccount(
        id=new_id(),
        account_id=acct_sh.account_id,
        agency_id=agency.id,
        waba_id="waba-sh-02",
        onboarding_mode="manual",
        token_source="manual",
        is_active=True,
        ai_enabled=True,
        webhook_subscribed=False,
    )
    session.add(waba2)
    session.flush()
    pn2 = WhatsAppPhoneNumber(
        id=new_id(),
        account_id=acct_sh.account_id,
        waba_account_id=waba2.id,
        phone_number_id="phn-sh-02",
        display_phone_number="+86-138-0002",
        verified_name="锦囊抖音",
        quality_rating="GREEN",
        is_registered=True,
        is_active=True,
        waba_id=waba2.waba_id,
    )
    session.add(pn2)
    session.flush()
    session.add(SiteWABABinding(id=new_id(), site_id=site2.id, waba_id=waba2.id, assigned_at=utc_now()))

    site2_users = []
    site2_convs = []
    for i in range(1, 4):
        bal = 20.0 + i * 15.0
        u, prof, w = create_member_user(
            session, acct_sh.account_id, site2.id,
            f"抖音用户{i:02d}", f"M{i + 5:07d}", bal,
        )
        site2_users.append((u, prof, w))
        session.add(InviteLink(id=new_id(), account_id=acct_sh.account_id, user_id=u.id, invite_code=f"inv-{short_id()}"))

    # 2 conversations for site2 (user 1-2)
    for j in range(2):
        u, prof, w = site2_users[j]
        conv = Conversation(
            id=new_id(),
            account_id=acct_sh.account_id,
            external_conversation_id=f"ext-{short_id()}",
            phone_number_id=pn2.id,
            customer_id=u.public_user_id,
            customer_language="zh-CN",
            status="open",
            ai_enabled=True,
            management_mode="ai_managed",
            site_key=site2.site_key,
            last_message_at=days_ago(j),
            created_at=days_ago(7 - j),
        )
        session.add(conv)
        session.flush()
        site2_convs.append(conv)
        for k in range(5):
            direction = "inbound" if k % 2 == 0 else "outbound"
            sender = u.public_user_id if k % 2 == 0 else pn2.display_phone_number
            recipient = pn2.display_phone_number if k % 2 == 0 else u.public_user_id
            msg = Message(
                id=new_id(),
                account_id=acct_sh.account_id,
                conversation_id=conv.id,
                phone_number_id=pn2.id,
                provider_message_id=f"pm-{short_id()}",
                direction=direction,
                message_type="text",
                sender_id=sender,
                recipient_id=recipient,
                content_text=f"抖音会话{j+1}的第{k+1}条消息",
                ai_generated=(k % 2 == 1),
                created_at=days_ago(7 - j) + timedelta(hours=k),
            )
            session.add(msg)

    # ── Ticket for site1 user1 ──
    tk1 = Ticket(
        id=new_id(),
        account_id=acct_sh.account_id,
        ticket_no="TK-202606-0001",
        user_id=site1_users[0][0].id,
        site_id=site1.id,
        site_key=site1.site_key,
        ticket_type="help",
        status="open",
        priority="medium",
        title="订单配送问题",
        is_active=True,
        created_at=days_ago(2),
    )
    session.add(tk1)
    session.flush()
    session.add(TicketMessage(
        id=new_id(),
        ticket_id=tk1.id,
        sender_type="customer",
        body_text="我的订单显示已发货但一直没收到，请帮忙查询。",
        is_internal=False,
        created_at=days_ago(2),
    ))

    # ✅ Tickets for site1 user2 (resolved)
    tk2 = Ticket(
        id=new_id(),
        account_id=acct_sh.account_id,
        ticket_no="TK-202606-0002",
        user_id=site1_users[1][0].id,
        site_id=site1.id,
        site_key=site1.site_key,
        ticket_type="help",
        status="resolved",
        priority="low",
        title="商品咨询已处理",
        is_active=False,
        resolved_at=days_ago(1),
        created_at=days_ago(5),
    )
    session.add(tk2)

    # ── Billing for Agency A ──
    bill_a1 = AgencyBilling(
        id=new_id(),
        agency_id=agency.id,
        billing_type="monthly",
        amount=Decimal("2999.00"),
        billing_period_start=date(2026, 6, 1),
        billing_period_end=date(2026, 6, 30),
        status="paid",
        line_items=[
            {"item": "基础服务费", "qty": 1, "unit_price": 1999, "subtotal": 1999},
            {"item": "站点费用（2站点）", "qty": 2, "unit_price": 500, "subtotal": 1000},
        ],
    )
    session.add(bill_a1)
    bill_a2 = AgencyBilling(
        id=new_id(),
        agency_id=agency.id,
        billing_type="per_site",
        amount=Decimal("5000.00"),
        billing_period_start=date(2026, 7, 1),
        billing_period_end=date(2026, 7, 31),
        status="pending",
        line_items=[
            {"item": "站点附加费", "qty": 2, "unit_price": 2500, "subtotal": 5000},
        ],
    )
    session.add(bill_a2)

    # ── Template binding ──
    session.add(AgencyTemplate(id=new_id(), agency_id=agency.id, template_id=tpl1.id))

    # ── Notifications for Agency A ──
    for notif in [
        ("模板更新通知", "默认商城版模板已更新至 v1.0.1", "info", False, days_ago(3)),
        ("账单提醒", "7月账单已生成，请及时查看", "warning", False, days_ago(1)),
        ("系统通知", "SSL 证书将于 7 天后过期，请及时续期", "warning", True, days_ago(5)),
    ]:
        session.add(Notification(
            id=new_id(),
            account_id=acct_sh.account_id,
            type="system",
            category="notice",
            title=notif[0],
            message=notif[1],
            severity=notif[2],
            is_read=notif[3],
            created_at=notif[4],
        ))

    session.flush()
    print(f"  ✅ 上海锦囊 (agency={agency.id})")
    print(f"     Admin: agent_sh / Agent@2026")
    print(f"     Members: finance_sh, manager_sh, support_sh")
    print(f"     Sites: wechat-01 (5 users, 3 convs), douyin-01 (3 users, 2 convs)")
    print(f"     WABAs: waba-sh-01 (+86-138-0001), waba-sh-02 (+86-138-0002)")
    print(f"     Tickets: 2, Billings: 2, Notifications: 3\n")

    return {
        "agency": agency,
        "admin_agent": admin_agent,
        "subs": subs,
        "sites": [site1, site2],
        "wabas": [waba1, waba2],
        "phones": [pn1, pn2],
        "users": [site1_users, site2_users],
        "convs": [site1_convs, site2_convs],
    }


def seed_agency_b(session, acct_sz: Account, tpl2: H5Template) -> dict:
    """
    Create Agency B: 深圳启航
    - 1 admin (agent_sz), 2 members (finance, support)
    - 1 site (xiaohongshu-01) with WABA
    - 4 users
    """
    print("=" * 60)
    print("Step 6: Creating Agency B — 深圳启航 ...")
    print("=" * 60)

    agency = Agency(
        id=new_id(),
        name="深圳启航",
        brand_name="启航网络",
        status="online",
        username="agent_sz",
        password_hash=hash_agency_pw("Agent@2026"),
        contact_name="李总",
        contact_phone="0755-8888-9999",
        contact_email="contact@qihang.net",
        created_at=days_ago(28),
    )
    session.add(agency)
    session.flush()

    admin_agent = Agent(
        id=new_id(),
        account_id=acct_sz.account_id,
        agency_id=agency.id,
        agent_key="agent_sz",
        display_name="深圳启航管理员",
        email="admin@qihang.net",
        status="online",
        is_active=True,
        user_type="agent",
    )
    session.add(admin_agent)
    session.flush()
    session.add(AgencyMember(id=new_id(), agency_id=agency.id, user_id=admin_agent.id, role="admin"))

    subs = []
    for key, name, role in [
        ("finance_sz", "财务-启航", "finance"),
        ("support_sz", "客服-启航", "support"),
    ]:
        ag = Agent(
            id=new_id(),
            account_id=acct_sz.account_id,
            agency_id=agency.id,
            agent_key=key,
            display_name=name,
            status="online",
            is_active=True,
            user_type="agent_member",
        )
        session.add(ag)
        session.flush()
        session.add(AgencyMember(id=new_id(), agency_id=agency.id, user_id=ag.id, role=role))
        subs.append(ag)

    # Site 3: xiaohongshu-01
    site = H5Site(
        id=new_id(),
        account_id=acct_sz.account_id,
        agency_id=agency.id,
        site_key="xiaohongshu-01",
        domain="h5-xhs.example.com",
        brand_name="启航小红书商城",
        default_language="zh-CN",
        status="online",
        metadata_json={"channel": "xiaohongshu", "template_id": tpl2.id},
        created_at=days_ago(22),
    )
    session.add(site)
    session.flush()
    session.add(H5SiteConfig(id=new_id(), site_id=site.id, primary_color="#2f54eb", ssl_enabled=True))
    session.add(SitePermission(id=new_id(), user_id=admin_agent.id, site_id=site.id, role="admin"))

    waba = WhatsAppBusinessAccount(
        id=new_id(),
        account_id=acct_sz.account_id,
        agency_id=agency.id,
        waba_id="waba-sz-01",
        onboarding_mode="manual",
        token_source="manual",
        is_active=True,
        ai_enabled=True,
        webhook_subscribed=False,
    )
    session.add(waba)
    session.flush()
    pn = WhatsAppPhoneNumber(
        id=new_id(),
        account_id=acct_sz.account_id,
        waba_account_id=waba.id,
        phone_number_id="phn-sz-01",
        display_phone_number="+86-139-0001",
        verified_name="启航网络",
        quality_rating="GREEN",
        is_registered=True,
        is_active=True,
        waba_id=waba.waba_id,
    )
    session.add(pn)
    session.flush()
    session.add(SiteWABABinding(id=new_id(), site_id=site.id, waba_id=waba.id, assigned_at=utc_now()))

    site_users = []
    site_convs = []
    for i in range(1, 5):
        bal = 10.0 + i * 20.0
        u, prof, w = create_member_user(
            session, acct_sz.account_id, site.id,
            f"小红书用户{i:02d}", f"M{i + 8:07d}", bal,
        )
        site_users.append((u, prof, w))
        session.add(InviteLink(id=new_id(), account_id=acct_sz.account_id, user_id=u.id, invite_code=f"inv-{short_id()}"))

    # 2 conversations for site3 (user 1-2)
    for j in range(2):
        u, prof, w = site_users[j]
        conv = Conversation(
            id=new_id(),
            account_id=acct_sz.account_id,
            external_conversation_id=f"ext-{short_id()}",
            phone_number_id=pn.id,
            customer_id=u.public_user_id,
            customer_language="zh-CN",
            status="open",
            ai_enabled=True,
            management_mode="ai_managed",
            site_key=site.site_key,
            last_message_at=days_ago(j),
            created_at=days_ago(5 - j),
        )
        session.add(conv)
        session.flush()
        site_convs.append(conv)
        for k in range(5):
            direction = "inbound" if k % 2 == 0 else "outbound"
            sender = u.public_user_id if k % 2 == 0 else pn.display_phone_number
            recipient = pn.display_phone_number if k % 2 == 0 else u.public_user_id
            msg = Message(
                id=new_id(),
                account_id=acct_sz.account_id,
                conversation_id=conv.id,
                phone_number_id=pn.id,
                provider_message_id=f"pm-{short_id()}",
                direction=direction,
                message_type="text",
                sender_id=sender,
                recipient_id=recipient,
                content_text=f"小红书会话{j+1}的第{k+1}条消息",
                ai_generated=(k % 2 == 1),
                created_at=days_ago(5 - j) + timedelta(hours=k),
            )
            session.add(msg)

    # Billing for Agency B
    bill_b = AgencyBilling(
        id=new_id(),
        agency_id=agency.id,
        billing_type="monthly",
        amount=Decimal("1500.00"),
        billing_period_start=date(2026, 6, 1),
        billing_period_end=date(2026, 6, 30),
        status="pending",
        line_items=[
            {"item": "基础服务费", "qty": 1, "unit_price": 1000, "subtotal": 1000},
            {"item": "站点费用（1站点）", "qty": 1, "unit_price": 500, "subtotal": 500},
        ],
    )
    session.add(bill_b)

    # Template binding
    session.add(AgencyTemplate(id=new_id(), agency_id=agency.id, template_id=tpl2.id))

    # Notifications for Agency B
    for notif in [
        ("模板更新通知", "简约商务版模板已更新至 v1.0.1", "info", False, days_ago(2)),
        ("系统通知", "欢迎使用启航网络管理系统", "info", True, days_ago(20)),
        ("账单提醒", "6月账单待支付，金额 ¥1500", "warning", False, days_ago(1)),
    ]:
        session.add(Notification(
            id=new_id(),
            account_id=acct_sz.account_id,
            type="system",
            category="notice",
            title=notif[0],
            message=notif[1],
            severity=notif[2],
            is_read=notif[3],
            created_at=notif[4],
        ))

    session.flush()
    print(f"  ✅ 深圳启航 (agency={agency.id})")
    print(f"     Admin: agent_sz / Agent@2026")
    print(f"     Members: finance_sz, support_sz")
    print(f"     Sites: xiaohongshu-01 (4 users, 2 convs)")
    print(f"     WABAs: waba-sz-01 (+86-139-0001)")
    print(f"     Billings: 1, Notifications: 3\n")

    return {
        "agency": agency,
        "admin_agent": admin_agent,
        "subs": subs,
        "sites": [site],
        "wabas": [waba],
        "phones": [pn],
        "users": [site_users],
        "convs": [site_convs],
    }


def seed_products_and_tasks(session, acct_sh: Account, acct_sz: Account, sites_a: list, sites_b: list) -> None:
    """Create 5 products, 3 packages, 3 rules, 6 task instances with sign-in/invite records."""
    print("=" * 60)
    print("Step 7: Creating products, packages, rules, tasks ...")
    print("=" * 60)

    all_sites = sites_a + sites_b

    # ── 5 Products (3 for Agency A, 2 for Agency B) ──
    prods = []
    prod_data = [
        ("acct-sh", acct_sh.account_id, "高端蓝牙耳机", 299.00),
        ("acct-sh", acct_sh.account_id, "智能手表 Pro", 599.00),
        ("acct-sh", acct_sh.account_id, "无线充电宝", 99.00),
        ("acct-sz", acct_sz.account_id, "运动手环", 149.00),
        ("acct-sz", acct_sz.account_id, "瑜伽垫", 79.00),
    ]
    for _, aid, name, price in prod_data:
        p = Product(
            id=new_id(),
            account_id=aid,
            name=name,
            price=Decimal(str(price)),
            tags=["测试商品", "种子数据"],
        )
        session.add(p)
        prods.append(p)
    session.flush()

    # ── 3 Product Packages (1 per site) ──
    packages = []
    pkg_sites = [sites_a[0], sites_a[1], sites_b[0]]
    pkg_prods = [[prods[0].id, prods[2].id], [prods[1].id], [prods[3].id, prods[4].id]]
    pkg_values = [398.00, 599.00, 228.00]
    pkg_names = ["数码超值包", "智能穿戴包", "运动健康包"]

    for idx, site in enumerate(pkg_sites):
        aid = site.account_id
        pk = ProductPackage(
            id=new_id(),
            account_id=aid,
            name=pkg_names[idx],
            target_amount=Decimal(str(pkg_values[idx])),
            amount_tolerance_pct=10,
            product_count=len(pkg_prods[idx]),
            product_ids=pkg_prods[idx],
            product_snapshot=[{"product_id": pid, "name": f"商品{pid[:8]}"} for pid in pkg_prods[idx]],
            total_value=Decimal(str(pkg_values[idx])),
            completion_reward=Decimal(str(round(pkg_values[idx] * 0.1, 2))),
        )
        session.add(pk)
        packages.append(pk)
    session.flush()

    # ── 3 Task Rules ──
    rules = []
    rule_defs = [
        ("签到奖励规则", "sign_in", "automatic", packages[0].id, acct_sh.account_id),
        ("邀请好友规则", "invite", "automatic", packages[1].id, acct_sh.account_id),
        ("手动推送规则", "push", "manual", packages[2].id, acct_sz.account_id),
    ]
    for name, rtype, trigger, pkg_id, aid in rule_defs:
        r = TaskRule(
            id=new_id(),
            account_id=aid,
            name=name,
            rule_type=rtype,
            trigger_type=trigger,
            trigger_config={"max_per_day": 1} if rtype == "sign_in" else {},
            package_id=pkg_id,
            is_enabled=True,
        )
        session.add(r)
        rules.append(r)
    session.flush()

    # ── 6 Task Instances (2 per site, using first 3 sites) ──
    all_users_flat = []
    for acct, sites_list in [(acct_sh, sites_a), (acct_sz, sites_b)]:
        for s in sites_list:
            users = session.query(AppUser).filter(
                AppUser.account_id == acct.account_id,
                AppUser.registration_site_id == s.id,
            ).limit(3).all()
            all_users_flat.append((acct, s, users))

    task_instances = []
    task_idx = 0
    for aid, rtid, pkgid, stype in [
        (acct_sh.account_id, rules[0].id, packages[0].id, "sign_in"),
        (acct_sh.account_id, rules[1].id, packages[1].id, "invite"),
        (acct_sz.account_id, rules[2].id, packages[2].id, "push"),
    ]:
        for _ in range(2):  # 2 instances each
            ti = MktTaskInstance(
                id=new_id(),
                account_id=aid,
                user_id=all_users_flat[task_idx % len(all_users_flat)][2][0].id if all_users_flat[task_idx % len(all_users_flat)][2] else all_users_flat[0][2][0].id,
                rule_id=rtid,
                package_id=pkgid,
                task_type=stype,
                status="active" if task_idx % 2 == 0 else "completed",
                total_paid=Decimal("0.00"),
                reward_amount=Decimal("10.00"),
                site_key=all_sites[task_idx % len(all_sites)].site_key,
                created_at=days_ago(7 - task_idx),
                started_at=days_ago(7 - task_idx) if task_idx % 2 == 0 else days_ago(7 - task_idx),
                completed_at=None if task_idx % 2 == 0 else days_ago(1),
                expires_at=utc_now() + timedelta(days=30),
            )
            session.add(ti)
            task_instances.append(ti)
            task_idx += 1

    # ── 6 SignInRecords ──
    for si in range(6):
        u_idx = si % len(all_users_flat)
        uid = all_users_flat[u_idx][2][0].id if all_users_flat[u_idx][2] else None
        aid = all_users_flat[u_idx][0].account_id
        if uid:
            session.add(SignInRecord(
                id=new_id(),
                account_id=aid,
                user_id=uid,
                sign_date=date(2026, 6, 10 - si),
                consecutive_days=min(si + 1, 5),
                is_rewarded=(si % 2 == 0),
            ))

    # ── 3 InviteRecords ──
    for ir in range(3):
        u1 = all_users_flat[ir][2][0] if all_users_flat[ir][2] else None
        u2_idx = (ir + 1) % len(all_users_flat)
        u2 = all_users_flat[u2_idx][2][0] if all_users_flat[u2_idx][2] else None
        if u1 and u2:
            session.add(InviteRecord(
                id=new_id(),
                account_id=all_users_flat[ir][0].account_id,
                inviter_user_id=u1.id,
                invitee_user_id=u2.id,
                invite_type="share",
                reward_amount=Decimal("5.00"),
                is_rewarded=True,
            ))

    # ── Wallet Ledger Entries (~20) ──
    wallets = session.query(WalletAccount).all()
    for idx, w in enumerate(wallets[:12]):
        # Each wallet gets at least 1 entry, first 8 get 2 entries
        session.add(WalletLedgerEntry(
            id=new_id(),
            account_id=w.account_id,
            wallet_account_id=w.id,
            user_id=w.user_id,
            ledger_type="system",
            transaction_type="recharge" if idx % 2 == 0 else "reward",
            direction="in",
            amount=Decimal("100.00") if idx % 2 == 0 else Decimal("20.00"),
            currency="CNY",
            status="paid",
            note="种子数据初始充值" if idx % 2 == 0 else "任务奖励",
        ))
        if idx < 8:
            session.add(WalletLedgerEntry(
                id=new_id(),
                account_id=w.account_id,
                wallet_account_id=w.id,
                user_id=w.user_id,
                ledger_type="task",
                transaction_type="reward",
                direction="in",
                amount=Decimal("10.00"),
                currency="CNY",
                status="paid",
                note="签到奖励",
            ))

    session.flush()
    print(f"  ✅ 5 products, 3 packages, 3 rules, {len(task_instances)} task instances")
    print(f"  ✅ 6 sign-in records, 3 invite records, ~20 wallet entries\n")


def seed_languages_and_translations(session, all_sites: list) -> None:
    """Create 3 languages + 15 translations (5 per site)."""
    print("=" * 60)
    print("Step 8: Creating languages and translations ...")
    print("=" * 60)

    langs = [
        ("zh-CN", "中文", "🇨🇳", True, True),
        ("en-US", "English", "🇺🇸", True, False),
        ("ja-JP", "日本語", "🇯🇵", True, False),
    ]
    for code, name, flag, enabled, default in langs:
        session.add(H5Language(
            id=new_id(), language_code=code, display_name=name,
            flag_emoji=flag, is_enabled=enabled, is_default=default,
        ))
    session.flush()

    translation_keys = [
        ("home.title", "首页标题"),
        ("home.banner", "首页横幅"),
        ("tasks.title", "任务中心标题"),
        ("profile.title", "个人中心标题"),
        ("wallet.balance", "钱包余额"),
    ]
    translations_en = [
        "Home Page Title", "Home Banner", "Task Center Title",
        "Profile Title", "Wallet Balance",
    ]
    translations_ja = [
        "ホームページタイトル", "ホームバナー", "タスクセンタータイトル",
        "プロフィールタイトル", "ウォレット残高",
    ]

    for site in all_sites:
        for i, (key, zh_text) in enumerate(translation_keys):
            # Chinese
            session.add(H5Translation(
                id=new_id(), site_id=site.id, language_code="zh-CN",
                translation_key=key, translated_text=zh_text,
                is_ai_translated=False,
            ))
            # English
            session.add(H5Translation(
                id=new_id(), site_id=site.id, language_code="en-US",
                translation_key=key, translated_text=translations_en[i],
                is_ai_translated=True,
            ))
            # Japanese
            session.add(H5Translation(
                id=new_id(), site_id=site.id, language_code="ja-JP",
                translation_key=key, translated_text=translations_ja[i],
                is_ai_translated=True,
            ))

    session.flush()
    print(f"  ✅ 3 languages, {len(all_sites) * 15} translations ({len(all_sites)} sites * 5 keys * 3 langs)\n")


def seed_secrets(session) -> None:
    """Create 2 secrets (OpenAI + DeepSeek API keys)."""
    print("=" * 60)
    print("Step 9: Creating secrets ...")
    print("=" * 60)
    session.add_all([
        Secret(
            id=new_id(), name="OpenAI API Key",
            encrypted_value="sk-seed-openai-placeholder",
            description="OpenAI API 密钥（种子数据占位）",
        ),
        Secret(
            id=new_id(), name="DeepSeek API Key",
            encrypted_value="sk-seed-deepseek-placeholder",
            description="DeepSeek API 密钥（种子数据占位）",
        ),
    ])
    session.flush()
    print("  ✅ OpenAI API Key, DeepSeek API Key\n")


def seed_audit_logs(session) -> None:
    """Create audit log entries for the seed operation."""
    print("=" * 60)
    print("Step 10: Creating audit logs ...")
    print("=" * 60)
    logs = [
        AuditLog(
            id=new_id(), account_id="seed-acct-sh",
            actor_type="system", actor_id="seed-script",
            action="seed_data_created",
            target_type="system", target_id="all",
            payload={"reason": "种子数据初始化", "tables_cleaned": len(TABLES_TO_CLEAN)},
        ),
    ]
    session.add_all(logs)
    session.flush()
    print("  ✅ 1 audit log entry\n")


# ── Main ─────────────────────────────────────

def main() -> None:
    session = get_sessionmaker()()
    try:
        # 1. Clean
        clean_all(session)

        # 2. Base entities
        acct_sh, acct_sz = seed_accounts(session)
        seed_super_admin(session)
        tpl1, tpl2 = seed_templates(session)

        # 3. Agencies
        data_a = seed_agency_a(session, acct_sh, tpl1)
        data_b = seed_agency_b(session, acct_sz, tpl2)

        # 4. Agent member passwords (for workspace-auth login)
        seed_agent_member_passwords(session)

        # 5. Products & tasks
        all_sites = data_a["sites"] + data_b["sites"]
        seed_products_and_tasks(session, acct_sh, acct_sz, data_a["sites"], data_b["sites"])

        # 5. Languages & translations
        seed_languages_and_translations(session, all_sites)

        # 6. Secrets & audit
        seed_secrets(session)
        seed_audit_logs(session)

        # ── Commit ──
        session.commit()

        # ── Summary ──
        print("=" * 60)
        print("🎉 种子数据创建完成！")
        print("=" * 60)
        print()
        print("超管登录:")
        print("  账号: admin / admin123")
        print()
        print("代理商 A - 上海锦囊 (锦囊科技):")
        print("  管理员: agent_sh / Agent@2026")
        print("  下属:")
        print("    - 财务: finance_sh / Finance@2026")
        print("    - 经理: manager_sh / Manager@2026")
        print("    - 客服: support_sh / Support@2026")
        print("  站点: wechat-01 (5会员), douyin-01 (3会员)")
        print("  会话: 3 + 2 = 5")
        print("  工单: 2 (1待处理 + 1已解决)")
        print("  账单: 2 (1已付 + 1待付)")
        print()
        print("代理商 B - 深圳启航 (启航网络):")
        print("  管理员: agent_sz / Agent@2026")
        print("  下属:")
        print("    - 财务: finance_sz / Finance@2026")
        print("    - 客服: support_sz / Support@2026")
        print("  站点: xiaohongshu-01 (4会员)")
        print("  会话: 2")
        print("  账单: 1 (待付)")
        print()
        print("会员默认密码: Member@2026")

    except Exception as exc:
        session.rollback()
        print(f"\n❌ 种子数据创建失败: {exc}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()
