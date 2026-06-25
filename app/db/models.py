from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    Float,
    and_,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    JSON,
    Numeric,
    or_,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, foreign, mapped_column, relationship

from app.core.platform_enums import (
    AudienceRuleStatus,
    H5SiteStatus,
    InviteCodeStatus,
    TaskProofFileStatus,
    TaskReviewDecisionSource,
    TaskReviewDecisionType,
    TaskSubmissionProofRole,
    TaskSubmissionStatus,
    TaskInstanceStatus,
    TaskTemplateStatus,
    TaskType,
    TicketMessageSenderType,
    TicketStatus,
    TicketType,
    UserIdentityType,
    UserLifecycleStatus,
    UserTagSourceType,
)
from app.db.base import Base


def _nullable_text_dimension(column: Any) -> Any:
    return func.coalesce(column, text("'__NULL__'"))


def _nullable_int_dimension(column: Any) -> Any:
    return func.coalesce(column, text("-1"))


def _string_enum_check(column_name: str, allowed_values: tuple[str, ...], *, name: str) -> CheckConstraint:
    allowed_sql = ", ".join(f"'{value}'" for value in allowed_values)
    return CheckConstraint(f"{column_name} IN ({allowed_sql})", name=name)


_WABA_WEBHOOK_VERIFICATION_STATUSES = ("pending", "verified", "failed", "unavailable")
_WABA_WEBHOOK_RUNTIME_STATUSES = (
    "pending",
    "healthy",
    "verification_pending",
    "signature_failed",
    "signature_unavailable",
    "payload_invalid",
)
_META_BUSINESS_PORTFOLIO_STATUSES = ("active",)
_WEBHOOK_SUBSCRIPTION_STATUSES = (
    "pending",
    "mock_subscribed",
    "remote_subscribed",
    "remote_pending",
    "subscribed",
)
_EMBEDDED_SIGNUP_SESSION_STATUSES = ("created", "completed", "failed")
_EMBEDDED_SIGNUP_COMPLETION_STAGES = (
    "pending_callback",
    "callback_recorded",
    "remote_confirmed",
    "local_waba_linked",
    "webhook_verification_pending",
    "failed",
)
_EMBEDDED_SIGNUP_EVENT_SOURCES = ("operator", "provider_callback", "system_sync")


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def new_id() -> str:
    return str(uuid4())


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )


class MetaBusinessPortfolio(Base, TimestampMixin):
    __tablename__ = "meta_business_portfolios"
    __table_args__ = (
        _string_enum_check(
            "status",
            _META_BUSINESS_PORTFOLIO_STATUSES,
            name="status",
        ),
        UniqueConstraint("id", "account_id", name="uq_meta_business_portfolios_id_account"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(
        ForeignKey("accounts.account_id"),
        nullable=False,
        index=True,
    )
    meta_business_portfolio_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    display_name: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)

    account: Mapped["Account | None"] = relationship(back_populates="meta_business_portfolios")
    whatsapp_business_accounts: Mapped[list["WhatsAppBusinessAccount"]] = relationship(
        back_populates="portfolio",
        primaryjoin=lambda: and_(
            MetaBusinessPortfolio.id == foreign(WhatsAppBusinessAccount.portfolio_id),
            MetaBusinessPortfolio.account_id == foreign(WhatsAppBusinessAccount.account_id),
        ),
        foreign_keys=lambda: [
            WhatsAppBusinessAccount.portfolio_id,
            WhatsAppBusinessAccount.account_id,
        ],
        overlaps="account,whatsapp_business_accounts",
    )


class Account(Base, TimestampMixin):
    __tablename__ = "accounts"

    account_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_type: Mapped[str] = mapped_column(String(32), nullable=False, default="whatsapp")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    ai_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)

    meta_business_portfolios: Mapped[list["MetaBusinessPortfolio"]] = relationship(back_populates="account")
    whatsapp_business_accounts: Mapped[list["WhatsAppBusinessAccount"]] = relationship(
        back_populates="account",
        overlaps="portfolio,whatsapp_business_accounts",
    )
    embedded_signup_sessions: Mapped[list["EmbeddedSignupSession"]] = relationship(back_populates="account")
    conversations: Mapped[list["Conversation"]] = relationship(back_populates="account")
    messages: Mapped[list["Message"]] = relationship(back_populates="account")
    support_knowledge_entries: Mapped[list["SupportKnowledgeEntry"]] = relationship(back_populates="account")
    h5_sites: Mapped[list["H5Site"]] = relationship(back_populates="account")
    app_users: Mapped[list["AppUser"]] = relationship(back_populates="account")
    member_profiles: Mapped[list["MemberProfile"]] = relationship(back_populates="account")
    member_auth_sessions: Mapped[list["MemberAuthSession"]] = relationship(back_populates="account")
    member_verification_requests: Mapped[list["MemberVerificationRequest"]] = relationship(
        back_populates="account"
    )
    member_verification_documents: Mapped[list["MemberVerificationDocument"]] = relationship(
        back_populates="account"
    )
    member_notifications: Mapped[list["MemberNotification"]] = relationship(back_populates="account")
    promotion_task_templates: Mapped[list["PromotionTaskTemplate"]] = relationship()
    promotion_task_instances: Mapped[list["PromotionTaskInstance"]] = relationship()
    user_referrals: Mapped[list["UserReferral"]] = relationship()
    task_templates: Mapped[list["TaskTemplate"]] = relationship(back_populates="account")
    task_instances: Mapped[list["TaskInstance"]] = relationship(back_populates="account")
    task_proof_files: Mapped[list["TaskProofFile"]] = relationship(back_populates="account")
    task_submissions: Mapped[list["TaskSubmission"]] = relationship(back_populates="account")
    task_review_decisions: Mapped[list["TaskReviewDecision"]] = relationship(back_populates="account")
    tickets: Mapped[list["Ticket"]] = relationship(back_populates="account")
    ai_prompts: Mapped[list["AIPrompt"]] = relationship(back_populates="account")


class SystemSetting(Base, TimestampMixin):
    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class H5Site(Base, TimestampMixin):
    __tablename__ = "h5_sites"
    __table_args__ = (
        UniqueConstraint("id", "account_id", name="uq_h5_sites_id_account_scope"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False, index=True)
    site_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    domain: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    brand_name: Mapped[str] = mapped_column(String(255), nullable=False)
    logo_url: Mapped[str | None] = mapped_column(String(1024))
    favicon_url: Mapped[str | None] = mapped_column(String(1024))
    default_language: Mapped[str] = mapped_column(String(32), nullable=False, default="zh-CN")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=H5SiteStatus.ACTIVE.value)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    agency_id: Mapped[str | None] = mapped_column(ForeignKey("agencies.id"), index=True)

    # ── 站点注册与接待配置（spec 5.11） ──
    registration_entry_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    allow_invite_code_alias: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    allow_unattributed_waba_inbound: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    default_staff_entry_link_id: Mapped[str | None] = mapped_column(String(36))
    default_ai_agent_id: Mapped[str | None] = mapped_column(String(36), index=True)
    default_ai_entry_link_id: Mapped[str | None] = mapped_column(String(36))
    default_waba_id: Mapped[str | None] = mapped_column(String(128))
    default_phone_number_id: Mapped[str | None] = mapped_column(String(128))
    member_invite_inherits_human_owner: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    member_invite_inherits_ai: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    existing_member_link_override_policy: Mapped[str] = mapped_column(
        String(32), nullable=False, default="do_not_override"
    )
    # do_not_override / allow_manual_override / allow_new_link_override
    ai_failover_policy: Mapped[str] = mapped_column(
        String(48), nullable=False, default="temporary_then_auto_reassign"
    )
    # temporary_only / temporary_then_auto_reassign / immediate_reassign / handover_only
    ai_failover_threshold_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=30)

    account: Mapped["Account | None"] = relationship(back_populates="h5_sites", overlaps="users,task_instances,task_proof_files,task_submissions,tickets")
    users: Mapped[list["AppUser"]] = relationship(
        back_populates="registration_site",
        overlaps="account,app_users",
        primaryjoin=lambda: and_(
            H5Site.id == foreign(AppUser.registration_site_id),
            H5Site.account_id == foreign(AppUser.account_id),
        ),
        foreign_keys=lambda: [
            AppUser.registration_site_id,
            AppUser.account_id,
        ],
    )
    invite_codes: Mapped[list["InviteCode"]] = relationship(back_populates="site")
    task_instances: Mapped[list["TaskInstance"]] = relationship(
        back_populates="site",
        overlaps="account,task_instances,template,user",
        primaryjoin=lambda: and_(
            H5Site.id == foreign(TaskInstance.site_id),
            H5Site.account_id == foreign(TaskInstance.account_id),
        ),
        foreign_keys=lambda: [
            TaskInstance.site_id,
            TaskInstance.account_id,
        ],
    )
    task_proof_files: Mapped[list["TaskProofFile"]] = relationship(
        back_populates="site",
        overlaps="account,task_proof_files,task_instance,user",
        primaryjoin=lambda: and_(
            H5Site.id == foreign(TaskProofFile.site_id),
            H5Site.account_id == foreign(TaskProofFile.account_id),
        ),
        foreign_keys=lambda: [
            TaskProofFile.site_id,
            TaskProofFile.account_id,
        ],
    )
    task_submissions: Mapped[list["TaskSubmission"]] = relationship(
        back_populates="site",
        overlaps="account,task_submissions,task_instance,submitted_by_user",
        primaryjoin=lambda: and_(
            H5Site.id == foreign(TaskSubmission.site_id),
            H5Site.account_id == foreign(TaskSubmission.account_id),
        ),
        foreign_keys=lambda: [
            TaskSubmission.site_id,
            TaskSubmission.account_id,
        ],
    )
    tickets: Mapped[list["Ticket"]] = relationship(
        back_populates="site",
        overlaps="account,tickets,task_instance,submission,review_decision,user",
        primaryjoin=lambda: and_(
            H5Site.id == foreign(Ticket.site_id),
            H5Site.account_id == foreign(Ticket.account_id),
        ),
        foreign_keys=lambda: [
            Ticket.site_id,
            Ticket.account_id,
        ],
    )


class AppUser(Base, TimestampMixin):
    __tablename__ = "app_users"
    __table_args__ = (
        UniqueConstraint("id", "account_id", name="uq_app_users_id_account_scope"),
        ForeignKeyConstraint(
            ["registration_site_id", "account_id"],
            ["h5_sites.id", "h5_sites.account_id"],
            name="fk_app_users_registration_site_account_scope",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False, index=True)
    public_user_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    registration_site_id: Mapped[str | None] = mapped_column(String(36), index=True)
    display_name: Mapped[str | None] = mapped_column(String(255))
    country_code: Mapped[str | None] = mapped_column(String(8))
    language_code: Mapped[str] = mapped_column(String(32), nullable=False, default="zh-CN")
    is_anonymous: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    lifecycle_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=UserLifecycleStatus.ACTIVE.value,
    )
    has_phone: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    has_email: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    has_whatsapp: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_invited_user: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_new_user: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    restrict_task_claim: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    registration_invite_code: Mapped[str | None] = mapped_column(String(64), index=True)
    registration_ip: Mapped[str | None] = mapped_column(String(45))
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))

    account: Mapped["Account | None"] = relationship(back_populates="app_users", overlaps="users,registration_site")
    registration_site: Mapped["H5Site | None"] = relationship(
        back_populates="users",
        overlaps="account,app_users",
        primaryjoin=lambda: and_(
            foreign(AppUser.registration_site_id) == H5Site.id,
            foreign(AppUser.account_id) == H5Site.account_id,
        ),
        foreign_keys=lambda: [
            AppUser.registration_site_id,
            AppUser.account_id,
        ],
    )
    identities: Mapped[list["UserIdentity"]] = relationship(back_populates="user")
    tag_assignments: Mapped[list["UserTagAssignment"]] = relationship(back_populates="user")
    issued_invite_codes: Mapped[list["InviteCode"]] = relationship(back_populates="inviter_user")
    task_instances: Mapped[list["TaskInstance"]] = relationship(
        back_populates="user",
        overlaps="account,task_instances,template,site",
        primaryjoin=lambda: and_(
            AppUser.id == foreign(TaskInstance.user_id),
            AppUser.account_id == foreign(TaskInstance.account_id),
        ),
        foreign_keys=lambda: [
            TaskInstance.user_id,
            TaskInstance.account_id,
        ],
    )
    task_proof_files: Mapped[list["TaskProofFile"]] = relationship(
        back_populates="user",
        overlaps="account,task_proof_files,task_instance,site",
        primaryjoin=lambda: and_(
            AppUser.id == foreign(TaskProofFile.user_id),
            AppUser.account_id == foreign(TaskProofFile.account_id),
        ),
        foreign_keys=lambda: [
            TaskProofFile.user_id,
            TaskProofFile.account_id,
        ],
    )
    task_submissions: Mapped[list["TaskSubmission"]] = relationship(
        back_populates="submitted_by_user",
        overlaps="account,task_submissions,task_instance,site",
        primaryjoin=lambda: and_(
            AppUser.id == foreign(TaskSubmission.submitted_by_user_id),
            AppUser.account_id == foreign(TaskSubmission.account_id),
        ),
        foreign_keys=lambda: [
            TaskSubmission.submitted_by_user_id,
            TaskSubmission.account_id,
        ],
    )
    tickets: Mapped[list["Ticket"]] = relationship(
        back_populates="user",
        overlaps="account,tickets,task_instance,submission,review_decision,site",
        primaryjoin=lambda: and_(
            AppUser.id == foreign(Ticket.user_id),
            AppUser.account_id == foreign(Ticket.account_id),
        ),
        foreign_keys=lambda: [
            Ticket.user_id,
            Ticket.account_id,
        ],
    )
    member_profile: Mapped["MemberProfile | None"] = relationship(back_populates="user", uselist=False)


class MemberProfile(Base, TimestampMixin):
    __tablename__ = "member_profiles"
    __table_args__ = (
        UniqueConstraint("account_id", "user_id", name="uq_member_profiles_account_user"),
        UniqueConstraint("account_id", "member_no", name="uq_member_profiles_account_member_no"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), nullable=False, index=True)
    member_no: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    password_salt: Mapped[str] = mapped_column(String(64), nullable=False)
    password_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, default=utc_now)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))

    account: Mapped["Account | None"] = relationship(back_populates="member_profiles")
    user: Mapped["AppUser"] = relationship(back_populates="member_profile")
    auth_sessions: Mapped[list["MemberAuthSession"]] = relationship(back_populates="member_profile")
    verification_requests: Mapped[list["MemberVerificationRequest"]] = relationship(
        back_populates="member_profile"
    )

    # ── 归属快照：当前人力 / AI 归属 + 注册入口（spec 5.7） ──
    current_owner_agency_id: Mapped[str | None] = mapped_column(String(128))
    current_owner_staff_user_id: Mapped[str | None] = mapped_column(String(128), index=True)
    current_owner_agency_member_id: Mapped[str | None] = mapped_column(String(128))
    current_owner_assignment_id: Mapped[str | None] = mapped_column(String(36))
    owner_assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))

    current_ai_agent_id: Mapped[str | None] = mapped_column(String(36), index=True)
    current_ai_assignment_id: Mapped[str | None] = mapped_column(String(36))
    ai_assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))

    registration_entry_link_id: Mapped[str | None] = mapped_column(String(36), index=True)
    registration_ai_agent_id: Mapped[str | None] = mapped_column(String(36))
    registration_staff_user_id: Mapped[str | None] = mapped_column(String(128))
    registration_channel: Mapped[str | None] = mapped_column(String(32))
    registration_source_type: Mapped[str | None] = mapped_column(String(48))
    attribution_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="unattributed", index=True
    )
    # owned / unattributed / pending_resolution / owner_disabled / ai_disabled / no_ai_assignment


class MemberAuthSession(Base, TimestampMixin):
    __tablename__ = "member_auth_sessions"
    __table_args__ = (
        UniqueConstraint("session_token_hash", name="uq_member_auth_sessions_session_token_hash"),
        UniqueConstraint("refresh_token_hash", name="uq_member_auth_sessions_refresh_token_hash"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), nullable=False, index=True)
    member_profile_id: Mapped[str] = mapped_column(ForeignKey("member_profiles.id"), nullable=False, index=True)
    session_token_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    refresh_token_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    refresh_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    client_ip: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(1024))

    account: Mapped["Account | None"] = relationship(back_populates="member_auth_sessions")
    member_profile: Mapped["MemberProfile"] = relationship(back_populates="auth_sessions")


class MemberVerificationRequest(Base, TimestampMixin):
    __tablename__ = "member_verification_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False, index=True)
    member_profile_id: Mapped[str] = mapped_column(ForeignKey("member_profiles.id"), nullable=False, index=True)
    request_type: Mapped[str] = mapped_column(String(32), nullable=False, default="identity")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    notes: Mapped[str | None] = mapped_column(Text)
    review_note: Mapped[str | None] = mapped_column(Text)
    reviewer_actor_id: Mapped[str | None] = mapped_column(String(128))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))

    account: Mapped["Account | None"] = relationship(back_populates="member_verification_requests")
    member_profile: Mapped["MemberProfile"] = relationship(back_populates="verification_requests")
    documents: Mapped[list["MemberVerificationDocument"]] = relationship(
        back_populates="verification_request"
    )


class MemberVerificationDocument(Base, TimestampMixin):
    __tablename__ = "member_verification_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False, index=True)
    verification_request_id: Mapped[str] = mapped_column(
        ForeignKey("member_verification_requests.id"),
        nullable=False,
        index=True,
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(128))
    storage_key: Mapped[str | None] = mapped_column(String(512))
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    account: Mapped["Account | None"] = relationship(back_populates="member_verification_documents")
    verification_request: Mapped["MemberVerificationRequest"] = relationship(
        back_populates="documents"
    )


class MemberWhatsAppBindingRequest(Base, TimestampMixin):
    __tablename__ = "member_whatsapp_binding_requests"
    __table_args__ = (
        UniqueConstraint(
            "account_id",
            "member_profile_id",
            name="uq_member_whatsapp_binding_requests_account_member_profile",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), nullable=False, index=True)
    member_profile_id: Mapped[str] = mapped_column(ForeignKey("member_profiles.id"), nullable=False, index=True)
    site_id: Mapped[str | None] = mapped_column(ForeignKey("h5_sites.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    requested_phone_number: Mapped[str | None] = mapped_column(String(32))
    start_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    last_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    bound_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    last_error: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    user: Mapped["AppUser"] = relationship()
    member_profile: Mapped["MemberProfile"] = relationship()
    site: Mapped["H5Site | None"] = relationship()


class MemberNotification(Base, TimestampMixin):
    __tablename__ = "member_notifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), nullable=False, index=True)
    member_profile_id: Mapped[str] = mapped_column(ForeignKey("member_profiles.id"), nullable=False, index=True)
    site_id: Mapped[str | None] = mapped_column(ForeignKey("h5_sites.id"), index=True)
    category: Mapped[str] = mapped_column(String(32), nullable=False, default="system")
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body_text: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    reference_type: Mapped[str | None] = mapped_column(String(64))
    reference_id: Mapped[str | None] = mapped_column(String(36), index=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    account: Mapped["Account | None"] = relationship(back_populates="member_notifications")


class FragmentDefinition(Base, TimestampMixin):
    __tablename__ = "fragment_definitions"
    __table_args__ = (
        UniqueConstraint("account_id", "fragment_key", name="uq_fragment_definitions_account_key"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False, index=True)
    fragment_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    rarity: Mapped[str] = mapped_column(String(32), nullable=False, default="common")
    color: Mapped[str] = mapped_column(String(32), nullable=False, default="#1677ff")
    required_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    reward_name: Mapped[str] = mapped_column(String(255), nullable=False, default="Star Ring Gift Box")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class FragmentInventory(Base, TimestampMixin):
    __tablename__ = "fragment_inventory"
    __table_args__ = (
        UniqueConstraint(
            "account_id",
            "user_id",
            "fragment_definition_id",
            name="uq_fragment_inventory_account_user_definition",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), nullable=False, index=True)
    member_profile_id: Mapped[str] = mapped_column(ForeignKey("member_profiles.id"), nullable=False, index=True)
    fragment_definition_id: Mapped[str] = mapped_column(
        ForeignKey("fragment_definitions.id"),
        nullable=False,
        index=True,
    )
    owned_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class FragmentLedgerEntry(Base, TimestampMixin):
    __tablename__ = "fragment_ledger_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), nullable=False, index=True)
    member_profile_id: Mapped[str] = mapped_column(ForeignKey("member_profiles.id"), nullable=False, index=True)
    fragment_definition_id: Mapped[str] = mapped_column(
        ForeignKey("fragment_definitions.id"),
        nullable=False,
        index=True,
    )
    entry_type: Mapped[str] = mapped_column(String(32), nullable=False, default="drop")
    direction: Mapped[str] = mapped_column(String(16), nullable=False, default="credit")
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, default="checkin")
    source_id: Mapped[str | None] = mapped_column(String(36), index=True)
    note: Mapped[str | None] = mapped_column(String(1024))


class FragmentDropLog(Base, TimestampMixin):
    __tablename__ = "fragment_drop_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), nullable=False, index=True)
    member_profile_id: Mapped[str] = mapped_column(ForeignKey("member_profiles.id"), nullable=False, index=True)
    fragment_definition_id: Mapped[str] = mapped_column(
        ForeignKey("fragment_definitions.id"),
        nullable=False,
        index=True,
    )
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="checkin")
    fragment_ledger_entry_id: Mapped[str | None] = mapped_column(
        ForeignKey("fragment_ledger_entries.id"),
        index=True,
    )
    source_id: Mapped[str | None] = mapped_column(String(36), index=True)


class FragmentExchangeRequest(Base, TimestampMixin):
    __tablename__ = "fragment_exchange_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), nullable=False, index=True)
    member_profile_id: Mapped[str] = mapped_column(ForeignKey("member_profiles.id"), nullable=False, index=True)
    reward_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="submitted")
    mailing_request_id: Mapped[str | None] = mapped_column(String(36), index=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class MailingRequest(Base, TimestampMixin):
    __tablename__ = "mailing_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), nullable=False, index=True)
    member_profile_id: Mapped[str] = mapped_column(ForeignKey("member_profiles.id"), nullable=False, index=True)
    fragment_exchange_request_id: Mapped[str | None] = mapped_column(
        ForeignKey("fragment_exchange_requests.id"),
        index=True,
    )
    reward_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending_address")
    receiver: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(32), nullable=False)
    country: Mapped[str] = mapped_column(String(128), nullable=False)
    province: Mapped[str] = mapped_column(String(128), nullable=False)
    city: Mapped[str] = mapped_column(String(128), nullable=False)
    address_line: Mapped[str] = mapped_column(Text, nullable=False)
    tracking_no: Mapped[str | None] = mapped_column(String(128))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    packed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class TaskPackageTemplate(Base, TimestampMixin):
    __tablename__ = "task_package_templates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    package_type: Mapped[str] = mapped_column(String(32), nullable=False, default="rookie")
    reward_ratio: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False, default=Decimal("0"))
    completion_window_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=24)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    promotion_metric: Mapped[str | None] = mapped_column(String(64))
    promotion_target_value: Mapped[int | None] = mapped_column(Integer)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    items: Mapped[list["TaskPackageTemplateItem"]] = relationship(
        back_populates="template",
        order_by="TaskPackageTemplateItem.sort_order",
    )


class TaskPackageTemplateItem(Base, TimestampMixin):
    __tablename__ = "task_package_template_items"
    __table_args__ = (
        UniqueConstraint("template_id", "sort_order", name="uq_task_package_template_items_order"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False, index=True)
    template_id: Mapped[str] = mapped_column(
        ForeignKey("task_package_templates.id"),
        nullable=False,
        index=True,
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(1024))
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))
    currency: Mapped[str] = mapped_column(String(16), nullable=False, default="USD")
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    template: Mapped["TaskPackageTemplate"] = relationship(back_populates="items")


class TaskPackageInstance(Base, TimestampMixin):
    __tablename__ = "task_package_instances"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False, index=True)
    template_id: Mapped[str] = mapped_column(
        ForeignKey("task_package_templates.id"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), nullable=False, index=True)
    site_id: Mapped[str | None] = mapped_column(ForeignKey("h5_sites.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending_claim")
    reward_ratio_snapshot: Mapped[Decimal] = mapped_column(
        Numeric(12, 4),
        nullable=False,
        default=Decimal("0"),
    )
    dispatched_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, default=utc_now)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    task_balance_awarded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    completion_window_hours_snapshot: Mapped[int] = mapped_column(Integer, nullable=False, default=24)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    template: Mapped["TaskPackageTemplate"] = relationship()
    items: Mapped[list["TaskPackageInstanceItem"]] = relationship(
        back_populates="package_instance",
        order_by="TaskPackageInstanceItem.sort_order",
    )


class TaskPackageInstanceItem(Base, TimestampMixin):
    __tablename__ = "task_package_instance_items"
    __table_args__ = (
        UniqueConstraint("package_instance_id", "sort_order", name="uq_task_package_instance_items_order"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False, index=True)
    package_instance_id: Mapped[str] = mapped_column(
        ForeignKey("task_package_instances.id"),
        nullable=False,
        index=True,
    )
    template_item_id: Mapped[str] = mapped_column(
        ForeignKey("task_package_template_items.id"),
        nullable=False,
        index=True,
    )
    order_id: Mapped[str | None] = mapped_column(ForeignKey("member_orders.id"), index=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(1024))
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))
    currency: Mapped[str] = mapped_column(String(16), nullable=False, default="USD")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    package_instance: Mapped["TaskPackageInstance"] = relationship(back_populates="items")
    template_item: Mapped["TaskPackageTemplateItem"] = relationship()


class PromotionTaskTemplate(Base, TimestampMixin):
    __tablename__ = "promotion_task_templates"
    __table_args__ = (
        UniqueConstraint(
            "task_package_template_id",
            name="uq_promotion_task_templates_task_package_template_id",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False, index=True)
    task_package_template_id: Mapped[str] = mapped_column(
        ForeignKey("task_package_templates.id"),
        nullable=False,
        index=True,
    )
    metric: Mapped[str] = mapped_column(String(64), nullable=False)
    target_value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class PromotionTaskInstance(Base, TimestampMixin):
    __tablename__ = "promotion_task_instances"
    __table_args__ = (
        UniqueConstraint(
            "task_package_instance_id",
            name="uq_promotion_task_instances_task_package_instance_id",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False, index=True)
    promotion_task_template_id: Mapped[str] = mapped_column(
        ForeignKey("promotion_task_templates.id"),
        nullable=False,
        index=True,
    )
    task_package_instance_id: Mapped[str] = mapped_column(
        ForeignKey("task_package_instances.id"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), nullable=False, index=True)
    member_profile_id: Mapped[str] = mapped_column(ForeignKey("member_profiles.id"), nullable=False, index=True)
    metric: Mapped[str] = mapped_column(String(64), nullable=False)
    target_value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    invite_code_snapshot: Mapped[str | None] = mapped_column(String(64), index=True)
    current_value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    achieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    rewarded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class UserReferral(Base, TimestampMixin):
    __tablename__ = "user_referrals"
    __table_args__ = (
        UniqueConstraint(
            "account_id",
            "referrer_user_id",
            "referred_user_id",
            name="uq_user_referrals_account_referrer_referred",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False, index=True)
    site_id: Mapped[str | None] = mapped_column(ForeignKey("h5_sites.id"), index=True)
    invite_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    referrer_user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), nullable=False, index=True)
    referred_user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), nullable=False, index=True)
    referred_member_profile_id: Mapped[str | None] = mapped_column(
        ForeignKey("member_profiles.id"),
        index=True,
    )
    registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, default=utc_now)
    first_recharged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    first_recharge_order_id: Mapped[str | None] = mapped_column(String(36), index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="registered")
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class WalletAccount(Base, TimestampMixin):
    __tablename__ = "wallet_accounts"
    __table_args__ = (
        UniqueConstraint("account_id", "user_id", name="uq_wallet_accounts_account_user"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), nullable=False, index=True)
    system_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))
    system_cash_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))
    system_bonus_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))
    frozen_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))
    system_cash_frozen: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))
    system_bonus_frozen: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))
    task_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))
    currency: Mapped[str] = mapped_column(String(16), nullable=False, default="USD")
    withdraw_threshold: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("100"),
    )


class WalletLedgerEntry(Base, TimestampMixin):
    __tablename__ = "wallet_ledger_entries"
    __table_args__ = (
        UniqueConstraint(
            "account_id",
            "wallet_account_id",
            "user_id",
            "ledger_type",
            "transaction_type",
            "direction",
            "reference_type",
            "reference_id",
            name="uq_wallet_ledger_entries_reference_scope",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False, index=True)
    wallet_account_id: Mapped[str] = mapped_column(
        ForeignKey("wallet_accounts.id"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), nullable=False, index=True)
    ledger_type: Mapped[str] = mapped_column(String(32), nullable=False)
    transaction_type: Mapped[str] = mapped_column(String(64), nullable=False)
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))
    currency: Mapped[str] = mapped_column(String(16), nullable=False, default="USD")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="paid")
    source_type: Mapped[str | None] = mapped_column(String(64), index=True)
    fund_type: Mapped[str | None] = mapped_column(String(32), index=True)
    cash_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))
    bonus_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))
    task_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))
    balance_before: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    balance_after: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    cash_balance_before: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    cash_balance_after: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    bonus_balance_before: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    bonus_balance_after: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    task_balance_before: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    task_balance_after: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    operator_id: Mapped[str | None] = mapped_column(String(64), index=True)
    operator_type: Mapped[str | None] = mapped_column(String(32))
    idempotency_key: Mapped[str | None] = mapped_column(String(128), index=True)
    display_category: Mapped[str | None] = mapped_column(String(64))
    display_title: Mapped[str | None] = mapped_column(String(128))
    is_bonus: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_real_recharge: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    note: Mapped[str | None] = mapped_column(String(1024))
    reference_type: Mapped[str | None] = mapped_column(String(64))
    reference_id: Mapped[str | None] = mapped_column(String(36), index=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class WalletTransferRequest(Base, TimestampMixin):
    __tablename__ = "wallet_transfer_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False, index=True)
    wallet_account_id: Mapped[str] = mapped_column(
        ForeignKey("wallet_accounts.id"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))
    currency: Mapped[str] = mapped_column(String(16), nullable=False, default="USD")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="paid")


class WalletRechargeOrder(Base, TimestampMixin):
    __tablename__ = "wallet_recharge_orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False, index=True)
    wallet_account_id: Mapped[str] = mapped_column(
        ForeignKey("wallet_accounts.id"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))
    currency: Mapped[str] = mapped_column(String(16), nullable=False, default="USD")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="paid")
    credited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))


class WithdrawalRequest(Base, TimestampMixin):
    __tablename__ = "withdrawal_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False, index=True)
    wallet_account_id: Mapped[str] = mapped_column(
        ForeignKey("wallet_accounts.id"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), nullable=False, index=True)
    member_profile_id: Mapped[str | None] = mapped_column(ForeignKey("member_profiles.id"), index=True)
    request_no: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))
    cash_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))
    bonus_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))
    actual_payout_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    withdraw_account_type: Mapped[str | None] = mapped_column(String(32))
    bank_name: Mapped[str | None] = mapped_column(String(128))
    account_no_masked: Mapped[str | None] = mapped_column(String(128))
    account_fingerprint: Mapped[str | None] = mapped_column(String(128), index=True)
    account_snapshot_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    duplicate_account_count: Mapped[int] = mapped_column(nullable=False, default=0)
    risk_level: Mapped[str | None] = mapped_column(String(32))
    risk_flags: Mapped[list[str] | None] = mapped_column(JSON)
    currency: Mapped[str] = mapped_column(String(16), nullable=False, default="USD")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="submitted")
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class WithdrawalAuditLog(Base):
    __tablename__ = "withdrawal_audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False, index=True)
    withdrawal_request_id: Mapped[str] = mapped_column(
        ForeignKey("withdrawal_requests.id"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    actor_type: Mapped[str] = mapped_column(String(32), nullable=False, default="system")
    actor_id: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, nullable=False)


class WalletBonusGrantRecord(Base, TimestampMixin):
    __tablename__ = "wallet_bonus_grant_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False, index=True)
    grant_no: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))
    currency: Mapped[str] = mapped_column(String(16), nullable=False, default="USD")
    source_type: Mapped[str] = mapped_column(String(64), nullable=False, default="admin_bonus")
    reason: Mapped[str] = mapped_column(String(128), nullable=False)
    remark: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    operator_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    approved_by: Mapped[str | None] = mapped_column(String(64), index=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    credited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    ledger_id: Mapped[str | None] = mapped_column(String(36), index=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class RechargeRepairOrder(Base, TimestampMixin):
    __tablename__ = "recharge_repair_orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False, index=True)
    repair_no: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), nullable=False, index=True)
    channel_id: Mapped[str | None] = mapped_column(String(36), index=True)
    platform_order_no: Mapped[str | None] = mapped_column(String(128), index=True)
    channel_order_no: Mapped[str | None] = mapped_column(String(128), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))
    currency: Mapped[str] = mapped_column(String(16), nullable=False, default="USD")
    repair_type: Mapped[str] = mapped_column(String(64), nullable=False, default="callback_missing")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    reason: Mapped[str] = mapped_column(String(256), nullable=False)
    remark: Mapped[str | None] = mapped_column(Text)
    operator_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    approved_by: Mapped[str | None] = mapped_column(String(64), index=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    credited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    recharge_record_id: Mapped[str | None] = mapped_column(String(36), index=True)
    ledger_id: Mapped[str | None] = mapped_column(String(36), index=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class MemberOrder(Base, TimestampMixin):
    __tablename__ = "member_orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), nullable=False, index=True)
    package_instance_id: Mapped[str | None] = mapped_column(
        ForeignKey("task_package_instances.id"),
        index=True,
    )
    order_no: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    package_title: Mapped[str | None] = mapped_column(String(255))
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))
    currency: Mapped[str] = mapped_column(String(16), nullable=False, default="USD")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="paid")
    source_label: Mapped[str | None] = mapped_column(String(255))
    ordered_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, default=utc_now)


class UserIdentity(Base, TimestampMixin):
    __tablename__ = "user_identities"
    __table_args__ = (
        UniqueConstraint("identity_type", "identity_value", name="uq_user_identities_value"),
        UniqueConstraint("user_id", "identity_type", "identity_value", name="uq_user_identities_user_value"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), nullable=False, index=True)
    identity_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=UserIdentityType.ANONYMOUS.value,
    )
    identity_value: Mapped[str] = mapped_column(String(255), nullable=False)
    country_code: Mapped[str | None] = mapped_column(String(8))
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    user: Mapped["AppUser"] = relationship(back_populates="identities")


class InviteCode(Base, TimestampMixin):
    __tablename__ = "invite_codes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    site_id: Mapped[str | None] = mapped_column(ForeignKey("h5_sites.id"), index=True)
    inviter_user_id: Mapped[str | None] = mapped_column(ForeignKey("app_users.id"), index=True)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=InviteCodeStatus.ACTIVE.value,
    )
    usage_limit: Mapped[int | None] = mapped_column(Integer)
    usage_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    site: Mapped["H5Site | None"] = relationship(back_populates="invite_codes")
    inviter_user: Mapped["AppUser | None"] = relationship(back_populates="issued_invite_codes")


class UserTag(Base, TimestampMixin):
    __tablename__ = "user_tags"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tag_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    color: Mapped[str | None] = mapped_column(String(32))
    source_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=UserTagSourceType.MANUAL.value,
    )
    rule_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[str | None] = mapped_column(String(128))

    assignments: Mapped[list["UserTagAssignment"]] = relationship(back_populates="tag")


class UserTagAssignment(Base):
    __tablename__ = "user_tag_assignments"
    __table_args__ = (
        UniqueConstraint("user_id", "tag_id", name="uq_user_tag_assignments_scope"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), nullable=False, index=True)
    tag_id: Mapped[str] = mapped_column(ForeignKey("user_tags.id"), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=UserTagSourceType.MANUAL.value,
    )
    source_rule_key: Mapped[str | None] = mapped_column(String(64))
    assigned_by: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, nullable=False)

    user: Mapped["AppUser"] = relationship(back_populates="tag_assignments")
    tag: Mapped["UserTag"] = relationship(back_populates="assignments")


class AudienceRuleSet(Base, TimestampMixin):
    __tablename__ = "audience_rule_sets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    rule_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    scope_type: Mapped[str] = mapped_column(String(64), nullable=False, default="task_template")
    scope_id: Mapped[str | None] = mapped_column(String(128), index=True)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=AudienceRuleStatus.DRAFT.value,
    )
    description: Mapped[str | None] = mapped_column(Text)
    rules_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_by: Mapped[str | None] = mapped_column(String(128))
    updated_by: Mapped[str | None] = mapped_column(String(128))


class TaskTemplate(Base, TimestampMixin):
    __tablename__ = "task_templates"
    __table_args__ = (
        UniqueConstraint("id", "account_id", name="uq_task_templates_id_account_scope"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False, index=True)
    task_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    task_type: Mapped[str] = mapped_column(String(32), nullable=False, default=TaskType.SHOPPING.value)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=TaskTemplateStatus.DRAFT.value,
    )
    audience_rule_set_id: Mapped[str | None] = mapped_column(ForeignKey("audience_rule_sets.id"), index=True)
    reward_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    reward_points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    claim_timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=86400)
    auto_review_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    account: Mapped["Account | None"] = relationship(back_populates="task_templates", overlaps="task_instances")
    task_instances: Mapped[list["TaskInstance"]] = relationship(
        back_populates="template",
        overlaps="account,task_instances,user,site",
        primaryjoin=lambda: and_(
            TaskTemplate.id == foreign(TaskInstance.template_id),
            TaskTemplate.account_id == foreign(TaskInstance.account_id),
        ),
        foreign_keys=lambda: [
            TaskInstance.template_id,
            TaskInstance.account_id,
        ],
    )


class TaskInstance(Base, TimestampMixin):
    __tablename__ = "task_instances"
    __table_args__ = (
        UniqueConstraint("id", "account_id", name="uq_task_instances_id_account_scope"),
        ForeignKeyConstraint(
            ["template_id", "account_id"],
            ["task_templates.id", "task_templates.account_id"],
            name="fk_task_instances_template_account_scope",
        ),
        ForeignKeyConstraint(
            ["user_id", "account_id"],
            ["app_users.id", "app_users.account_id"],
            name="fk_task_instances_user_account_scope",
        ),
        ForeignKeyConstraint(
            ["site_id", "account_id"],
            ["h5_sites.id", "h5_sites.account_id"],
            name="fk_task_instances_site_account_scope",
        ),
        _string_enum_check(
            "status",
            (
                TaskInstanceStatus.AVAILABLE.value,
                TaskInstanceStatus.CLAIMED.value,
                TaskInstanceStatus.SUBMITTED.value,
                TaskInstanceStatus.UNDER_REVIEW.value,
                TaskInstanceStatus.CHANGES_REQUESTED.value,
                TaskInstanceStatus.APPROVED.value,
                TaskInstanceStatus.REJECTED.value,
                TaskInstanceStatus.APPEALING.value,
                TaskInstanceStatus.COMPLETED.value,
                TaskInstanceStatus.EXPIRED.value,
                TaskInstanceStatus.ABANDONED.value,
                TaskInstanceStatus.CANCELLED.value,
            ),
            name="ck_task_instances_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False, index=True)
    template_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    site_id: Mapped[str | None] = mapped_column(String(36), index=True)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=TaskInstanceStatus.AVAILABLE.value,
    )
    claim_timeout_seconds_snapshot: Mapped[int] = mapped_column(Integer, nullable=False, default=86400)
    review_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, nullable=False)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    claim_deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    expired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    account: Mapped["Account | None"] = relationship(back_populates="task_instances", overlaps="task_instances,template,user,site")
    template: Mapped["TaskTemplate"] = relationship(
        back_populates="task_instances",
        overlaps="account,task_instances,user,site",
        primaryjoin=lambda: and_(
            foreign(TaskInstance.template_id) == TaskTemplate.id,
            foreign(TaskInstance.account_id) == TaskTemplate.account_id,
        ),
        foreign_keys=lambda: [
            TaskInstance.template_id,
            TaskInstance.account_id,
        ],
    )
    user: Mapped["AppUser"] = relationship(
        back_populates="task_instances",
        overlaps="account,task_instances,template,site",
        primaryjoin=lambda: and_(
            foreign(TaskInstance.user_id) == AppUser.id,
            foreign(TaskInstance.account_id) == AppUser.account_id,
        ),
        foreign_keys=lambda: [
            TaskInstance.user_id,
            TaskInstance.account_id,
        ],
    )
    site: Mapped["H5Site | None"] = relationship(
        back_populates="task_instances",
        overlaps="account,task_instances,template,user",
        primaryjoin=lambda: and_(
            foreign(TaskInstance.site_id) == H5Site.id,
            foreign(TaskInstance.account_id) == H5Site.account_id,
        ),
        foreign_keys=lambda: [
            TaskInstance.site_id,
            TaskInstance.account_id,
        ],
    )
    proof_files: Mapped[list["TaskProofFile"]] = relationship(
        back_populates="task_instance",
        overlaps="account,task_proof_files",
    )
    submissions: Mapped[list["TaskSubmission"]] = relationship(
        back_populates="task_instance",
        overlaps="account,task_submissions",
    )
    review_decisions: Mapped[list["TaskReviewDecision"]] = relationship(
        back_populates="task_instance",
        overlaps="account,task_review_decisions",
    )
    tickets: Mapped[list["Ticket"]] = relationship(
        back_populates="task_instance",
        overlaps="account,tickets,user,site",
    )


class TaskProofFile(Base, TimestampMixin):
    __tablename__ = "task_proof_files"
    __table_args__ = (
        UniqueConstraint(
            "id",
            "task_instance_id",
            "account_id",
            name="uq_task_proof_files_id_task_instance_account_scope",
        ),
        ForeignKeyConstraint(
            ["task_instance_id", "account_id"],
            ["task_instances.id", "task_instances.account_id"],
            name="fk_task_proof_files_task_instance_account_scope",
        ),
        ForeignKeyConstraint(
            ["user_id", "account_id"],
            ["app_users.id", "app_users.account_id"],
            name="fk_task_proof_files_user_account_scope",
        ),
        ForeignKeyConstraint(
            ["site_id", "account_id"],
            ["h5_sites.id", "h5_sites.account_id"],
            name="fk_task_proof_files_site_account_scope",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False, index=True)
    task_instance_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    site_id: Mapped[str | None] = mapped_column(String(36), index=True)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=TaskProofFileStatus.UPLOADED.value,
    )
    storage_provider: Mapped[str] = mapped_column(String(32), nullable=False, default="local")
    object_key: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    uploaded_by_type: Mapped[str] = mapped_column(String(32), nullable=False, default="user")
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    account: Mapped["Account | None"] = relationship(
        back_populates="task_proof_files",
        overlaps="proof_files,task_instance,user,site,task_proof_files",
    )
    task_instance: Mapped["TaskInstance"] = relationship(
        back_populates="proof_files",
        overlaps="account,task_proof_files,user,site",
    )
    user: Mapped["AppUser"] = relationship(
        back_populates="task_proof_files",
        overlaps="account,proof_files,task_instance,task_proof_files,site",
        primaryjoin=lambda: and_(
            foreign(TaskProofFile.user_id) == AppUser.id,
            foreign(TaskProofFile.account_id) == AppUser.account_id,
        ),
        foreign_keys=lambda: [
            TaskProofFile.user_id,
            TaskProofFile.account_id,
        ],
    )
    site: Mapped["H5Site | None"] = relationship(
        back_populates="task_proof_files",
        overlaps="account,proof_files,task_instance,task_proof_files,user",
        primaryjoin=lambda: and_(
            foreign(TaskProofFile.site_id) == H5Site.id,
            foreign(TaskProofFile.account_id) == H5Site.account_id,
        ),
        foreign_keys=lambda: [
            TaskProofFile.site_id,
            TaskProofFile.account_id,
        ],
    )
    submission_links: Mapped[list["TaskSubmissionProof"]] = relationship(
        back_populates="proof_file",
        overlaps="proofs,submission",
    )


class TaskSubmission(Base, TimestampMixin):
    __tablename__ = "task_submissions"
    __table_args__ = (
        UniqueConstraint("id", "task_instance_id", "account_id", name="uq_task_submissions_id_instance_account_scope"),
        ForeignKeyConstraint(
            ["task_instance_id", "account_id"],
            ["task_instances.id", "task_instances.account_id"],
            name="fk_task_submissions_task_instance_account_scope",
        ),
        ForeignKeyConstraint(
            ["submitted_by_user_id", "account_id"],
            ["app_users.id", "app_users.account_id"],
            name="fk_task_submissions_submitted_by_user_account_scope",
        ),
        ForeignKeyConstraint(
            ["site_id", "account_id"],
            ["h5_sites.id", "h5_sites.account_id"],
            name="fk_task_submissions_site_account_scope",
        ),
        _string_enum_check(
            "status",
            (
                TaskSubmissionStatus.DRAFT.value,
                TaskSubmissionStatus.SUBMITTED.value,
                TaskSubmissionStatus.UNDER_REVIEW.value,
                TaskSubmissionStatus.CHANGES_REQUESTED.value,
                TaskSubmissionStatus.APPROVED.value,
                TaskSubmissionStatus.REJECTED.value,
                TaskSubmissionStatus.WITHDRAWN.value,
            ),
            name="ck_task_submissions_status",
        ),
        UniqueConstraint("task_instance_id", "submission_no", name="uq_task_submissions_instance_attempt"),
        Index(
            "uq_task_submissions_active_per_task_instance",
            "task_instance_id",
            unique=True,
            sqlite_where=text("status IN ('submitted', 'under_review', 'rejected')"),
            postgresql_where=text("status IN ('submitted', 'under_review', 'rejected')"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False, index=True)
    task_instance_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    submitted_by_user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    site_id: Mapped[str | None] = mapped_column(String(36), index=True)
    submission_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=TaskSubmissionStatus.SUBMITTED.value,
    )
    source_channel: Mapped[str] = mapped_column(String(32), nullable=False, default="h5")
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, nullable=False)
    review_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    review_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    review_required_snapshot: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    account: Mapped["Account"] = relationship(
        back_populates="task_submissions",
        overlaps="submissions,task_instance,submitted_by_user,site,task_submissions",
    )
    task_instance: Mapped["TaskInstance"] = relationship(
        back_populates="submissions",
        overlaps="account,task_submissions,submitted_by_user,site",
    )
    submitted_by_user: Mapped["AppUser"] = relationship(
        back_populates="task_submissions",
        overlaps="account,submissions,task_instance,task_submissions,site",
        primaryjoin=lambda: and_(
            foreign(TaskSubmission.submitted_by_user_id) == AppUser.id,
            foreign(TaskSubmission.account_id) == AppUser.account_id,
        ),
        foreign_keys=lambda: [
            TaskSubmission.submitted_by_user_id,
            TaskSubmission.account_id,
        ],
    )
    site: Mapped["H5Site | None"] = relationship(
        back_populates="task_submissions",
        overlaps="account,submissions,submitted_by_user,task_instance,task_submissions",
        primaryjoin=lambda: and_(
            foreign(TaskSubmission.site_id) == H5Site.id,
            foreign(TaskSubmission.account_id) == H5Site.account_id,
        ),
        foreign_keys=lambda: [
            TaskSubmission.site_id,
            TaskSubmission.account_id,
        ],
    )
    proofs: Mapped[list["TaskSubmissionProof"]] = relationship(
        back_populates="submission",
        overlaps="proof_file,submission_links",
    )
    review_decisions: Mapped[list["TaskReviewDecision"]] = relationship(
        back_populates="submission",
        overlaps="account,review_decisions,task_instance,task_review_decisions",
    )
    tickets: Mapped[list["Ticket"]] = relationship(
        back_populates="submission",
        overlaps="account,review_decision,task_instance,tickets",
    )


class TaskSubmissionProof(Base):
    __tablename__ = "task_submission_proofs"
    __table_args__ = (
        UniqueConstraint("submission_id", "proof_file_id", name="uq_task_submission_proofs_scope"),
        ForeignKeyConstraint(
            ["submission_id", "task_instance_id", "account_id"],
            ["task_submissions.id", "task_submissions.task_instance_id", "task_submissions.account_id"],
            name="fk_task_submission_proofs_submission_account_scope",
        ),
        ForeignKeyConstraint(
            ["proof_file_id", "task_instance_id", "account_id"],
            ["task_proof_files.id", "task_proof_files.task_instance_id", "task_proof_files.account_id"],
            name="fk_task_submission_proofs_proof_file_account_scope",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False, index=True)
    task_instance_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    submission_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    proof_file_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    proof_role: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=TaskSubmissionProofRole.EVIDENCE.value,
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, nullable=False)

    submission: Mapped["TaskSubmission"] = relationship(
        back_populates="proofs",
        overlaps="proof_file,submission_links",
    )
    proof_file: Mapped["TaskProofFile"] = relationship(
        back_populates="submission_links",
        overlaps="proofs,submission",
    )


class TaskReviewDecision(Base):
    __tablename__ = "task_review_decisions"
    __table_args__ = (
        UniqueConstraint(
            "id",
            "task_instance_id",
            "submission_id",
            "account_id",
            name="uq_task_review_decisions_id_submission_account_scope",
        ),
        ForeignKeyConstraint(
            ["submission_id", "task_instance_id", "account_id"],
            ["task_submissions.id", "task_submissions.task_instance_id", "task_submissions.account_id"],
            name="fk_task_review_decisions_submission_account_scope",
        ),
        ForeignKeyConstraint(
            ["task_instance_id", "account_id"],
            ["task_instances.id", "task_instances.account_id"],
            name="fk_task_review_decisions_task_instance_account_scope",
        ),
        _string_enum_check(
            "decision",
            (
                TaskReviewDecisionType.PENDING.value,
                TaskReviewDecisionType.APPROVED.value,
                TaskReviewDecisionType.REJECTED.value,
                TaskReviewDecisionType.CHANGES_REQUESTED.value,
                TaskReviewDecisionType.ESCALATED.value,
            ),
            name="ck_task_review_decisions_decision",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False, index=True)
    task_instance_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    submission_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    decision: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=TaskReviewDecisionType.PENDING.value,
    )
    decision_source: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=TaskReviewDecisionSource.MANUAL.value,
    )
    reviewer_actor_id: Mapped[str | None] = mapped_column(String(128), index=True)
    reason_code: Mapped[str | None] = mapped_column(String(64))
    reason_text: Mapped[str | None] = mapped_column(Text)
    evidence_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, nullable=False)

    account: Mapped["Account"] = relationship(
        back_populates="task_review_decisions",
        overlaps="review_decisions,submission,task_instance,task_review_decisions",
    )
    task_instance: Mapped["TaskInstance"] = relationship(
        back_populates="review_decisions",
        overlaps="account,task_review_decisions",
        primaryjoin=lambda: and_(
            foreign(TaskReviewDecision.task_instance_id) == TaskInstance.id,
            foreign(TaskReviewDecision.account_id) == TaskInstance.account_id,
        ),
        foreign_keys=lambda: [
            TaskReviewDecision.task_instance_id,
            TaskReviewDecision.account_id,
        ],
    )
    submission: Mapped["TaskSubmission"] = relationship(
        back_populates="review_decisions",
        overlaps="account,review_decisions,task_instance,task_review_decisions",
    )
    tickets: Mapped[list["Ticket"]] = relationship(
        back_populates="review_decision",
        overlaps="account,submission,task_instance,tickets",
    )


class Ticket(Base, TimestampMixin):
    __tablename__ = "tickets"
    __table_args__ = (
        _string_enum_check(
            "ticket_type",
            (
                TicketType.SUBMISSION_REVIEW.value,
                TicketType.APPEAL.value,
                TicketType.HELP.value,
                TicketType.COMPLAINT.value,
                TicketType.MANUAL_SERVICE.value,
            ),
            name="ck_tickets_ticket_type",
        ),
        CheckConstraint(
            "status IN ('open', 'in_progress', 'waiting_user', 'pending_user', 'resolved', 'rejected', 'closed', 'cancelled')",
            name="ck_tickets_status",
        ),
        CheckConstraint(
            "linked_submission_id IS NULL OR linked_task_instance_id IS NOT NULL",
            name="ck_tickets_linked_submission_requires_task",
        ),
        CheckConstraint(
            "review_decision_id IS NULL OR (linked_submission_id IS NOT NULL AND linked_task_instance_id IS NOT NULL)",
            name="ck_tickets_review_decision_requires_submission",
        ),
        CheckConstraint(
            "ticket_type != 'appeal' OR (linked_task_instance_id IS NOT NULL AND linked_submission_id IS NOT NULL AND review_decision_id IS NOT NULL)",
            name="ck_tickets_appeal_requires_review_chain",
        ),
        ForeignKeyConstraint(
            ["linked_submission_id", "linked_task_instance_id", "account_id"],
            ["task_submissions.id", "task_submissions.task_instance_id", "task_submissions.account_id"],
            name="fk_tickets_submission_account_scope",
        ),
        ForeignKeyConstraint(
            ["review_decision_id", "linked_task_instance_id", "linked_submission_id", "account_id"],
            [
                "task_review_decisions.id",
                "task_review_decisions.task_instance_id",
                "task_review_decisions.submission_id",
                "task_review_decisions.account_id",
            ],
            name="fk_tickets_review_decision_account_scope",
        ),
        ForeignKeyConstraint(
            ["linked_task_instance_id", "account_id"],
            ["task_instances.id", "task_instances.account_id"],
            name="fk_tickets_task_instance_account_scope",
        ),
        ForeignKeyConstraint(
            ["user_id", "account_id"],
            ["app_users.id", "app_users.account_id"],
            name="fk_tickets_user_account_scope",
        ),
        ForeignKeyConstraint(
            ["site_id", "account_id"],
            ["h5_sites.id", "h5_sites.account_id"],
            name="fk_tickets_site_account_scope",
        ),
        Index(
            "uq_tickets_active_appeal_per_task_instance",
            "linked_task_instance_id",
            unique=True,
            sqlite_where=text("ticket_type = 'appeal' AND is_active = 1"),
            postgresql_where=text("ticket_type = 'appeal' AND is_active = true"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False, index=True)
    ticket_no: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    linked_task_instance_id: Mapped[str | None] = mapped_column(String(36), index=True)
    linked_submission_id: Mapped[str | None] = mapped_column(String(36), index=True)
    review_decision_id: Mapped[str | None] = mapped_column(String(36), index=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    site_id: Mapped[str | None] = mapped_column(String(36), index=True)
    ticket_type: Mapped[str] = mapped_column(String(32), nullable=False, default=TicketType.APPEAL.value)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=TicketStatus.OPEN.value)
    priority: Mapped[str] = mapped_column(String(32), nullable=False, default="normal")
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    latest_reply_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    site_key: Mapped[str | None] = mapped_column(String(50))

    account: Mapped["Account"] = relationship(
        back_populates="tickets",
        overlaps="review_decision,submission,tickets,task_instance,user,site",
    )
    task_instance: Mapped["TaskInstance | None"] = relationship(
        back_populates="tickets",
        overlaps="account,tickets,user,site",
        primaryjoin=lambda: and_(
            foreign(Ticket.linked_task_instance_id) == TaskInstance.id,
            foreign(Ticket.account_id) == TaskInstance.account_id,
        ),
        foreign_keys=lambda: [
            Ticket.linked_task_instance_id,
            Ticket.account_id,
        ],
    )
    submission: Mapped["TaskSubmission | None"] = relationship(
        back_populates="tickets",
        overlaps="account,review_decision,task_instance,tickets",
    )
    review_decision: Mapped["TaskReviewDecision | None"] = relationship(
        back_populates="tickets",
        overlaps="account,submission,task_instance,tickets",
    )
    user: Mapped["AppUser"] = relationship(
        back_populates="tickets",
        overlaps="account,review_decision,submission,task_instance,tickets,site",
        primaryjoin=lambda: and_(
            foreign(Ticket.user_id) == AppUser.id,
            foreign(Ticket.account_id) == AppUser.account_id,
        ),
        foreign_keys=lambda: [
            Ticket.user_id,
            Ticket.account_id,
        ],
    )
    site: Mapped["H5Site | None"] = relationship(
        back_populates="tickets",
        overlaps="account,review_decision,submission,task_instance,tickets,user",
        primaryjoin=lambda: and_(
            foreign(Ticket.site_id) == H5Site.id,
            foreign(Ticket.account_id) == H5Site.account_id,
        ),
        foreign_keys=lambda: [
            Ticket.site_id,
            Ticket.account_id,
        ],
    )
    messages: Mapped[list["TicketMessage"]] = relationship(back_populates="ticket")


class TicketMessage(Base):
    __tablename__ = "ticket_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("tickets.id"), nullable=False, index=True)
    sender_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=TicketMessageSenderType.USER.value,
    )
    sender_id: Mapped[str | None] = mapped_column(String(128), index=True)
    body_text: Mapped[str | None] = mapped_column(Text)
    attachments_json: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)
    is_internal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, nullable=False)

    ticket: Mapped["Ticket"] = relationship(back_populates="messages")


class SupportKnowledgeEntry(Base, TimestampMixin):
    __tablename__ = "support_knowledge_entries"
    __table_args__ = (
        UniqueConstraint("account_id", "article_id", name="uq_support_knowledge_entries_account_article"),
        UniqueConstraint("account_id", "route_name", name="uq_support_knowledge_entries_account_route"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False, index=True)
    article_id: Mapped[str] = mapped_column(String(128), nullable=False)
    route_name: Mapped[str] = mapped_column(String(128), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    answer_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_language: Mapped[str] = mapped_column(String(32), nullable=False, default="en")
    keywords_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    minimum_score: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    agency_id: Mapped[str | None] = mapped_column(ForeignKey("agencies.id"), index=True)

    account: Mapped["Account"] = relationship(back_populates="support_knowledge_entries")


class AIPrompt(Base, TimestampMixin):
    __tablename__ = "ai_prompts"
    __table_args__ = (
        UniqueConstraint("name", "account_id", "language", name="uq_ai_prompts_name_account_language"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    account_id: Mapped[str | None] = mapped_column(ForeignKey("accounts.account_id"), nullable=True, index=True)
    language: Mapped[str] = mapped_column(String(16), nullable=False, default="en")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    account: Mapped["Account | None"] = relationship(back_populates="ai_prompts")


class WhatsAppBusinessAccount(Base, TimestampMixin):
    __tablename__ = "whatsapp_business_accounts"
    __table_args__ = (
        _string_enum_check(
            "webhook_verification_status",
            _WABA_WEBHOOK_VERIFICATION_STATUSES,
            name="webhook_verification_status",
        ),
        _string_enum_check(
            "webhook_runtime_status",
            _WABA_WEBHOOK_RUNTIME_STATUSES,
            name="webhook_runtime_status",
        ),
        UniqueConstraint("account_id", "waba_id", name="uq_whatsapp_business_accounts_account_waba"),
        UniqueConstraint("id", "account_id", name="uq_whatsapp_business_accounts_id_account"),
        ForeignKeyConstraint(
            ["portfolio_id", "account_id"],
            ["meta_business_portfolios.id", "meta_business_portfolios.account_id"],
            name="fk_whatsapp_business_accounts_portfolio_account_scope",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False, index=True)
    portfolio_id: Mapped[str | None] = mapped_column(ForeignKey("meta_business_portfolios.id"))
    waba_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    onboarding_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    token_source: Mapped[str] = mapped_column(String(32), nullable=False)
    access_token: Mapped[str | None] = mapped_column(Text)
    verify_token: Mapped[str | None] = mapped_column(String(255))
    app_secret: Mapped[str | None] = mapped_column(String(255))
    webhook_subscribed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    webhook_verification_status: Mapped[str] = mapped_column(
        String(32),
        default="pending",
        nullable=False,
    )
    webhook_last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    webhook_last_verification_error: Mapped[str | None] = mapped_column(Text)
    webhook_runtime_status: Mapped[str] = mapped_column(
        String(32),
        default="pending",
        nullable=False,
    )
    webhook_last_event_received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    webhook_last_message_received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    webhook_last_status_update_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    webhook_last_management_event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    webhook_last_signature_failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    webhook_signature_failure_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    webhook_runtime_error: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    ai_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    agency_id: Mapped[str | None] = mapped_column(ForeignKey("agencies.id"), index=True)

    account: Mapped["Account"] = relationship(
        back_populates="whatsapp_business_accounts",
        overlaps="portfolio,whatsapp_business_accounts",
    )
    portfolio: Mapped["MetaBusinessPortfolio | None"] = relationship(
        back_populates="whatsapp_business_accounts",
        primaryjoin=lambda: and_(
            foreign(WhatsAppBusinessAccount.portfolio_id) == MetaBusinessPortfolio.id,
            foreign(WhatsAppBusinessAccount.account_id) == MetaBusinessPortfolio.account_id,
        ),
        foreign_keys=[portfolio_id, account_id],
        overlaps="account,whatsapp_business_accounts",
    )
    phone_numbers: Mapped[list["WhatsAppPhoneNumber"]] = relationship(
        back_populates="waba_account",
        primaryjoin=lambda: and_(
            WhatsAppBusinessAccount.id == foreign(WhatsAppPhoneNumber.waba_account_id),
            WhatsAppBusinessAccount.account_id == foreign(WhatsAppPhoneNumber.account_id),
        ),
        foreign_keys=lambda: [
            WhatsAppPhoneNumber.waba_account_id,
            WhatsAppPhoneNumber.account_id,
        ],
    )
    webhook_subscriptions: Mapped[list["WebhookSubscription"]] = relationship(
        back_populates="waba_account",
        primaryjoin=lambda: and_(
            WhatsAppBusinessAccount.id == foreign(WebhookSubscription.waba_account_id),
            WhatsAppBusinessAccount.account_id == foreign(WebhookSubscription.account_id),
        ),
        foreign_keys=lambda: [
            WebhookSubscription.waba_account_id,
            WebhookSubscription.account_id,
        ],
    )
    embedded_signup_sessions: Mapped[list["EmbeddedSignupSession"]] = relationship(
        back_populates="waba_account",
        primaryjoin=lambda: and_(
            WhatsAppBusinessAccount.id == foreign(EmbeddedSignupSession.waba_account_id),
            WhatsAppBusinessAccount.account_id == foreign(EmbeddedSignupSession.account_id),
        ),
        foreign_keys=lambda: [
            EmbeddedSignupSession.waba_account_id,
            EmbeddedSignupSession.account_id,
        ],
        overlaps="embedded_signup_sessions,account",
    )
    templates: Mapped[list["MessageTemplate"]] = relationship(
        back_populates="waba_account",
        primaryjoin=lambda: and_(
            WhatsAppBusinessAccount.id == foreign(MessageTemplate.waba_account_id),
            WhatsAppBusinessAccount.account_id == foreign(MessageTemplate.account_id),
        ),
        foreign_keys=lambda: [
            MessageTemplate.waba_account_id,
            MessageTemplate.account_id,
        ],
    )


class WhatsAppPhoneNumber(Base, TimestampMixin):
    __tablename__ = "whatsapp_phone_numbers"
    __table_args__ = (
        ForeignKeyConstraint(
            ["waba_account_id", "account_id"],
            ["whatsapp_business_accounts.id", "whatsapp_business_accounts.account_id"],
            name="fk_whatsapp_phone_numbers_waba_account_scope",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False, index=True)
    waba_account_id: Mapped[str] = mapped_column(ForeignKey("whatsapp_business_accounts.id"), nullable=False, index=True)
    waba_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    phone_number_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    display_phone_number: Mapped[str] = mapped_column(String(64), nullable=False)
    verified_name: Mapped[str | None] = mapped_column(String(255))
    quality_rating: Mapped[str] = mapped_column(String(16), default="UNKNOWN", nullable=False)
    quality_event: Mapped[str | None] = mapped_column(String(64))
    previous_quality_rating: Mapped[str | None] = mapped_column(String(16))
    messaging_limit_tier: Mapped[str | None] = mapped_column(String(64))
    max_daily_conversations_per_business: Mapped[int | None] = mapped_column(Integer)
    last_quality_event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    last_status_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    is_registered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    waba_account: Mapped["WhatsAppBusinessAccount"] = relationship(
        back_populates="phone_numbers",
        primaryjoin=lambda: and_(
            foreign(WhatsAppPhoneNumber.waba_account_id) == WhatsAppBusinessAccount.id,
            foreign(WhatsAppPhoneNumber.account_id) == WhatsAppBusinessAccount.account_id,
        ),
        foreign_keys=[waba_account_id, account_id],
    )
    conversations: Mapped[list["Conversation"]] = relationship(back_populates="phone_number")
    messages: Mapped[list["Message"]] = relationship(back_populates="phone_number")
    template_send_logs: Mapped[list["TemplateSendLog"]] = relationship(
        back_populates="phone_number",
        primaryjoin=lambda: and_(
            foreign(TemplateSendLog.account_id) == WhatsAppPhoneNumber.account_id,
            or_(
                foreign(TemplateSendLog.phone_number_id) == WhatsAppPhoneNumber.id,
                foreign(TemplateSendLog.phone_number_id) == WhatsAppPhoneNumber.phone_number_id,
            ),
        ),
        viewonly=True,
    )
    media_assets: Mapped[list["MediaAsset"]] = relationship(back_populates="phone_number")


class WebhookSubscription(Base, TimestampMixin):
    __tablename__ = "webhook_subscriptions"
    __table_args__ = (
        _string_enum_check(
            "status",
            _WEBHOOK_SUBSCRIPTION_STATUSES,
            name="status",
        ),
        Index(
            "uq_webhook_subscriptions_waba_callback",
            "account_id",
            "waba_id",
            "callback_url",
            unique=True,
        ),
        UniqueConstraint("id", "account_id", name="uq_webhook_subscriptions_id_account"),
        ForeignKeyConstraint(
            ["waba_account_id", "account_id"],
            ["whatsapp_business_accounts.id", "whatsapp_business_accounts.account_id"],
            name="fk_webhook_subscriptions_waba_account_scope",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False, index=True)
    waba_account_id: Mapped[str] = mapped_column(ForeignKey("whatsapp_business_accounts.id"), nullable=False, index=True)
    waba_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    callback_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    verify_token: Mapped[str | None] = mapped_column(String(255))
    app_secret: Mapped[str | None] = mapped_column(String(255))
    app_id: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    subscribed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))

    waba_account: Mapped["WhatsAppBusinessAccount"] = relationship(
        back_populates="webhook_subscriptions",
        primaryjoin=lambda: and_(
            foreign(WebhookSubscription.waba_account_id) == WhatsAppBusinessAccount.id,
            foreign(WebhookSubscription.account_id) == WhatsAppBusinessAccount.account_id,
        ),
        foreign_keys=[waba_account_id, account_id],
    )
    created_by_embedded_signup_sessions: Mapped[list["EmbeddedSignupSession"]] = relationship(
        back_populates="created_webhook_subscription",
        foreign_keys="EmbeddedSignupSession.created_webhook_subscription_id",
    )


class EmbeddedSignupSession(Base, TimestampMixin):
    __tablename__ = "embedded_signup_sessions"
    __table_args__ = (
        _string_enum_check(
            "status",
            _EMBEDDED_SIGNUP_SESSION_STATUSES,
            name="status",
        ),
        _string_enum_check(
            "completion_stage",
            _EMBEDDED_SIGNUP_COMPLETION_STAGES,
            name="completion_stage",
        ),
        _string_enum_check(
            "last_event_source",
            _EMBEDDED_SIGNUP_EVENT_SOURCES,
            name="last_event_source",
        ),
        ForeignKeyConstraint(
            ["waba_account_id", "account_id"],
            ["whatsapp_business_accounts.id", "whatsapp_business_accounts.account_id"],
            name="fk_embedded_signup_sessions_waba_account_scope",
        ),
        ForeignKeyConstraint(
            ["created_webhook_subscription_id", "account_id"],
            ["webhook_subscriptions.id", "webhook_subscriptions.account_id"],
            name="fk_embedded_signup_sessions_created_webhook_subscription_scope",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False, index=True)
    waba_account_id: Mapped[str | None] = mapped_column(ForeignKey("whatsapp_business_accounts.id"))
    created_webhook_subscription_id: Mapped[str | None] = mapped_column(
        ForeignKey("webhook_subscriptions.id"),
        index=True,
    )
    redirect_uri: Mapped[str] = mapped_column(String(1024), nullable=False)
    provider_name: Mapped[str] = mapped_column(String(32), default="mock", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="created", nullable=False)
    completion_stage: Mapped[str] = mapped_column(String(32), default="pending_callback", nullable=False)
    last_event_source: Mapped[str] = mapped_column(String(32), default="operator", nullable=False)
    remote_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    provider_waba_id: Mapped[str | None] = mapped_column(String(128))
    provider_business_portfolio_id: Mapped[str | None] = mapped_column(String(128))
    setup_session_id: Mapped[str | None] = mapped_column(String(128))
    linked_phone_number_ids_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    authorization_code_present: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    system_user_access_token_present: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    callback_received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    completion_message: Mapped[str | None] = mapped_column(Text)
    completion_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    error_message: Mapped[str | None] = mapped_column(Text)

    account: Mapped["Account"] = relationship(
        back_populates="embedded_signup_sessions",
        overlaps="embedded_signup_sessions",
    )
    waba_account: Mapped["WhatsAppBusinessAccount | None"] = relationship(
        back_populates="embedded_signup_sessions",
        primaryjoin=lambda: and_(
            foreign(EmbeddedSignupSession.waba_account_id) == WhatsAppBusinessAccount.id,
            foreign(EmbeddedSignupSession.account_id) == WhatsAppBusinessAccount.account_id,
        ),
        foreign_keys=[waba_account_id, account_id],
        overlaps="account,embedded_signup_sessions",
    )
    created_webhook_subscription: Mapped["WebhookSubscription | None"] = relationship(
        back_populates="created_by_embedded_signup_sessions",
        foreign_keys=[created_webhook_subscription_id],
    )


class Agent(Base, TimestampMixin):
    __tablename__ = "agents"
    __table_args__ = (
        UniqueConstraint("account_id", "agent_key", name="uq_agents_account_agent_key"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str | None] = mapped_column(ForeignKey("accounts.account_id"), index=True)
    agent_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), unique=True)
    status: Mapped[str] = mapped_column(String(32), default="offline", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    user_type: Mapped[str] = mapped_column(String(32), default="super_admin", nullable=False)
    agency_id: Mapped[str | None] = mapped_column(ForeignKey("agencies.id"), index=True)

    conversations: Mapped[list["Conversation"]] = relationship(back_populates="assigned_agent")


class Conversation(Base, TimestampMixin):
    __tablename__ = "conversations"
    __table_args__ = (
        UniqueConstraint("account_id", "external_conversation_id", name="uq_conversations_account_external_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False, index=True)
    external_conversation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    phone_number_id: Mapped[str | None] = mapped_column(ForeignKey("whatsapp_phone_numbers.id"))
    customer_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    customer_language: Mapped[str] = mapped_column(String(32), default="und", nullable=False)
    customer_language_source: Mapped[str] = mapped_column(String(32), default="unknown", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="open", nullable=False)
    ai_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    management_mode: Mapped[str] = mapped_column(String(32), default="ai_managed", nullable=False)
    assigned_agent_id: Mapped[str | None] = mapped_column(ForeignKey("agents.id"))
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    is_sleeping: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    last_customer_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), index=True)

    # ── 会话当前归属快照（spec 5.8） ──
    current_ai_agent_id: Mapped[str | None] = mapped_column(String(36), index=True)
    current_ai_assignment_id: Mapped[str | None] = mapped_column(String(36))
    current_entry_link_id: Mapped[str | None] = mapped_column(String(36), index=True)
    current_owner_agency_id_snapshot: Mapped[str | None] = mapped_column(String(128))
    current_owner_staff_user_id_snapshot: Mapped[str | None] = mapped_column(String(128))
    current_owner_agency_member_id_snapshot: Mapped[str | None] = mapped_column(String(128))
    current_owner_assignment_id_snapshot: Mapped[str | None] = mapped_column(String(36))
    ai_failover_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ai_failover_from_agent_id: Mapped[str | None] = mapped_column(String(36))
    ai_failover_reason: Mapped[str | None] = mapped_column(String(255))

    account: Mapped["Account"] = relationship(back_populates="conversations")
    phone_number: Mapped["WhatsAppPhoneNumber | None"] = relationship(back_populates="conversations")
    assigned_agent: Mapped["Agent | None"] = relationship(back_populates="conversations")
    tags: Mapped[list[str] | None] = mapped_column(JSON, nullable=True, default=list)
    site_key: Mapped[str | None] = mapped_column(String(50))
    messages: Mapped[list["Message"]] = relationship(back_populates="conversation")
    message_events: Mapped[list["MessageEvent"]] = relationship(back_populates="conversation")
    handover_logs: Mapped[list["HandoverLog"]] = relationship(back_populates="conversation")
    template_send_logs: Mapped[list["TemplateSendLog"]] = relationship(back_populates="conversation")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False, index=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), nullable=False, index=True)
    phone_number_id: Mapped[str | None] = mapped_column(ForeignKey("whatsapp_phone_numbers.id"))
    provider_message_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    message_type: Mapped[str] = mapped_column(String(32), nullable=False, default="text")
    language_code: Mapped[str | None] = mapped_column(String(32))
    translated_text: Mapped[str | None] = mapped_column(Text)
    translated_language_code: Mapped[str | None] = mapped_column(String(32))
    sender_id: Mapped[str | None] = mapped_column(String(128))
    recipient_id: Mapped[str | None] = mapped_column(String(128))
    content_text: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    ai_generated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sent_by_agent_id: Mapped[str | None] = mapped_column(ForeignKey("agents.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, nullable=False)
    is_cold: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)

    # ── 消息归属快照（spec 5.9） ──
    actor_type: Mapped[str | None] = mapped_column(String(32))
    # customer / staff / ai_agent / system
    actor_id: Mapped[str | None] = mapped_column(String(128))
    ai_agent_id: Mapped[str | None] = mapped_column(String(36), index=True)
    ai_assignment_id_snapshot: Mapped[str | None] = mapped_column(String(36))
    ai_provider: Mapped[str | None] = mapped_column(String(64))
    ai_model: Mapped[str | None] = mapped_column(String(128))
    ai_prompt_version: Mapped[str | None] = mapped_column(String(64))
    source_entry_link_id_snapshot: Mapped[str | None] = mapped_column(String(36), index=True)
    owner_agency_id_snapshot: Mapped[str | None] = mapped_column(String(128))
    owner_staff_user_id_snapshot: Mapped[str | None] = mapped_column(String(128), index=True)
    owner_agency_member_id_snapshot: Mapped[str | None] = mapped_column(String(128))
    owner_assignment_id_snapshot: Mapped[str | None] = mapped_column(String(36))
    source_job_id: Mapped[str | None] = mapped_column(String(64), index=True)
    delivery_mode: Mapped[str | None] = mapped_column(String(48))
    failover_from_ai_agent_id: Mapped[str | None] = mapped_column(String(36))
    failover_reason: Mapped[str | None] = mapped_column(String(255))

    account: Mapped["Account"] = relationship(back_populates="messages")
    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
    phone_number: Mapped["WhatsAppPhoneNumber | None"] = relationship(back_populates="messages")
    events: Mapped[list["MessageEvent"]] = relationship(back_populates="message")


class MessageEvent(Base):
    __tablename__ = "message_events"
    __table_args__ = (
        Index(
            "ix_message_events_account_event_created",
            "account_id",
            "event_type",
            "created_at",
        ),
        Index("ix_message_events_conversation_id", "conversation_id"),
        Index("ix_message_events_message_id", "message_id"),
        Index("ix_message_events_provider_name", "provider_name"),
        Index("ix_message_events_waba_id", "waba_id"),
        Index("ix_message_events_phone_number_id", "phone_number_id"),
        Index("ix_message_events_occurred_at", "occurred_at"),
        Index(
            "uq_message_events_account_provider_event",
            "account_id",
            "provider_name",
            "provider_event_id",
            unique=True,
            sqlite_where=text("provider_name IS NOT NULL AND provider_event_id IS NOT NULL"),
            postgresql_where=text("provider_name IS NOT NULL AND provider_event_id IS NOT NULL"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False, index=True)
    conversation_id: Mapped[str | None] = mapped_column(ForeignKey("conversations.id"))
    message_id: Mapped[str | None] = mapped_column(ForeignKey("messages.id"))
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_name: Mapped[str | None] = mapped_column(String(32))
    waba_id: Mapped[str | None] = mapped_column(String(128))
    phone_number_id: Mapped[str | None] = mapped_column(String(128))
    provider_event_id: Mapped[str | None] = mapped_column(String(255))
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, nullable=False)

    conversation: Mapped["Conversation | None"] = relationship(back_populates="message_events")
    message: Mapped["Message | None"] = relationship(back_populates="events")


class ProviderStatusEventBuffer(Base):
    __tablename__ = "provider_status_event_buffer"
    __table_args__ = (
        UniqueConstraint(
            "account_id",
            "provider_name",
            "provider_message_id",
            "external_status",
            name="uq_provider_status_buffer_status",
        ),
        Index(
            "ix_provider_status_buffer_account_state",
            "account_id",
            "replay_state",
            "last_seen_at",
        ),
        Index(
            "ix_provider_status_buffer_provider_message",
            "account_id",
            "provider_name",
            "provider_message_id",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False, index=True)
    provider_name: Mapped[str] = mapped_column(String(64), nullable=False)
    waba_id: Mapped[str | None] = mapped_column(String(128), index=True)
    phone_number_id: Mapped[str | None] = mapped_column(String(128), index=True)
    provider_message_id: Mapped[str] = mapped_column(String(255), nullable=False)
    external_status: Mapped[str] = mapped_column(String(64), nullable=False)
    recipient_id: Mapped[str | None] = mapped_column(String(128))
    occurred_at: Mapped[str | None] = mapped_column(String(64))
    error_code: Mapped[str | None] = mapped_column(String(128))
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, nullable=False)
    seen_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    replay_state: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    replayed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    replayed_message_event_id: Mapped[str | None] = mapped_column(ForeignKey("message_events.id"))
    replay_error: Mapped[str | None] = mapped_column(Text)


class HandoverLog(Base):
    __tablename__ = "handover_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False, index=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), nullable=False, index=True)
    triggered_by_type: Mapped[str] = mapped_column(String(32), nullable=False)
    triggered_by_id: Mapped[str | None] = mapped_column(String(128))
    from_mode: Mapped[str | None] = mapped_column(String(32))
    to_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, nullable=False)

    conversation: Mapped["Conversation"] = relationship(back_populates="handover_logs")


class MessageTemplate(Base, TimestampMixin):
    __tablename__ = "message_templates"
    __table_args__ = (
        Index(
            "uq_message_templates_account_waba_meta_template_id",
            "account_id",
            "waba_id",
            "meta_template_id",
            unique=True,
            sqlite_where=text("waba_id IS NOT NULL AND meta_template_id IS NOT NULL"),
            postgresql_where=text("waba_id IS NOT NULL AND meta_template_id IS NOT NULL"),
        ),
        Index(
            "uq_message_templates_account_waba_name_language",
            "account_id",
            "waba_id",
            "name",
            "language",
            unique=True,
            sqlite_where=text("waba_id IS NOT NULL"),
            postgresql_where=text("waba_id IS NOT NULL"),
        ),
        ForeignKeyConstraint(
            ["waba_account_id", "account_id"],
            ["whatsapp_business_accounts.id", "whatsapp_business_accounts.account_id"],
            name="fk_message_templates_waba_account_scope",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False, index=True)
    waba_account_id: Mapped[str | None] = mapped_column(ForeignKey("whatsapp_business_accounts.id"))
    waba_id: Mapped[str | None] = mapped_column(String(128), index=True)
    meta_template_id: Mapped[str | None] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    language: Mapped[str] = mapped_column(String(16), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="PENDING", nullable=False)
    components: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    rejected_reason: Mapped[str | None] = mapped_column(Text)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    provider_template_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    agency_id: Mapped[str | None] = mapped_column(ForeignKey("agencies.id"), index=True)

    waba_account: Mapped["WhatsAppBusinessAccount | None"] = relationship(
        back_populates="templates",
        primaryjoin=lambda: and_(
            foreign(MessageTemplate.waba_account_id) == WhatsAppBusinessAccount.id,
            foreign(MessageTemplate.account_id) == WhatsAppBusinessAccount.account_id,
        ),
        foreign_keys=[waba_account_id, account_id],
    )
    send_logs: Mapped[list["TemplateSendLog"]] = relationship(back_populates="template")


class TemplateSendLog(Base):
    __tablename__ = "template_send_logs"
    __table_args__ = (
        Index(
            "uq_template_send_logs_account_message_id",
            "account_id",
            "message_id",
            unique=True,
            sqlite_where=text("message_id IS NOT NULL"),
            postgresql_where=text("message_id IS NOT NULL"),
        ),
        Index(
            "uq_template_send_logs_account_idempotency_key",
            "account_id",
            "idempotency_key",
            unique=True,
            sqlite_where=text("idempotency_key IS NOT NULL"),
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False, index=True)
    template_id: Mapped[str | None] = mapped_column(ForeignKey("message_templates.id"))
    conversation_id: Mapped[str | None] = mapped_column(ForeignKey("conversations.id"))
    phone_number_id: Mapped[str | None] = mapped_column(String(128), index=True)
    waba_id: Mapped[str | None] = mapped_column(String(128), index=True)
    template_name: Mapped[str | None] = mapped_column(String(100))
    template_language: Mapped[str | None] = mapped_column(String(16))
    template_category: Mapped[str | None] = mapped_column(String(32))
    template_code: Mapped[str | None] = mapped_column(String(255))
    header_media_asset_id: Mapped[str | None] = mapped_column(String(36), index=True)
    header_media_asset_name: Mapped[str | None] = mapped_column(String(255))
    header_media_asset_type: Mapped[str | None] = mapped_column(String(32))
    header_media_provider_media_id: Mapped[str | None] = mapped_column(String(255))
    header_media_meta_media_id: Mapped[str | None] = mapped_column(String(255))
    header_media_sync_status: Mapped[str | None] = mapped_column(String(32))
    wa_id: Mapped[str] = mapped_column(String(128), nullable=False)
    message_id: Mapped[str | None] = mapped_column(String(255))
    idempotency_key: Mapped[str | None] = mapped_column(String(128), index=True)
    status: Mapped[str] = mapped_column(String(32), default="QUEUED", nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(64))
    conversation_origin_type: Mapped[str | None] = mapped_column(String(32), index=True)
    conversation_category: Mapped[str | None] = mapped_column(String(32), index=True)
    pricing_model: Mapped[str | None] = mapped_column(String(64), index=True)
    billable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    estimated_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    last_status_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    template: Mapped["MessageTemplate | None"] = relationship(back_populates="send_logs")
    conversation: Mapped["Conversation | None"] = relationship(back_populates="template_send_logs")
    phone_number: Mapped["WhatsAppPhoneNumber | None"] = relationship(
        back_populates="template_send_logs",
        primaryjoin=lambda: and_(
            foreign(TemplateSendLog.account_id) == WhatsAppPhoneNumber.account_id,
            or_(
                foreign(TemplateSendLog.phone_number_id) == WhatsAppPhoneNumber.id,
                foreign(TemplateSendLog.phone_number_id) == WhatsAppPhoneNumber.phone_number_id,
            ),
        ),
        viewonly=True,
    )


class TemplateDailyStat(Base, TimestampMixin):
    __tablename__ = "template_daily_stats"
    __table_args__ = (
        UniqueConstraint(
            "date",
            "account_id",
            "template_id",
            "waba_id",
            "phone_number_id",
            "template_name",
            "template_language",
            name="uq_template_daily_stats_scope",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False, index=True)
    template_id: Mapped[str | None] = mapped_column(ForeignKey("message_templates.id"), index=True)
    waba_id: Mapped[str | None] = mapped_column(String(128), index=True)
    phone_number_id: Mapped[str | None] = mapped_column(String(128), index=True)
    template_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    template_code: Mapped[str | None] = mapped_column(String(255))
    template_category: Mapped[str] = mapped_column(String(32), nullable=False)
    template_language: Mapped[str] = mapped_column(String(16), nullable=False)
    send_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    delivered_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    read_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    billable_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))


class TemplateHourlyStat(Base, TimestampMixin):
    __tablename__ = "template_hourly_stats"
    __table_args__ = (
        UniqueConstraint(
            "date",
            "hour_bucket",
            "account_id",
            "template_id",
            "waba_id",
            "phone_number_id",
            "template_name",
            "template_language",
            name="uq_template_hourly_stats_scope",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    hour_bucket: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False, index=True)
    template_id: Mapped[str | None] = mapped_column(ForeignKey("message_templates.id"), index=True)
    waba_id: Mapped[str | None] = mapped_column(String(128), index=True)
    phone_number_id: Mapped[str | None] = mapped_column(String(128), index=True)
    template_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    template_code: Mapped[str | None] = mapped_column(String(255))
    template_category: Mapped[str] = mapped_column(String(32), nullable=False)
    template_language: Mapped[str] = mapped_column(String(16), nullable=False)
    send_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    delivered_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    read_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    billable_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))


class TemplateFailureStat(Base, TimestampMixin):
    __tablename__ = "template_failure_stats"
    __table_args__ = (
        UniqueConstraint(
            "date",
            "account_id",
            "template_id",
            "waba_id",
            "phone_number_id",
            "template_name",
            "template_language",
            "error_code",
            name="uq_template_failure_stats_scope",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False, index=True)
    template_id: Mapped[str | None] = mapped_column(ForeignKey("message_templates.id"), index=True)
    waba_id: Mapped[str | None] = mapped_column(String(128), index=True)
    phone_number_id: Mapped[str | None] = mapped_column(String(128), index=True)
    template_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    template_code: Mapped[str | None] = mapped_column(String(255))
    template_category: Mapped[str] = mapped_column(String(32), nullable=False)
    template_language: Mapped[str] = mapped_column(String(16), nullable=False)
    error_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class WhatsAppDailyStat(Base, TimestampMixin):
    __tablename__ = "whatsapp_daily_stats"
    __table_args__ = (
        UniqueConstraint(
            "date",
            "account_id",
            "waba_id",
            "phone_number_id",
            "conversation_origin_type",
            "conversation_category",
            "pricing_model",
            "billable",
            "hour_bucket",
            name="uq_whatsapp_daily_stats_scope",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False, index=True)
    waba_id: Mapped[str | None] = mapped_column(String(128), index=True)
    phone_number_id: Mapped[str | None] = mapped_column(String(128), index=True)
    conversation_origin_type: Mapped[str | None] = mapped_column(String(32), index=True)
    conversation_category: Mapped[str | None] = mapped_column(String(32), index=True)
    pricing_model: Mapped[str | None] = mapped_column(String(64), index=True)
    billable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    inbound_message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    outbound_message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    delivered_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    read_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    billable_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    conversation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unique_customer_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    hour_bucket: Mapped[int | None] = mapped_column(Integer)


class WhatsAppConversationStat(Base, TimestampMixin):
    __tablename__ = "whatsapp_conversation_stats"
    __table_args__ = (
        UniqueConstraint(
            "date",
            "account_id",
            "conversation_id",
            "waba_id",
            "phone_number_id",
            "conversation_origin_type",
            "conversation_category",
            "pricing_model",
            "billable",
            "billable_key",
            "hour_bucket",
            name="uq_whatsapp_conversation_stats_scope",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False, index=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), nullable=False, index=True)
    customer_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    waba_id: Mapped[str | None] = mapped_column(String(128), index=True)
    phone_number_id: Mapped[str | None] = mapped_column(String(128), index=True)
    conversation_origin_type: Mapped[str | None] = mapped_column(String(32), index=True)
    conversation_category: Mapped[str | None] = mapped_column(String(32), index=True)
    pricing_model: Mapped[str | None] = mapped_column(String(64), index=True)
    billable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    billable_key: Mapped[str | None] = mapped_column(String(255), index=True)
    inbound_message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    outbound_message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    delivered_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    read_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    billable_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    hour_bucket: Mapped[int | None] = mapped_column(Integer)


Index(
    "ux_template_daily_stats_scope_nulls_not_distinct",
    TemplateDailyStat.date,
    TemplateDailyStat.account_id,
    _nullable_text_dimension(TemplateDailyStat.template_id),
    _nullable_text_dimension(TemplateDailyStat.waba_id),
    _nullable_text_dimension(TemplateDailyStat.phone_number_id),
    TemplateDailyStat.template_name,
    TemplateDailyStat.template_language,
    unique=True,
)

Index(
    "ux_template_hourly_stats_scope_nulls_not_distinct",
    TemplateHourlyStat.date,
    TemplateHourlyStat.hour_bucket,
    TemplateHourlyStat.account_id,
    _nullable_text_dimension(TemplateHourlyStat.template_id),
    _nullable_text_dimension(TemplateHourlyStat.waba_id),
    _nullable_text_dimension(TemplateHourlyStat.phone_number_id),
    TemplateHourlyStat.template_name,
    TemplateHourlyStat.template_language,
    unique=True,
)

Index(
    "ux_template_failure_stats_scope_nulls_not_distinct",
    TemplateFailureStat.date,
    TemplateFailureStat.account_id,
    _nullable_text_dimension(TemplateFailureStat.template_id),
    _nullable_text_dimension(TemplateFailureStat.waba_id),
    _nullable_text_dimension(TemplateFailureStat.phone_number_id),
    TemplateFailureStat.template_name,
    TemplateFailureStat.template_language,
    TemplateFailureStat.error_code,
    unique=True,
)

Index(
    "ux_whatsapp_daily_stats_scope_nulls_not_distinct",
    WhatsAppDailyStat.date,
    WhatsAppDailyStat.account_id,
    _nullable_text_dimension(WhatsAppDailyStat.waba_id),
    _nullable_text_dimension(WhatsAppDailyStat.phone_number_id),
    _nullable_text_dimension(WhatsAppDailyStat.conversation_origin_type),
    _nullable_text_dimension(WhatsAppDailyStat.conversation_category),
    _nullable_text_dimension(WhatsAppDailyStat.pricing_model),
    WhatsAppDailyStat.billable,
    _nullable_int_dimension(WhatsAppDailyStat.hour_bucket),
    unique=True,
)

Index(
    "ux_whatsapp_conversation_stats_scope_nulls_not_distinct",
    WhatsAppConversationStat.date,
    WhatsAppConversationStat.account_id,
    WhatsAppConversationStat.conversation_id,
    _nullable_text_dimension(WhatsAppConversationStat.waba_id),
    _nullable_text_dimension(WhatsAppConversationStat.phone_number_id),
    _nullable_text_dimension(WhatsAppConversationStat.conversation_origin_type),
    _nullable_text_dimension(WhatsAppConversationStat.conversation_category),
    _nullable_text_dimension(WhatsAppConversationStat.pricing_model),
    WhatsAppConversationStat.billable,
    _nullable_text_dimension(WhatsAppConversationStat.billable_key),
    _nullable_int_dimension(WhatsAppConversationStat.hour_bucket),
    unique=True,
)


class MediaAsset(Base, TimestampMixin):
    __tablename__ = "media_assets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False, index=True)
    waba_id: Mapped[str | None] = mapped_column(String(128), index=True)
    phone_number_id: Mapped[str | None] = mapped_column(ForeignKey("whatsapp_phone_numbers.id"), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    file_size: Mapped[int | None] = mapped_column(Integer)
    storage_key: Mapped[str | None] = mapped_column(String(512), index=True)
    storage_url: Mapped[str | None] = mapped_column(String(1024))
    meta_media_id: Mapped[str | None] = mapped_column(String(255), index=True)
    meta_media_status: Mapped[str | None] = mapped_column(String(64))
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="manual_upload")
    tags_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    created_by: Mapped[str | None] = mapped_column(String(128))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    phone_number: Mapped["WhatsAppPhoneNumber | None"] = relationship(back_populates="media_assets")
    events: Mapped[list["MediaAssetEvent"]] = relationship(back_populates="asset")
    provider_syncs: Mapped[list["MediaAssetProviderSync"]] = relationship(back_populates="asset")


class MediaAssetProviderSync(Base, TimestampMixin):
    __tablename__ = "media_asset_provider_syncs"
    __table_args__ = (
        UniqueConstraint(
            "asset_id",
            "provider_name",
            "phone_number_id",
            name="uq_media_asset_provider_syncs_scope",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False, index=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey("media_assets.id"), nullable=False, index=True)
    provider_name: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    waba_id: Mapped[str | None] = mapped_column(String(128), index=True)
    phone_number_id: Mapped[str | None] = mapped_column(String(128), index=True)
    provider_media_id: Mapped[str | None] = mapped_column(String(255), index=True)
    meta_media_id: Mapped[str | None] = mapped_column(String(255), index=True)
    sync_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    last_error_code: Mapped[str | None] = mapped_column(String(64))
    last_error_message: Mapped[str | None] = mapped_column(Text)
    raw_response: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    asset: Mapped["MediaAsset"] = relationship(back_populates="provider_syncs")


Index(
    "ux_media_asset_provider_syncs_scope_nulls_not_distinct",
    MediaAssetProviderSync.asset_id,
    MediaAssetProviderSync.provider_name,
    _nullable_text_dimension(MediaAssetProviderSync.phone_number_id),
    unique=True,
)


class MediaAssetEvent(Base):
    __tablename__ = "media_asset_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False, index=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey("media_assets.id"), nullable=False, index=True)
    waba_id: Mapped[str | None] = mapped_column(String(128), index=True)
    phone_number_id: Mapped[str | None] = mapped_column(String(128), index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    provider_media_id: Mapped[str | None] = mapped_column(String(255), index=True)
    meta_media_id: Mapped[str | None] = mapped_column(String(255), index=True)
    created_by: Mapped[str | None] = mapped_column(String(128))
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, nullable=False)

    asset: Mapped["MediaAsset"] = relationship(back_populates="events")


class ConversationNote(Base, TimestampMixin):
    __tablename__ = "conversation_notes"
    __table_args__ = (
        Index("ix_conversation_notes_account_conversation", "account_id", "conversation_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False, index=True)
    conversation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    agent_id: Mapped[str] = mapped_column(String(128), nullable=False)
    agent_name: Mapped[str | None] = mapped_column(String(255))

    account: Mapped["Account"] = relationship()


class CannedResponse(Base, TimestampMixin):
    __tablename__ = "canned_responses"
    __table_args__ = (
        Index("ix_canned_responses_account_category", "account_id", "category"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str | None] = mapped_column(ForeignKey("accounts.account_id"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    variables: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(128))

    account: Mapped["Account | None"] = relationship()


class BusinessHours(Base, TimestampMixin):
    __tablename__ = "business_hours"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False, unique=True, index=True)
    weekdays: Mapped[list[int]] = mapped_column(JSON, nullable=False, default=lambda: [1, 2, 3, 4, 5])
    start_time: Mapped[str] = mapped_column(String(5), nullable=False, default="09:00")
    end_time: Mapped[str] = mapped_column(String(5), nullable=False, default="18:00")
    timezone: Mapped[str] = mapped_column(String(50), nullable=False, default="Asia/Shanghai")
    off_hours_behavior: Mapped[str] = mapped_column(String(20), nullable=False, default="ai_managed")
    off_hours_message: Mapped[str | None] = mapped_column(Text)

    account: Mapped["Account"] = relationship()


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str | None] = mapped_column(ForeignKey("accounts.account_id"), index=True)
    actor_type: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String(128))
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    target_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_id: Mapped[str | None] = mapped_column(String(128))
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(String(500))
    action_type: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, nullable=False)


class AIProviderConfig(Base):
    __tablename__ = "ai_provider_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    provider_type: Mapped[str] = mapped_column(String(64), nullable=False)
    api_base_url: Mapped[str | None] = mapped_column(String(512))
    api_key_encrypted: Mapped[str | None] = mapped_column(String(1024))
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    use_responses_api: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    metadata_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, onupdate=utc_now, nullable=False)


class AccountAIProviderOverride(Base):
    __tablename__ = "account_ai_provider_overrides"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    provider_config_id: Mapped[str] = mapped_column(ForeignKey("ai_provider_configs.id", ondelete="CASCADE"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, onupdate=utc_now, nullable=False)


class TranslationProviderConfig(Base):
    __tablename__ = "translation_provider_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    provider_type: Mapped[str] = mapped_column(String(64), nullable=False)  # tencent_cloud
    secret_id_encrypted: Mapped[str | None] = mapped_column(String(1024))
    secret_key_encrypted: Mapped[str | None] = mapped_column(String(2048))
    region: Mapped[str | None] = mapped_column(String(64))
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    metadata_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, onupdate=utc_now, nullable=False)


class Product(Base, TimestampMixin):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("account_id", "name", name="uq_products_name_account"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    image_asset_id: Mapped[str | None] = mapped_column(ForeignKey("media_assets.id"), nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    tags: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class ProductPackage(Base, TimestampMixin):
    __tablename__ = "product_packages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    target_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    amount_tolerance_pct: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    product_count: Mapped[int] = mapped_column(Integer, nullable=False)
    product_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    product_snapshot: Mapped[list | None] = mapped_column(JSON, nullable=True)
    total_value: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))
    completion_reward: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))


class TaskRule(Base, TimestampMixin):
    __tablename__ = "task_rules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    rule_type: Mapped[str] = mapped_column(String(32), nullable=False)
    trigger_type: Mapped[str] = mapped_column(String(32), nullable=False)
    trigger_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    package_id: Mapped[str | None] = mapped_column(ForeignKey("product_packages.id"), nullable=True)
    follow_up_chain: Mapped[list | None] = mapped_column(JSON, nullable=True)
    expiry_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class MktTaskInstance(Base, TimestampMixin):
    __tablename__ = "mkt_task_instances"
    __table_args__ = (
        Index("ix_mkt_task_instances_user_status", "user_id", "status"),
        Index("ix_mkt_task_instances_rule_id", "rule_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), nullable=False, index=True)
    rule_id: Mapped[str] = mapped_column(ForeignKey("task_rules.id"), nullable=False)
    package_id: Mapped[str | None] = mapped_column(ForeignKey("product_packages.id"), nullable=True)
    task_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    product_progress: Mapped[list | None] = mapped_column(JSON, nullable=True)
    total_paid: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))
    reward_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    site_key: Mapped[str | None] = mapped_column(String(50))


class SignInRecord(Base, TimestampMixin):
    __tablename__ = "sign_in_records"
    __table_args__ = (
        UniqueConstraint("user_id", "sign_date", name="uq_sign_in_records_user_date"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), nullable=False, index=True)
    sign_date: Mapped[date] = mapped_column(Date, nullable=False)
    consecutive_days: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_rewarded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class InviteRecord(Base, TimestampMixin):
    __tablename__ = "invite_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False, index=True)
    inviter_user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), nullable=False, index=True)
    invitee_user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), nullable=False, index=True)
    invite_type: Mapped[str] = mapped_column(String(32), nullable=False)
    reward_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))
    is_rewarded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    invitee_ip: Mapped[str | None] = mapped_column(String(45), nullable=True, index=True)
    invitee_device_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)


class InviteLink(Base, TimestampMixin):
    __tablename__ = "invite_links"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), nullable=False, unique=True, index=True)
    invite_code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str | None] = mapped_column(ForeignKey("accounts.account_id"), nullable=True, index=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("app_users.id"), nullable=True)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="info")
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    action_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)


class H5SiteConfig(Base, TimestampMixin):
    __tablename__ = "h5_site_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    site_id: Mapped[str] = mapped_column(ForeignKey("h5_sites.id"), nullable=False, unique=True)

    # 品牌配置
    logo_url: Mapped[str | None] = mapped_column(String(500))
    favicon_url: Mapped[str | None] = mapped_column(String(500))
    primary_color: Mapped[str | None] = mapped_column(String(7), default="#1677ff")
    font_family: Mapped[str | None] = mapped_column(String(100))
    footer_text: Mapped[str | None] = mapped_column(String(500))

    # 功能开关
    enabled_pages: Mapped[list | None] = mapped_column(JSON)
    custom_css: Mapped[str | None] = mapped_column(Text)

    # 部署配置
    deploy_type: Mapped[str | None] = mapped_column(String(32))
    ssh_host: Mapped[str | None] = mapped_column(String(200))
    ssh_user: Mapped[str | None] = mapped_column(String(50))
    ssh_key_path: Mapped[str | None] = mapped_column(String(500))
    domain: Mapped[str | None] = mapped_column(String(200))
    ssl_enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class H5Language(Base, TimestampMixin):
    __tablename__ = "h5_languages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    language_code: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(50), nullable=False)
    flag_emoji: Mapped[str | None] = mapped_column(String(10))
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)


class H5Translation(Base, TimestampMixin):
    __tablename__ = "h5_translations"
    __table_args__ = (
        UniqueConstraint("site_id", "language_code", "translation_key", name="uq_h5_translation"),
        Index("ix_h5_translation_site_lang", "site_id", "language_code"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    site_id: Mapped[str] = mapped_column(ForeignKey("h5_sites.id"), nullable=False)
    language_code: Mapped[str] = mapped_column(String(10), nullable=False)
    translation_key: Mapped[str] = mapped_column(String(200), nullable=False)
    translated_text: Mapped[str] = mapped_column(Text, nullable=False)
    is_ai_translated: Mapped[bool] = mapped_column(Boolean, default=False)


class SitePermission(Base, TimestampMixin):
    __tablename__ = "site_permissions"
    __table_args__ = (
        UniqueConstraint("user_id", "site_id", name="uq_site_permission"),
        Index("ix_site_permission_user", "user_id"),
        Index("ix_site_permission_site", "site_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), nullable=False)
    site_id: Mapped[str] = mapped_column(ForeignKey("h5_sites.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)  # admin/editor/analyst/support


class Secret(Base, TimestampMixin):
    __tablename__ = "secrets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    encrypted_value: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))
    created_by: Mapped[str | None] = mapped_column(String(36))


class IPBlacklist(Base, TimestampMixin):
    __tablename__ = "ip_blacklist"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    ip_address: Mapped[str] = mapped_column(String(45), unique=True, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(500))
    blocked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    created_by: Mapped[str | None] = mapped_column(String(36))


class ClientError(Base):
    __tablename__ = "client_errors"
    __table_args__ = (
        Index("ix_client_errors_created_at", "created_at"),
        Index("ix_client_errors_error_type", "error_type"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    site_key: Mapped[str | None] = mapped_column(String(50))
    error_type: Mapped[str] = mapped_column(String(50), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    stack_trace: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(String(500))
    user_agent: Mapped[str | None] = mapped_column(String(500))
    ip_address: Mapped[str | None] = mapped_column(String(45))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, nullable=False)


class UptimeCheck(Base, TimestampMixin):
    __tablename__ = "uptime_checks"
    __table_args__ = (
        Index("ix_uptime_checks_site_id", "site_id"),
        Index("ix_uptime_checks_created_at", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    site_id: Mapped[str] = mapped_column(ForeignKey("h5_sites.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # up / down / timeout
    response_time_ms: Mapped[int | None] = mapped_column(Integer)
    status_code: Mapped[int | None] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(Text)


class DeployHistory(Base):
    __tablename__ = "deploy_history"
    __table_args__ = (
        Index("ix_deploy_history_site_created", "site_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    site_id: Mapped[str] = mapped_column(ForeignKey("h5_sites.id"), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, nullable=False)


class Agency(Base, TimestampMixin):
    __tablename__ = "agencies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    brand_name: Mapped[str | None] = mapped_column(String(200))
    logo_url: Mapped[str | None] = mapped_column(String(500))
    contact_name: Mapped[str | None] = mapped_column(String(100))
    contact_phone: Mapped[str | None] = mapped_column(String(20))
    contact_email: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    username: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(256), nullable=True)

    billing: Mapped[list["AgencyBilling"]] = relationship(back_populates="agency")
    members: Mapped[list["AgencyMember"]] = relationship(back_populates="agency")
    permission_grant: Mapped["AgencyPermissionGrant | None"] = relationship(
        back_populates="agency",
        uselist=False,
    )
    h5_template: Mapped["AgencyTemplate | None"] = relationship(back_populates="agency", uselist=False)


class AgencyMember(Base):
    __tablename__ = "agency_members"
    __table_args__ = (
        UniqueConstraint("agency_id", "user_id", name="uq_agency_members_agency_user"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    agency_id: Mapped[str] = mapped_column(ForeignKey("agencies.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, nullable=False)

    agency: Mapped["Agency"] = relationship(back_populates="members")


class AgencyBilling(Base):
    __tablename__ = "agency_billing"
    __table_args__ = (
        Index("ix_agency_billing_agency_status", "agency_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    agency_id: Mapped[str] = mapped_column(ForeignKey("agencies.id"), nullable=False, index=True)
    billing_type: Mapped[str] = mapped_column(String(32), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    billing_period_start: Mapped[date | None] = mapped_column(Date)
    billing_period_end: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    line_items: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, nullable=False)

    agency: Mapped["Agency"] = relationship(back_populates="billing")


class AgencyPermissionGrant(Base, TimestampMixin):
    __tablename__ = "agency_permission_grants"
    __table_args__ = (
        UniqueConstraint("agency_id", name="uq_agency_permission_grants_agency_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    agency_id: Mapped[str] = mapped_column(ForeignKey("agencies.id"), nullable=False, index=True)
    permissions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)

    agency: Mapped["Agency"] = relationship(back_populates="permission_grant")


class RolePermission(Base, TimestampMixin):
    """Role-based permission configuration for agencies.

    - agency_id = NULL → super admin level template (3 presets)
    - agency_id = set → agency-level role configuration
    - is_template = True → preset template (standard_support/standard_manager/finance_specialist)
    """

    __tablename__ = "role_permissions"
    __table_args__ = (
        UniqueConstraint("agency_id", "role_name", name="uq_role_permissions_agency_role"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    agency_id: Mapped[str | None] = mapped_column(ForeignKey("agencies.id"), nullable=True, index=True)
    role_name: Mapped[str] = mapped_column(String(50), nullable=False)
    is_template: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    template_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    permissions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)

    agency: Mapped["Agency | None"] = relationship()


class H5Template(Base, TimestampMixin):
    __tablename__ = "h5_templates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    preview_url: Mapped[str | None] = mapped_column(String(500))
    template_data: Mapped[dict | None] = mapped_column(JSON)
    created_by: Mapped[str | None] = mapped_column(String(36))

    # ── 模板包字段 ──
    package_filename: Mapped[str | None] = mapped_column(String(500), nullable=True)
    package_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    package_uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    preview_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    publish_status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    published_by: Mapped[str | None] = mapped_column(String(36), nullable=True)

    agencies: Mapped[list["AgencyTemplate"]] = relationship(back_populates="template")


class AgencyTemplate(Base):
    __tablename__ = "agency_templates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    agency_id: Mapped[str] = mapped_column(ForeignKey("agencies.id"), nullable=False, unique=True)
    template_id: Mapped[str] = mapped_column(ForeignKey("h5_templates.id"), nullable=False)
    selected_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, nullable=False)

    agency: Mapped["Agency"] = relationship(back_populates="h5_template")
    template: Mapped["H5Template"] = relationship(back_populates="agencies")


class SiteWABABinding(Base):
    __tablename__ = "site_waba_bindings"
    __table_args__ = (
        UniqueConstraint("site_id", "waba_id", name="uq_site_waba_binding"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    site_id: Mapped[str] = mapped_column(ForeignKey("h5_sites.id"), nullable=False, index=True)
    waba_id: Mapped[str] = mapped_column(ForeignKey("whatsapp_business_accounts.id"), nullable=False, index=True)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, nullable=False)
    assigned_by: Mapped[str | None] = mapped_column(String(36))


class DbBackup(Base):
    __tablename__ = "db_backups"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    filename: Mapped[str] = mapped_column(String(200), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    backup_type: Mapped[str] = mapped_column(String(20), default="manual")  # manual/auto_daily/auto_weekly
    status: Mapped[str] = mapped_column(String(20), default="running")  # running/completed/failed
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36))


class KnowledgeCategory(Base, TimestampMixin):
    __tablename__ = "knowledge_categories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    agency_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class KnowledgeArticle(Base, TimestampMixin):
    __tablename__ = "knowledge_articles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    category_id: Mapped[str | None] = mapped_column(ForeignKey("knowledge_categories.id"), nullable=True, index=True)
    agency_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    keywords: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    view_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class CustomerAutoTagRule(Base):
    __tablename__ = "customer_auto_tag_rules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    agency_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    condition_type: Mapped[str] = mapped_column(String(50), nullable=False)  # recharge_total/sign_in_count/conversation_count
    condition_operator: Mapped[str] = mapped_column(String(10), nullable=False)  # gt/lt/eq/gte/lte
    condition_value: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    tag_name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, nullable=False)


class ApiRateLimit(Base):
    __tablename__ = "api_rate_limits"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    agency_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    endpoint_pattern: Mapped[str] = mapped_column(String(200), nullable=False)
    max_requests: Mapped[int] = mapped_column(Integer, nullable=False)
    window_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    ban_minutes: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, nullable=False)


class EmailConfig(Base):
    __tablename__ = "email_config"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    smtp_host: Mapped[str] = mapped_column(String(200), nullable=False)
    smtp_port: Mapped[int] = mapped_column(Integer, default=465, nullable=False)
    smtp_user: Mapped[str] = mapped_column(String(200), nullable=False)
    smtp_password: Mapped[str] = mapped_column(String(500), nullable=False)
    smtp_ssl: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    from_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    from_email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, nullable=False)


class HealthCheck(Base):
    __tablename__ = "health_checks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    check_type: Mapped[str] = mapped_column(String(50), nullable=False)  # db/redis/api/site/ssl
    target: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # healthy/warning/error
    response_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, nullable=False)


class AiChatConfig(Base):
    """AI 智能聊天行为配置 — 严格对齐 spec 文档.

    - agency_id=NULL: 系统默认配置
    - agency_id=非NULL: 代理商自定义配置（唯一索引）
    - 包含 8 大类 40+ 配置参数
    """

    __tablename__ = "ai_chat_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    agency_id: Mapped[str | None] = mapped_column(String(36), nullable=True, unique=True, index=True)

    # ── 1. 系统提示词 ──
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_append_context: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=True)
    prompt_variables: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # ── 2. 模型参数 ──
    temperature: Mapped[float | None] = mapped_column(Float, nullable=True, default=0.3)
    max_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True, default=300)
    top_p: Mapped[float | None] = mapped_column(Float, nullable=True, default=1.0)
    frequency_penalty: Mapped[float | None] = mapped_column(Float, nullable=True, default=0.0)
    presence_penalty: Mapped[float | None] = mapped_column(Float, nullable=True, default=0.0)
    stop_sequences: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # ── 3. 会话行为 ──
    context_window_messages: Mapped[int | None] = mapped_column(Integer, nullable=True, default=10)
    context_window_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True, default=2000)
    conversation_memory: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=True)
    greeting_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    off_hours_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    off_hours_start: Mapped[str | None] = mapped_column(String(5), nullable=True)
    off_hours_end: Mapped[str | None] = mapped_column(String(5), nullable=True)
    off_hours_timezone: Mapped[str | None] = mapped_column(String(50), nullable=True, default="Asia/Shanghai")

    # ── 4. 自动回复 ──
    auto_reply_enabled: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=True)
    auto_reply_delay_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True, default=2)
    auto_reply_keywords: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    auto_reply_fallback: Mapped[str | None] = mapped_column(Text, nullable=True)
    duplicate_message_filter: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=True)

    # ── 5. 转人工 ──
    auto_escalation_enabled: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=True)
    escalation_keywords: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    escalation_max_failures: Mapped[int | None] = mapped_column(Integer, nullable=True, default=3)
    escalation_sentiment_threshold: Mapped[float | None] = mapped_column(Float, nullable=True, default=-0.5)
    escalation_max_rounds: Mapped[int | None] = mapped_column(Integer, nullable=True, default=20)
    escalation_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── 6. 安全 ──
    blocked_topics: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    content_filter_enabled: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=True)
    pii_protection: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=True)
    max_response_length: Mapped[int | None] = mapped_column(Integer, nullable=True, default=500)
    language_lock: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=False)

    # ── 7. 高级 ──
    response_format: Mapped[str | None] = mapped_column(String(20), nullable=True, default="text")
    inject_brand_info: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=True)
    inject_knowledge_base: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=True)
    debug_mode: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=False)

    # ── 8. AI 工具调用 ──
    tools_enabled: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=True)
    enabled_tools: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    max_tool_calls_per_session: Mapped[int | None] = mapped_column(Integer, nullable=True, default=10)
    identity_verify_method: Mapped[str | None] = mapped_column(String(20), nullable=True, default="whatsapp")
    identity_auto_verify: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=True)
    tool_call_timeout_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True, default=5)

    # ── 元数据 ──
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, onupdate=utc_now, nullable=False)



# ═══════════════════════════════════════════════════════════════════════════════
# 39. AI 用量记录 ai_usage_records
# ═══════════════════════════════════════════════════════════════════════════════

class AiUsageRecord(Base):
    __tablename__ = "ai_usage_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    agency_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    site_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    conversation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    provider_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    message_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    cost: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=0, nullable=False)
    billing_month: Mapped[str | None] = mapped_column(String(7), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, nullable=False)


# ═══════════════════════════════════════════════════════════════════════════════
# 40. 翻译用量记录 translation_usage_records
# ═══════════════════════════════════════════════════════════════════════════════

class TranslationUsageRecord(Base):
    __tablename__ = "translation_usage_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    agency_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    site_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    translation_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    cost: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=0, nullable=False)
    billing_month: Mapped[str | None] = mapped_column(String(7), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, nullable=False)


# ═══════════════════════════════════════════════════════════════════════════════
# 41. AI Provider 费率 ai_provider_rates
# ═══════════════════════════════════════════════════════════════════════════════

class AiProviderRate(Base):
    __tablename__ = "ai_provider_rates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    provider_name: Mapped[str] = mapped_column(String(64), nullable=False)
    cost_per_message: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="CNY", nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, onupdate=utc_now, nullable=False)


# ═══════════════════════════════════════════════════════════════════════════════
# 42. 代理商免费额度 agency_free_quotas
# ═══════════════════════════════════════════════════════════════════════════════

class AgencyFreeQuota(Base):
    __tablename__ = "agency_free_quotas"
    __table_args__ = (
        UniqueConstraint("agency_id", "billing_month", name="uq_agency_free_quotas_month"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    agency_id: Mapped[str] = mapped_column(String(36), nullable=False)
    free_ai_messages: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    free_translations: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    billing_month: Mapped[str] = mapped_column(String(7), nullable=False)
    used_ai_messages: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    used_translations: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, nullable=False)


# ═══════════════════════════════════════════════════════════════════════════════
# 43. 代理商月度账单 agency_monthly_bills
# ═══════════════════════════════════════════════════════════════════════════════

class AgencyMonthlyBill(Base):
    __tablename__ = "agency_monthly_bills"
    __table_args__ = (
        UniqueConstraint("agency_id", "billing_month", name="uq_agency_monthly_bills_month"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    agency_id: Mapped[str] = mapped_column(String(36), nullable=False)
    billing_month: Mapped[str] = mapped_column(String(7), nullable=False)
    ai_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    translation_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    total_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    free_ai_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    free_translation_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, nullable=False)


# ═══════════════════════════════════════════════════════════════════════════════
# 44. 站点币种 site_currencies
# ═══════════════════════════════════════════════════════════════════════════════

class SiteCurrency(Base):
    __tablename__ = "site_currencies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    site_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    currency_code: Mapped[str] = mapped_column(String(10), nullable=False)
    currency_symbol: Mapped[str] = mapped_column(String(5), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, nullable=False)


# ═══════════════════════════════════════════════════════════════════════════════
# 45. 汇率 exchange_rates
# ═══════════════════════════════════════════════════════════════════════════════

class ExchangeRate(Base):
    __tablename__ = "exchange_rates"
    __table_args__ = (
        UniqueConstraint("from_currency", "to_currency", name="uq_exchange_rates_pair"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    from_currency: Mapped[str] = mapped_column("from_currency", String(10), nullable=False)
    to_currency: Mapped[str] = mapped_column(String(10), nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    source: Mapped[str] = mapped_column(String(20), default="manual", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, onupdate=utc_now, nullable=False)


# ═══════════════════════════════════════════════════════════════════════════════
# 46. 支付渠道 payment_channels
# ═══════════════════════════════════════════════════════════════════════════════

class PaymentChannel(Base):
    __tablename__ = "payment_channels"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    channel_type: Mapped[str] = mapped_column(String(50), nullable=False)
    app_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    app_secret_encrypted: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    callback_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    fee_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=0, nullable=False)
    min_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    max_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    is_sandbox: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    callback_secret: Mapped[str | None] = mapped_column(String(200), nullable=True)
    config_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, onupdate=utc_now, nullable=False)


# ═══════════════════════════════════════════════════════════════════════════════
# 47. 代理商渠道设置 agent_payment_channel_settings
# ═══════════════════════════════════════════════════════════════════════════════

class AgentPaymentChannelSetting(Base):
    __tablename__ = "agent_payment_channel_settings"
    __table_args__ = (
        UniqueConstraint("agency_id", "channel_id", name="uq_agent_channel_settings"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    agency_id: Mapped[str] = mapped_column(String(36), nullable=False)
    channel_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_recharge_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_withdraw_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    custom_merchant_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    custom_secret_encrypted: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, nullable=False)


# ═══════════════════════════════════════════════════════════════════════════════
# 48. 代理商提现设置 withdrawal_settings
# ═══════════════════════════════════════════════════════════════════════════════

class WithdrawalSetting(Base):
    __tablename__ = "withdrawal_settings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    agency_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    auto_approve_below: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    min_withdraw_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=10, nullable=False)
    max_daily_withdraw: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    fee_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    fee_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=0, nullable=False)
    freeze_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    freeze_threshold_count: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    freeze_threshold_hours: Mapped[int] = mapped_column(Integer, default=24, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, onupdate=utc_now, nullable=False)


# ═══════════════════════════════════════════════════════════════════════════════
# 49. 充值记录 recharge_records
# ═══════════════════════════════════════════════════════════════════════════════

class RechargeRecord(Base):
    __tablename__ = "recharge_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    agency_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    site_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    channel_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    converted_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    exchange_rate: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="completed", nullable=False)
    channel_order_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    callback_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    callback_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, nullable=False)


# ═══════════════════════════════════════════════════════════════════════════════
# 50. 提现记录 withdrawal_records
# ═══════════════════════════════════════════════════════════════════════════════

class WithdrawalRecord(Base):
    __tablename__ = "withdrawal_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    agency_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    site_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    fee: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    net_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    auto_approved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    reject_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    frozen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    frozen_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, nullable=False)


# ═══════════════════════════════════════════════════════════════════════════════
# 51. 支付回调记录 payment_callbacks
# ═══════════════════════════════════════════════════════════════════════════════

class PaymentCallback(Base):
    __tablename__ = "payment_callbacks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    channel_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    recharge_record_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    raw_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    signature_valid: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    processed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_retries: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)


# ═══════════════════════════════════════════════════════════════════════════════
# 52. 对账记录 payment_reconciliations
# ═══════════════════════════════════════════════════════════════════════════════

class PaymentReconciliation(Base):
    __tablename__ = "payment_reconciliations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    channel_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    reconcile_date: Mapped[date] = mapped_column(Date, nullable=False)
    platform_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    channel_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    difference: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, nullable=False)


# ── 注册归属 / AI 接待 / 入口链接新表到 Base.metadata（spec 5.1-5.10） ──
# 放在文件末尾以避免前向引用；新表定义集中在 ownership_models.py。
from app.db.ownership_models import (  # noqa: E402,F401
    AIAgent,
    AIFailoverEvent,
    AIOutboundJob,
    ConversationAIAssignment,
    EntryLink,
    MemberAIAssignment,
    MemberAITransferBatch,
    MemberAITransferItem,
    MemberOwnerAssignment,
    MemberOwnerTransferBatch,
    MemberOwnerTransferItem,
    OwnershipAuditEvent,
)
