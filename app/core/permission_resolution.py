from __future__ import annotations

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import ActorRole
from app.core.permission_defs import (
    DEFAULT_TEMPLATES,
    get_permission_definition,
    normalize_permission_codes,
    partition_permission_codes,
)
from app.db.models import RolePermission

logger = structlog.get_logger()

ROLE_TEMPLATE_ALIASES: dict[str, str] = {
    "support": "standard_support",
    "manager": "standard_manager",
    "finance": "finance_specialist",
}


def _codes(*permission_codes: str) -> tuple[str, ...]:
    return permission_codes


BUILTIN_ROLE_PERMISSION_CODES: dict[ActorRole, tuple[str, ...]] = {
    ActorRole.SUPER_ADMIN: (),
    ActorRole.OPERATOR: _codes(
        "dashboard.view",
        "dashboard.performance",
        "dashboard.stats",
        "runtime.view",
        "runtime.edit",
        "audit.view",
        "sites.view",
        "sites.create",
        "sites.edit",
        "sites.delete",
        "sites.waba_assign",
        "sites.template",
        "sites.deploy",
        "sites.brand_config",
        "sites.analytics",
        "sites.clone",
        "users.view",
        "users.create",
        "users.edit",
        "users.delete",
        "tags.view",
        "tags.create",
        "tags.edit",
        "tags.delete",
        "audience_rules.view",
        "audience_rules.create",
        "audience_rules.edit",
        "audience_rules.delete",
        "tasks.view",
        "tasks.detail",
        "tasks.push",
        "tasks.retry",
        "tasks.create",
        "tasks.claim",
        "tasks.submit",
        "tickets.view",
        "tickets.create",
        "tickets.status",
        "tickets.reply",
        "tickets.close",
        "tickets.assign",
        "notifications.view",
        "notifications.mark_read",
        "notifications.manage",
        "finance.view_channels",
        "finance.edit_channels",
        "finance.view_recharge",
        "finance.view_withdrawal",
        "finance.approve_withdrawal",
        "withdrawal.duplicate_account.view",
        "withdrawal.account_sensitive.view",
        "reports.view",
        "reports.whatsapp",
        "reports.operations",
        "reports.finance",
        "reports.export",
        "operations.view",
        "operations.queue",
        "operations.batch",
        "meta.view",
        "meta.create",
        "meta.edit",
        "meta.delete",
        "meta.sync_phones",
        "meta.webhook",
        "media.view",
        "media.upload",
        "media.delete",
        "knowledge.view",
        "knowledge.manage",
        "knowledge.ai_test",
        "settings.view",
        "settings.ai_config",
        "settings.translation",
        "settings.languages",
        "settings.runtime",
        "settings.secrets",
        "profile.view",
        "profile.edit",
        "profile.change_password",
        "conversations.view",
        "conversations.detail",
        "conversations.reply",
        "conversations.handover",
        "conversations.restore_ai",
        "conversations.close",
        "conversations.transfer",
        "conversations.batch",
        "conversations.filter",
        "conversations.notes",
        "conversations.tags",
        "conversations.translate",
        "conversations.wake",
        "conversations.ai_preview",
        "conversations.reopen",
        "conversations.sentiment",
        "conversations.sla",
        "templates.view",
        "templates.create",
        "templates.edit",
        "templates.delete",
        "templates.send",
        "templates.review",
        "templates.sync_meta",
        "templates.rebuild_stats",
        "dev.mock",
        "ai_chat_config.view_system",
        "ai_chat_config.edit_system",
        "ai_chat_config.view_agency",
        "ai_chat_config.edit_agency",
        "ai_chat_config.reset_agency",
        "ai_chat_config.test",
        "ai_chat_config.view_tools",
        "ai_chat_config.edit_tools",
        "ai_billing.view_rates",
        "ai_billing.edit_rates",
        "ai_billing.view_quotas",
        "ai_billing.edit_quotas",
        "ai_billing.view_usage",
        "ai_billing.view_bills",
        "exchange_rate.view",
        "exchange_rate.edit",
        "backups.view",
        "backups.create",
        "backups.restore",
        "backups.delete",
        "batch.tags",
        "batch.assign",
        "batch.send_template",
        "batch.import",
        "rate_limits.manage",
        "finance_settings.view",
        "finance_settings.edit",
        "customer_profile.view",
        "monitoring.view",
        "monitoring.manage",
        "reviews.view",
        "reviews.approve",
        "reviews.reject",
        "customers.edit_lifecycle",
        "member.popover.view",
        "member.sensitive.view",
        "member.finance_breakdown.view",
        "canned_responses.view",
        "canned_responses.create",
        "canned_responses.edit",
        "canned_responses.delete",
        "ai_providers.view",
        "ai_providers.create",
        "ai_providers.edit",
        "ai_providers.delete",
        "ai_providers.test",
        "ai_providers.override",
        "members.view",
        "members.status",
        "members.workload",
        "members.manage",
        "agents.view",
        "agents.create",
        "agents.edit",
        "agents.delete",
        "agents.reset_password",
        "agents.billing",
        "agents.billing_verify",
        "agents.members",
        "agents.members_role",
        "agents.permissions",
        "api_stats.view",
    ),
    ActorRole.REVIEWER: _codes(
        "dashboard.view",
        "reviews.view",
        "reviews.approve",
        "reviews.reject",
        "tasks.view",
        "tasks.detail",
        "tickets.view",
        "customers.view",
        "customers.detail",
        "member.popover.view",
        "profile.view",
        "profile.edit",
        "profile.change_password",
        "notifications.view",
        "notifications.mark_read",
    ),
    ActorRole.SUPPORT_AGENT: _codes(
        "dashboard.view",
        "conversations.view",
        "conversations.detail",
        "conversations.reply",
        "conversations.notes",
        "conversations.translate",
        "tickets.view",
        "tickets.create",
        "tickets.reply",
        "tickets.status",
        "customers.view",
        "customers.detail",
        "customers.timeline",
        "customers.conversations",
        "member.popover.view",
        "templates.view",
        "templates.send",
        "media.view",
        "media.upload",
        "ecommerce.view",
        "ecommerce.orders",
        "ecommerce.logistics",
        "knowledge.view",
        "notifications.view",
        "notifications.mark_read",
        "profile.view",
        "profile.edit",
        "profile.change_password",
    ),
    ActorRole.FINANCE: _codes(
        "dashboard.view",
        "dashboard.stats",
        "customers.view",
        "customers.finance",
        "finance.view_channels",
        "finance.edit_channels",
        "finance.view_recharge",
        "finance.view_withdrawal",
        "finance.approve_withdrawal",
        "withdrawal.duplicate_account.view",
        "withdrawal.account_sensitive.view",
        "member.popover.view",
        "member.finance_breakdown.view",
        "finance_settings.view",
        "reports.view",
        "reports.finance",
        "reports.export",
        "profile.view",
        "profile.edit",
        "profile.change_password",
        "notifications.view",
        "notifications.mark_read",
    ),
    ActorRole.RISK_CONTROL: _codes(
        "dashboard.view",
        "users.view",
        "users.edit",
        "audience_rules.view",
        "audience_rules.edit",
        "tasks.view",
        "tasks.detail",
        "customers.view",
        "finance.view_withdrawal",
        "withdrawal.duplicate_account.view",
        "member.popover.view",
        "monitoring.view",
        "profile.view",
        "profile.edit",
        "profile.change_password",
    ),
    ActorRole.READONLY: _codes(
        "dashboard.view",
        "dashboard.performance",
        "dashboard.stats",
        "runtime.view",
        "audit.view",
        "sites.view",
        "users.view",
        "tags.view",
        "audience_rules.view",
        "tasks.view",
        "tasks.detail",
        "tickets.view",
        "notifications.view",
        "finance.view_channels",
        "finance.view_recharge",
        "finance.view_withdrawal",
        "withdrawal.duplicate_account.view",
        "reports.view",
        "reports.whatsapp",
        "reports.operations",
        "reports.finance",
        "operations.view",
        "meta.view",
        "media.view",
        "knowledge.view",
        "settings.view",
        "profile.view",
        "conversations.view",
        "conversations.detail",
        "member.popover.view",
        "templates.view",
        "monitoring.view",
        "members.view",
        "api_stats.view",
    ),
    ActorRole.AGENT: _codes(
        *DEFAULT_TEMPLATES["standard_manager"]["permissions"],
        "members.manage",
        "agents.view",
        "agents.edit",
        "agents.members",
        "agents.members_role",
        "agents.billing",
        "agents.billing_verify",
        "users.view",
        "users.create",
        "users.edit",
        "users.delete",
        "audience_rules.view",
        "audience_rules.create",
        "audience_rules.edit",
        "audience_rules.delete",
        "canned_responses.view",
        "canned_responses.create",
        "canned_responses.edit",
        "canned_responses.delete",
        "runtime.view",
        "settings.runtime",
    ),
    ActorRole.AGENT_MEMBER: _codes(
        *DEFAULT_TEMPLATES["standard_support"]["permissions"],
        "runtime.view",
        "users.view",
        "ecommerce.view",
        "ecommerce.orders",
        "ecommerce.logistics",
    ),
}


def _normalize_permissions(
    permission_codes: list[str] | tuple[str, ...],
    *,
    source: str,
    ignore_unknown: bool,
) -> list[str]:
    valid, invalid = partition_permission_codes(permission_codes)
    if invalid:
        logger.warning(
            "permission_resolution.invalid_permissions",
            source=source,
            invalid_permissions=invalid,
        )
        if not ignore_unknown:
            raise ValueError(f"Unknown permission codes: {', '.join(invalid)}")
    return valid


def _strip_super_admin_only_permissions(
    permission_codes: list[str],
    *,
    source: str,
) -> list[str]:
    filtered: list[str] = []
    removed: list[str] = []
    for permission_code in permission_codes:
        if get_permission_definition(permission_code).get("super_admin_only"):
            removed.append(permission_code)
            continue
        filtered.append(permission_code)
    if removed:
        logger.warning(
            "permission_resolution.filtered_super_admin_only_permissions",
            source=source,
            removed_permissions=sorted(removed),
        )
    return filtered


def get_builtin_role_permissions(role: ActorRole) -> list[str]:
    permissions = _normalize_permissions(
        BUILTIN_ROLE_PERMISSION_CODES.get(role, ()),
        source=f"builtin:{role.value}",
        ignore_unknown=False,
    )
    if role in {ActorRole.AGENT, ActorRole.AGENT_MEMBER}:
        return _strip_super_admin_only_permissions(
            permissions,
            source=f"builtin:{role.value}",
        )
    return permissions


def resolve_role_permissions(
    session: Session,
    *,
    user_type: str,
    agency_id: str | None,
    role_name: str | None,
) -> list[str] | None:
    if user_type not in {"agent", "agent_member"} or not agency_id:
        return None

    if user_type == "agent":
        record = session.execute(
            select(RolePermission).where(
                RolePermission.agency_id == agency_id,
                RolePermission.role_name == "agent",
            )
        ).scalar_one_or_none()
        if record is None:
            return None
        return _strip_super_admin_only_permissions(
            _normalize_permissions(
                list(record.permissions or []),
                source=f"db:{agency_id}:agent",
                ignore_unknown=True,
            ),
            source=f"db:{agency_id}:agent",
        )

    member_role = role_name or "support"
    for candidate in (member_role, "support"):
        record = session.execute(
            select(RolePermission).where(
                RolePermission.agency_id == agency_id,
                RolePermission.role_name == candidate,
            )
        ).scalar_one_or_none()
        if record:
            return _strip_super_admin_only_permissions(
                _normalize_permissions(
                    list(record.permissions or []),
                    source=f"db:{agency_id}:{candidate}",
                    ignore_unknown=True,
                ),
                source=f"db:{agency_id}:{candidate}",
            )

    template = DEFAULT_TEMPLATES.get(member_role)
    if template is None:
        template = DEFAULT_TEMPLATES.get(ROLE_TEMPLATE_ALIASES.get(member_role, ""))
    if template:
        return _strip_super_admin_only_permissions(
            normalize_permission_codes(template["permissions"]),
            source=f"template:{member_role}",
        )
    return None
