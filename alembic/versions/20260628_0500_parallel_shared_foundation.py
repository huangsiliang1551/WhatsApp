"""parallel shared foundation for W0

Revision ID: 20260628_0500
Revises: 20260626_0405
Create Date: 2026-06-28 05:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260628_0500"
down_revision: str | Sequence[str] | None = "20260626_0405"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_table(inspector: sa.Inspector, table_name: str) -> bool:
    return inspector.has_table(table_name)


def _has_column(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    if not _has_table(inspector, table_name):
        return False
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def _has_index(inspector: sa.Inspector, table_name: str, index_name: str) -> bool:
    if not _has_table(inspector, table_name):
        return False
    return index_name in {index["name"] for index in inspector.get_indexes(table_name)}


def _add_column_if_missing(
    inspector: sa.Inspector,
    table_name: str,
    column: sa.Column,
) -> None:
    if not _has_column(inspector, table_name, column.name):
        op.add_column(table_name, column)


def _create_index_if_missing(
    inspector: sa.Inspector,
    table_name: str,
    index_name: str,
    columns: list[str],
    *,
    unique: bool = False,
    sqlite_where: sa.TextClause | None = None,
    postgresql_where: sa.TextClause | None = None,
) -> None:
    if not _has_index(inspector, table_name, index_name):
        op.create_index(
            index_name,
            table_name,
            columns,
            unique=unique,
            sqlite_where=sqlite_where,
            postgresql_where=postgresql_where,
        )


def _drop_index_if_exists(
    inspector: sa.Inspector,
    table_name: str,
    index_name: str,
) -> None:
    if _has_index(inspector, table_name, index_name):
        op.drop_index(index_name, table_name=table_name)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for column in (
        sa.Column("current_supervisor_id", sa.String(length=128), nullable=True),
        sa.Column("current_team_id", sa.String(length=128), nullable=True),
        sa.Column("owner_assigned_by", sa.String(length=128), nullable=True),
        sa.Column("owner_source", sa.String(length=64), nullable=True),
    ):
        _add_column_if_missing(inspector, "member_profiles", column)
    _create_index_if_missing(inspector, "member_profiles", "ix_member_profiles_current_supervisor_id", ["current_supervisor_id"])
    _create_index_if_missing(inspector, "member_profiles", "ix_member_profiles_current_team_id", ["current_team_id"])

    for table_name in (
        "wallet_ledger_entries",
        "withdrawal_requests",
        "wallet_bonus_grant_records",
        "recharge_repair_orders",
    ):
        for column in (
            sa.Column("owner_staff_id_snapshot", sa.String(length=128), nullable=True),
            sa.Column("supervisor_id_snapshot", sa.String(length=128), nullable=True),
            sa.Column("team_id_snapshot", sa.String(length=128), nullable=True),
            sa.Column("agency_id_snapshot", sa.String(length=36), nullable=True),
            sa.Column("site_id_snapshot", sa.String(length=36), nullable=True),
        ):
            _add_column_if_missing(inspector, table_name, column)
        _create_index_if_missing(inspector, table_name, f"ix_{table_name}_owner_staff_id_snapshot", ["owner_staff_id_snapshot"])
        _create_index_if_missing(inspector, table_name, f"ix_{table_name}_supervisor_id_snapshot", ["supervisor_id_snapshot"])
        _create_index_if_missing(inspector, table_name, f"ix_{table_name}_team_id_snapshot", ["team_id_snapshot"])
        _create_index_if_missing(inspector, table_name, f"ix_{table_name}_agency_id_snapshot", ["agency_id_snapshot"])
        _create_index_if_missing(inspector, table_name, f"ix_{table_name}_site_id_snapshot", ["site_id_snapshot"])

    for column in (
        sa.Column("gateway_node_id", sa.String(length=36), nullable=True),
        sa.Column("desired_gateway_config_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("actual_gateway_config_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("certificate_mode", sa.String(length=32), nullable=False, server_default="certbot_http01"),
        sa.Column("certificate_status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("certificate_expires_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("certificate_last_renewed_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("dns_target_type", sa.String(length=32), nullable=False, server_default="cname"),
        sa.Column("dns_expected_value", sa.String(length=255), nullable=True),
        sa.Column("dns_current_values_json", sa.JSON(), nullable=True),
        sa.Column("last_deploy_job_id", sa.String(length=36), nullable=True),
        sa.Column("last_verify_job_id", sa.String(length=36), nullable=True),
    ):
        _add_column_if_missing(inspector, "h5_site_configs", column)
    _create_index_if_missing(inspector, "h5_site_configs", "ix_h5_site_configs_gateway_node_id", ["gateway_node_id"])
    _create_index_if_missing(inspector, "h5_site_configs", "ix_h5_site_configs_last_deploy_job_id", ["last_deploy_job_id"])
    _create_index_if_missing(inspector, "h5_site_configs", "ix_h5_site_configs_last_verify_job_id", ["last_verify_job_id"])

    if _has_table(inspector, "h5_site_configs"):
        for column_name in ("desired_gateway_config_version", "actual_gateway_config_version", "certificate_mode", "certificate_status", "dns_target_type"):
            try:
                op.alter_column("h5_site_configs", column_name, server_default=None)
            except Exception:
                pass

    if not _has_table(inspector, "payment_reconciliation_items"):
        op.create_table(
            "payment_reconciliation_items",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("reconciliation_id", sa.String(length=36), sa.ForeignKey("payment_reconciliations.id"), nullable=False),
            sa.Column("channel_id", sa.String(length=64), nullable=False),
            sa.Column("item_type", sa.String(length=32), nullable=False),
            sa.Column("channel_order_no", sa.String(length=128), nullable=True),
            sa.Column("platform_order_no", sa.String(length=128), nullable=True),
            sa.Column("user_id", sa.String(length=36), sa.ForeignKey("app_users.id"), nullable=True),
            sa.Column("platform_amount", sa.Numeric(18, 2), nullable=True),
            sa.Column("channel_amount", sa.Numeric(18, 2), nullable=True),
            sa.Column("currency", sa.String(length=16), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="open"),
            sa.Column("repair_order_id", sa.String(length=36), nullable=True),
            sa.Column("raw_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.PrimaryKeyConstraint("id"),
        )
        _create_index_if_missing(inspector, "payment_reconciliation_items", "ix_payment_reconciliation_items_reconciliation_id", ["reconciliation_id"])
        _create_index_if_missing(inspector, "payment_reconciliation_items", "ix_payment_reconciliation_items_channel_id", ["channel_id"])
        _create_index_if_missing(inspector, "payment_reconciliation_items", "ix_payment_reconciliation_items_channel_order_no", ["channel_order_no"])
        _create_index_if_missing(inspector, "payment_reconciliation_items", "ix_payment_reconciliation_items_platform_order_no", ["platform_order_no"])
        _create_index_if_missing(inspector, "payment_reconciliation_items", "ix_payment_reconciliation_items_user_id", ["user_id"])
        _create_index_if_missing(inspector, "payment_reconciliation_items", "ix_payment_reconciliation_items_repair_order_id", ["repair_order_id"])

    if not _has_table(inspector, "site_whatsapp_phone_pools"):
        op.create_table(
            "site_whatsapp_phone_pools",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("account_id", sa.String(length=128), sa.ForeignKey("accounts.account_id"), nullable=False),
            sa.Column("site_id", sa.String(length=36), sa.ForeignKey("h5_sites.id"), nullable=False),
            sa.Column("waba_id", sa.String(length=128), nullable=False),
            sa.Column("phone_number_id", sa.String(length=128), nullable=False),
            sa.Column("display_phone_number", sa.String(length=64), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
            sa.Column("purpose_mode", sa.String(length=32), nullable=False, server_default="shared_auth_ai"),
            sa.Column("weight", sa.Integer(), nullable=False, server_default="100"),
            sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
            sa.Column("allow_new_users", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("allow_existing_users", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("only_existing_users", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("max_new_bindings_per_day", sa.Integer(), nullable=True),
            sa.Column("max_auth_sessions_per_hour", sa.Integer(), nullable=True),
            sa.Column("max_active_conversations", sa.Integer(), nullable=True),
            sa.Column("today_new_binding_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("today_auth_session_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("active_conversation_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("ready_for_webhook_delivery", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("ready_for_outbound_messages", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("webhook_runtime_status", sa.String(length=32), nullable=True),
            sa.Column("outbound_runtime_status", sa.String(length=32), nullable=True),
            sa.Column("quality_rating_snapshot", sa.String(length=32), nullable=True),
            sa.Column("phone_number_status_snapshot", sa.String(length=64), nullable=True),
            sa.Column("messaging_limit_tier_snapshot", sa.String(length=64), nullable=True),
            sa.Column("low_quality_stop_new_users", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("restricted_stop_allocation", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("last_webhook_at", sa.DateTime(timezone=False), nullable=True),
            sa.Column("last_outbound_at", sa.DateTime(timezone=False), nullable=True),
            sa.Column("last_error_at", sa.DateTime(timezone=False), nullable=True),
            sa.Column("last_error_message", sa.Text(), nullable=True),
            sa.Column("assigned_at", sa.DateTime(timezone=False), nullable=True),
            sa.Column("released_at", sa.DateTime(timezone=False), nullable=True),
            sa.Column("released_reason", sa.Text(), nullable=True),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing(inspector, "site_whatsapp_phone_pools", "ix_site_whatsapp_phone_pools_account_id", ["account_id"])
    _create_index_if_missing(inspector, "site_whatsapp_phone_pools", "ix_site_whatsapp_phone_pools_site_id", ["site_id"])
    _create_index_if_missing(inspector, "site_whatsapp_phone_pools", "ix_site_whatsapp_phone_pools_waba_id", ["waba_id"])
    _create_index_if_missing(inspector, "site_whatsapp_phone_pools", "ix_site_whatsapp_phone_pools_phone_number_id", ["phone_number_id"])
    _create_index_if_missing(inspector, "site_whatsapp_phone_pools", "ix_site_whatsapp_phone_pools_site_status", ["site_id", "status"])
    _create_index_if_missing(
        inspector,
        "site_whatsapp_phone_pools",
        "uq_site_whatsapp_phone_pools_phone_active",
        ["phone_number_id"],
        unique=True,
        sqlite_where=sa.text("status IN ('active','restricted','cooling_down')"),
        postgresql_where=sa.text("status IN ('active','restricted','cooling_down')"),
    )

    if not _has_table(inspector, "whatsapp_identities"):
        op.create_table(
            "whatsapp_identities",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("wa_id", sa.String(length=128), nullable=False),
            sa.Column("phone_number", sa.String(length=64), nullable=True),
            sa.Column("display_name", sa.String(length=128), nullable=True),
            sa.Column("account_id", sa.String(length=128), sa.ForeignKey("accounts.account_id"), nullable=False),
            sa.Column("site_id", sa.String(length=36), sa.ForeignKey("h5_sites.id"), nullable=False),
            sa.Column("user_id", sa.String(length=36), sa.ForeignKey("app_users.id"), nullable=False),
            sa.Column("member_profile_id", sa.String(length=36), sa.ForeignKey("member_profiles.id"), nullable=True),
            sa.Column("binding_status", sa.String(length=32), nullable=False, server_default="bound"),
            sa.Column("first_bound_phone_number_id", sa.String(length=128), nullable=True),
            sa.Column("current_assigned_phone_number_id", sa.String(length=128), nullable=True),
            sa.Column("bound_at", sa.DateTime(timezone=False), nullable=True),
            sa.Column("locked_at", sa.DateTime(timezone=False), nullable=True),
            sa.Column("unbound_at", sa.DateTime(timezone=False), nullable=True),
            sa.Column("first_seen_at", sa.DateTime(timezone=False), nullable=True),
            sa.Column("last_seen_at", sa.DateTime(timezone=False), nullable=True),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("wa_id", name="uq_whatsapp_identities_wa_id"),
        )
    _create_index_if_missing(inspector, "whatsapp_identities", "ix_whatsapp_identities_wa_id", ["wa_id"])
    _create_index_if_missing(inspector, "whatsapp_identities", "ix_whatsapp_identities_phone_number", ["phone_number"])
    _create_index_if_missing(inspector, "whatsapp_identities", "ix_whatsapp_identities_account_id", ["account_id"])
    _create_index_if_missing(inspector, "whatsapp_identities", "ix_whatsapp_identities_site_id", ["site_id"])
    _create_index_if_missing(inspector, "whatsapp_identities", "ix_whatsapp_identities_user_id", ["user_id"])
    _create_index_if_missing(inspector, "whatsapp_identities", "ix_whatsapp_identities_member_profile_id", ["member_profile_id"])
    _create_index_if_missing(inspector, "whatsapp_identities", "ix_whatsapp_identities_first_bound_phone_number_id", ["first_bound_phone_number_id"])
    _create_index_if_missing(inspector, "whatsapp_identities", "ix_whatsapp_identities_current_assigned_phone_number_id", ["current_assigned_phone_number_id"])
    _create_index_if_missing(
        inspector,
        "whatsapp_identities",
        "uq_whatsapp_identities_user_active",
        ["user_id"],
        unique=True,
        sqlite_where=sa.text("binding_status IN ('bound','locked')"),
        postgresql_where=sa.text("binding_status IN ('bound','locked')"),
    )

    if not _has_table(inspector, "user_whatsapp_service_assignments"):
        op.create_table(
            "user_whatsapp_service_assignments",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("account_id", sa.String(length=128), sa.ForeignKey("accounts.account_id"), nullable=False),
            sa.Column("site_id", sa.String(length=36), sa.ForeignKey("h5_sites.id"), nullable=False),
            sa.Column("user_id", sa.String(length=36), sa.ForeignKey("app_users.id"), nullable=False),
            sa.Column("wa_id", sa.String(length=128), nullable=False),
            sa.Column("assigned_waba_id", sa.String(length=128), nullable=False),
            sa.Column("assigned_phone_number_id", sa.String(length=128), nullable=False),
            sa.Column("assigned_display_phone_number", sa.String(length=64), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
            sa.Column("assignment_source", sa.String(length=32), nullable=False),
            sa.Column("assigned_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("migrated_at", sa.DateTime(timezone=False), nullable=True),
            sa.Column("migrated_from_phone_number_id", sa.String(length=128), nullable=True),
            sa.Column("migration_reason", sa.Text(), nullable=True),
            sa.Column("last_inbound_at", sa.DateTime(timezone=False), nullable=True),
            sa.Column("last_inbound_phone_number_id", sa.String(length=128), nullable=True),
            sa.Column("last_outbound_at", sa.DateTime(timezone=False), nullable=True),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.PrimaryKeyConstraint("id"),
        )
    for index_name, columns in (
        ("ix_user_whatsapp_service_assignments_account_id", ["account_id"]),
        ("ix_user_whatsapp_service_assignments_site_id", ["site_id"]),
        ("ix_user_whatsapp_service_assignments_user_id", ["user_id"]),
        ("ix_user_whatsapp_service_assignments_wa_id", ["wa_id"]),
        ("ix_user_whatsapp_service_assignments_assigned_waba_id", ["assigned_waba_id"]),
        ("ix_user_whatsapp_service_assignments_assigned_phone_number_id", ["assigned_phone_number_id"]),
        ("ix_user_whatsapp_service_assignments_last_inbound_phone_number_id", ["last_inbound_phone_number_id"]),
    ):
        _create_index_if_missing(inspector, "user_whatsapp_service_assignments", index_name, columns)
    _create_index_if_missing(
        inspector,
        "user_whatsapp_service_assignments",
        "uq_user_whatsapp_service_assignments_user_active",
        ["user_id"],
        unique=True,
        sqlite_where=sa.text("status = 'active'"),
        postgresql_where=sa.text("status = 'active'"),
    )
    _create_index_if_missing(
        inspector,
        "user_whatsapp_service_assignments",
        "uq_user_whatsapp_service_assignments_wa_active",
        ["wa_id"],
        unique=True,
        sqlite_where=sa.text("status = 'active'"),
        postgresql_where=sa.text("status = 'active'"),
    )

    if not _has_table(inspector, "whatsapp_auth_sessions"):
        op.create_table(
            "whatsapp_auth_sessions",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("account_id", sa.String(length=128), sa.ForeignKey("accounts.account_id"), nullable=False),
            sa.Column("site_id", sa.String(length=36), sa.ForeignKey("h5_sites.id"), nullable=False),
            sa.Column("user_id", sa.String(length=36), sa.ForeignKey("app_users.id"), nullable=True),
            sa.Column("session_type", sa.String(length=32), nullable=False),
            sa.Column("token_hash", sa.String(length=128), nullable=False),
            sa.Column("token_last4", sa.String(length=8), nullable=False),
            sa.Column("command_prefix", sa.String(length=32), nullable=False),
            sa.Column("selected_waba_id", sa.String(length=128), nullable=False),
            sa.Column("selected_phone_number_id", sa.String(length=128), nullable=False),
            sa.Column("selected_display_phone_number", sa.String(length=64), nullable=False),
            sa.Column("wa_link", sa.String(length=1024), nullable=False),
            sa.Column("command_text", sa.String(length=256), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
            sa.Column("wa_id", sa.String(length=128), nullable=True),
            sa.Column("inbound_message_id", sa.String(length=128), nullable=True),
            sa.Column("identity_id", sa.String(length=36), nullable=True),
            sa.Column("browser_session_id", sa.String(length=128), nullable=True),
            sa.Column("client_nonce_hash", sa.String(length=128), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=False), nullable=False),
            sa.Column("confirmed_at", sa.DateTime(timezone=False), nullable=True),
            sa.Column("consumed_at", sa.DateTime(timezone=False), nullable=True),
            sa.Column("failure_code", sa.String(length=64), nullable=True),
            sa.Column("failure_reason", sa.Text(), nullable=True),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("token_hash", name="uq_whatsapp_auth_sessions_token_hash"),
        )
    for index_name, columns in (
        ("ix_whatsapp_auth_sessions_account_id", ["account_id"]),
        ("ix_whatsapp_auth_sessions_site_id", ["site_id"]),
        ("ix_whatsapp_auth_sessions_user_id", ["user_id"]),
        ("ix_whatsapp_auth_sessions_token_hash", ["token_hash"]),
        ("ix_whatsapp_auth_sessions_selected_waba_id", ["selected_waba_id"]),
        ("ix_whatsapp_auth_sessions_selected_phone_number_id", ["selected_phone_number_id"]),
        ("ix_whatsapp_auth_sessions_wa_id", ["wa_id"]),
        ("ix_whatsapp_auth_sessions_inbound_message_id", ["inbound_message_id"]),
        ("ix_whatsapp_auth_sessions_identity_id", ["identity_id"]),
        ("ix_whatsapp_auth_sessions_browser_session_id", ["browser_session_id"]),
    ):
        _create_index_if_missing(inspector, "whatsapp_auth_sessions", index_name, columns)

    if not _has_table(inspector, "whatsapp_auto_bind_invites"):
        op.create_table(
            "whatsapp_auto_bind_invites",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("account_id", sa.String(length=128), sa.ForeignKey("accounts.account_id"), nullable=False),
            sa.Column("site_id", sa.String(length=36), sa.ForeignKey("h5_sites.id"), nullable=False),
            sa.Column("wa_id", sa.String(length=128), nullable=False),
            sa.Column("inbound_phone_number_id", sa.String(length=128), nullable=False),
            sa.Column("inbound_waba_id", sa.String(length=128), nullable=False),
            sa.Column("inbound_message_id", sa.String(length=128), nullable=True),
            sa.Column("token_hash", sa.String(length=128), nullable=False),
            sa.Column("token_last4", sa.String(length=8), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
            sa.Column("invite_link", sa.String(length=1024), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=False), nullable=False),
            sa.Column("consumed_at", sa.DateTime(timezone=False), nullable=True),
            sa.Column("user_id", sa.String(length=36), sa.ForeignKey("app_users.id"), nullable=True),
            sa.Column("failure_code", sa.String(length=64), nullable=True),
            sa.Column("failure_reason", sa.Text(), nullable=True),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("token_hash", name="uq_whatsapp_auto_bind_invites_token_hash"),
        )
    for index_name, columns in (
        ("ix_whatsapp_auto_bind_invites_account_id", ["account_id"]),
        ("ix_whatsapp_auto_bind_invites_site_id", ["site_id"]),
        ("ix_whatsapp_auto_bind_invites_wa_id", ["wa_id"]),
        ("ix_whatsapp_auto_bind_invites_inbound_phone_number_id", ["inbound_phone_number_id"]),
        ("ix_whatsapp_auto_bind_invites_inbound_waba_id", ["inbound_waba_id"]),
        ("ix_whatsapp_auto_bind_invites_inbound_message_id", ["inbound_message_id"]),
        ("ix_whatsapp_auto_bind_invites_token_hash", ["token_hash"]),
        ("ix_whatsapp_auto_bind_invites_user_id", ["user_id"]),
    ):
        _create_index_if_missing(inspector, "whatsapp_auto_bind_invites", index_name, columns)

    if not _has_table(inspector, "permission_grants"):
        op.create_table(
            "permission_grants",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("grantor_subject_type", sa.String(length=32), nullable=False),
            sa.Column("grantor_subject_id", sa.String(length=64), nullable=False),
            sa.Column("grantee_subject_type", sa.String(length=32), nullable=False),
            sa.Column("grantee_subject_id", sa.String(length=64), nullable=False),
            sa.Column("permission_code", sa.String(length=128), nullable=False),
            sa.Column("can_delegate", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("scope_type", sa.String(length=32), nullable=False, server_default="inherit"),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
            sa.Column("expires_at", sa.DateTime(timezone=False), nullable=True),
            sa.Column("created_by", sa.String(length=64), nullable=False),
            sa.Column("revoked_by", sa.String(length=64), nullable=True),
            sa.Column("revoked_at", sa.DateTime(timezone=False), nullable=True),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing(inspector, "permission_grants", "ix_permission_grants_permission_code", ["permission_code"])
    _create_index_if_missing(inspector, "permission_grants", "ix_permission_grants_grantee_status", ["grantee_subject_type", "grantee_subject_id", "status"])

    if not _has_table(inspector, "data_scope_grants"):
        op.create_table(
            "data_scope_grants",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("subject_type", sa.String(length=32), nullable=False),
            sa.Column("subject_id", sa.String(length=64), nullable=False),
            sa.Column("scope_type", sa.String(length=32), nullable=False),
            sa.Column("scope_id", sa.String(length=64), nullable=True),
            sa.Column("granted_by_subject_type", sa.String(length=32), nullable=False),
            sa.Column("granted_by_subject_id", sa.String(length=64), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
            sa.Column("revoked_at", sa.DateTime(timezone=False), nullable=True),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing(inspector, "data_scope_grants", "ix_data_scope_grants_scope_id", ["scope_id"])
    _create_index_if_missing(inspector, "data_scope_grants", "ix_data_scope_grants_subject_status", ["subject_type", "subject_id", "status"])

    if not _has_table(inspector, "staff_teams"):
        op.create_table(
            "staff_teams",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("agency_id", sa.String(length=36), sa.ForeignKey("agencies.id"), nullable=False),
            sa.Column("account_id", sa.String(length=128), sa.ForeignKey("accounts.account_id"), nullable=True),
            sa.Column("name", sa.String(length=128), nullable=False),
            sa.Column("supervisor_id", sa.String(length=64), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
            sa.Column("created_by", sa.String(length=64), nullable=False),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.PrimaryKeyConstraint("id"),
        )
    for index_name, columns in (
        ("ix_staff_teams_agency_id", ["agency_id"]),
        ("ix_staff_teams_account_id", ["account_id"]),
        ("ix_staff_teams_supervisor_id", ["supervisor_id"]),
        ("ix_staff_teams_agency_supervisor", ["agency_id", "supervisor_id"]),
    ):
        _create_index_if_missing(inspector, "staff_teams", index_name, columns)

    if not _has_table(inspector, "staff_team_assignments"):
        op.create_table(
            "staff_team_assignments",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("agency_id", sa.String(length=36), sa.ForeignKey("agencies.id"), nullable=False),
            sa.Column("team_id", sa.String(length=36), sa.ForeignKey("staff_teams.id"), nullable=False),
            sa.Column("staff_id", sa.String(length=64), nullable=False),
            sa.Column("supervisor_id", sa.String(length=64), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
            sa.Column("assigned_by", sa.String(length=64), nullable=False),
            sa.Column("assigned_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("ended_at", sa.DateTime(timezone=False), nullable=True),
            sa.Column("move_reason", sa.Text(), nullable=True),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.PrimaryKeyConstraint("id"),
        )
    for index_name, columns in (
        ("ix_staff_team_assignments_agency_id", ["agency_id"]),
        ("ix_staff_team_assignments_team_id", ["team_id"]),
        ("ix_staff_team_assignments_staff_id", ["staff_id"]),
        ("ix_staff_team_assignments_supervisor_id", ["supervisor_id"]),
    ):
        _create_index_if_missing(inspector, "staff_team_assignments", index_name, columns)
    _create_index_if_missing(
        inspector,
        "staff_team_assignments",
        "uq_staff_team_assignments_staff_active",
        ["agency_id", "staff_id"],
        unique=True,
        sqlite_where=sa.text("status = 'active'"),
        postgresql_where=sa.text("status = 'active'"),
    )

    if not _has_table(inspector, "customer_ownership_assignments"):
        op.create_table(
            "customer_ownership_assignments",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("customer_id", sa.String(length=36), sa.ForeignKey("app_users.id"), nullable=False),
            sa.Column("agency_id", sa.String(length=36), sa.ForeignKey("agencies.id"), nullable=False),
            sa.Column("account_id", sa.String(length=128), sa.ForeignKey("accounts.account_id"), nullable=True),
            sa.Column("site_id", sa.String(length=36), sa.ForeignKey("h5_sites.id"), nullable=True),
            sa.Column("owner_staff_id", sa.String(length=64), nullable=True),
            sa.Column("supervisor_id", sa.String(length=64), nullable=True),
            sa.Column("team_id", sa.String(length=64), nullable=True),
            sa.Column("assignment_type", sa.String(length=32), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
            sa.Column("assigned_by", sa.String(length=64), nullable=False),
            sa.Column("assigned_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("ended_at", sa.DateTime(timezone=False), nullable=True),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.PrimaryKeyConstraint("id"),
        )
    for index_name, columns in (
        ("ix_customer_ownership_assignments_customer_id", ["customer_id"]),
        ("ix_customer_ownership_assignments_agency_id", ["agency_id"]),
        ("ix_customer_ownership_assignments_account_id", ["account_id"]),
        ("ix_customer_ownership_assignments_site_id", ["site_id"]),
        ("ix_customer_ownership_assignments_owner_staff_id", ["owner_staff_id"]),
        ("ix_customer_ownership_assignments_supervisor_id", ["supervisor_id"]),
        ("ix_customer_ownership_assignments_team_id", ["team_id"]),
    ):
        _create_index_if_missing(inspector, "customer_ownership_assignments", index_name, columns)
    _create_index_if_missing(
        inspector,
        "customer_ownership_assignments",
        "uq_customer_ownership_assignments_customer_active",
        ["customer_id"],
        unique=True,
        sqlite_where=sa.text("status = 'active'"),
        postgresql_where=sa.text("status = 'active'"),
    )

    if not _has_table(inspector, "conversation_assignments"):
        op.create_table(
            "conversation_assignments",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("conversation_id", sa.String(length=36), sa.ForeignKey("conversations.id"), nullable=False),
            sa.Column("customer_id", sa.String(length=36), sa.ForeignKey("app_users.id"), nullable=False),
            sa.Column("agency_id", sa.String(length=36), sa.ForeignKey("agencies.id"), nullable=False),
            sa.Column("team_id", sa.String(length=64), nullable=True),
            sa.Column("supervisor_id", sa.String(length=64), nullable=True),
            sa.Column("assigned_staff_id", sa.String(length=64), nullable=True),
            sa.Column("assigned_queue_id", sa.String(length=36), nullable=True),
            sa.Column("assignment_type", sa.String(length=32), nullable=False),
            sa.Column("is_temporary", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
            sa.Column("assigned_by", sa.String(length=64), nullable=True),
            sa.Column("assigned_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("ended_at", sa.DateTime(timezone=False), nullable=True),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.PrimaryKeyConstraint("id"),
        )
    for index_name, columns in (
        ("ix_conversation_assignments_conversation_id", ["conversation_id"]),
        ("ix_conversation_assignments_customer_id", ["customer_id"]),
        ("ix_conversation_assignments_agency_id", ["agency_id"]),
        ("ix_conversation_assignments_team_id", ["team_id"]),
        ("ix_conversation_assignments_supervisor_id", ["supervisor_id"]),
        ("ix_conversation_assignments_assigned_staff_id", ["assigned_staff_id"]),
        ("ix_conversation_assignments_assigned_queue_id", ["assigned_queue_id"]),
    ):
        _create_index_if_missing(inspector, "conversation_assignments", index_name, columns)
    _create_index_if_missing(
        inspector,
        "conversation_assignments",
        "uq_conversation_assignments_conversation_active",
        ["conversation_id"],
        unique=True,
        sqlite_where=sa.text("status = 'active'"),
        postgresql_where=sa.text("status = 'active'"),
    )

    if not _has_table(inspector, "handover_queues"):
        op.create_table(
            "handover_queues",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("agency_id", sa.String(length=36), sa.ForeignKey("agencies.id"), nullable=False),
            sa.Column("team_id", sa.String(length=64), nullable=True),
            sa.Column("supervisor_id", sa.String(length=64), nullable=True),
            sa.Column("name", sa.String(length=128), nullable=False),
            sa.Column("strategy", sa.String(length=32), nullable=False, server_default="round_robin"),
            sa.Column("fallback_queue_id", sa.String(length=36), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.PrimaryKeyConstraint("id"),
        )
    for index_name, columns in (
        ("ix_handover_queues_agency_id", ["agency_id"]),
        ("ix_handover_queues_team_id", ["team_id"]),
        ("ix_handover_queues_supervisor_id", ["supervisor_id"]),
    ):
        _create_index_if_missing(inspector, "handover_queues", index_name, columns)

    if not _has_table(inspector, "ai_handover_policies"):
        op.create_table(
            "ai_handover_policies",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("agency_id", sa.String(length=36), sa.ForeignKey("agencies.id"), nullable=False),
            sa.Column("site_id", sa.String(length=36), sa.ForeignKey("h5_sites.id"), nullable=True),
            sa.Column("owner_first", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("require_online_owner", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("team_queue_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("agency_queue_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("max_wait_seconds_before_escalate", sa.Integer(), nullable=False, server_default="60"),
            sa.Column("fallback_action", sa.String(length=32), nullable=False, server_default="queue"),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing(inspector, "ai_handover_policies", "ix_ai_handover_policies_agency_id", ["agency_id"])
    _create_index_if_missing(inspector, "ai_handover_policies", "ix_ai_handover_policies_site_id", ["site_id"])

    if not _has_table(inspector, "h5_gateway_nodes"):
        op.create_table(
            "h5_gateway_nodes",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("name", sa.String(length=128), nullable=False),
            sa.Column("node_code", sa.String(length=64), nullable=False),
            sa.Column("public_ip", sa.String(length=64), nullable=True),
            sa.Column("private_ip", sa.String(length=64), nullable=True),
            sa.Column("region", sa.String(length=64), nullable=True),
            sa.Column("ssh_host", sa.String(length=255), nullable=True),
            sa.Column("ssh_port", sa.Integer(), nullable=False, server_default="22"),
            sa.Column("ssh_user", sa.String(length=64), nullable=True),
            sa.Column("ssh_credential_id", sa.String(length=36), nullable=True),
            sa.Column("agent_base_url", sa.String(length=512), nullable=True),
            sa.Column("agent_token_hash", sa.String(length=128), nullable=True),
            sa.Column("agent_mode", sa.String(length=32), nullable=False, server_default="pull"),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
            sa.Column("desired_config_version", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("actual_config_version", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("desired_frontend_version", sa.String(length=64), nullable=True),
            sa.Column("actual_frontend_version", sa.String(length=64), nullable=True),
            sa.Column("nginx_status", sa.String(length=32), nullable=True),
            sa.Column("agent_status", sa.String(length=32), nullable=True),
            sa.Column("firewall_status", sa.String(length=32), nullable=True),
            sa.Column("certbot_status", sa.String(length=32), nullable=True),
            sa.Column("last_heartbeat_at", sa.DateTime(timezone=False), nullable=True),
            sa.Column("last_health_check_at", sa.DateTime(timezone=False), nullable=True),
            sa.Column("cpu_usage_percent", sa.Numeric(5, 2), nullable=True),
            sa.Column("memory_usage_percent", sa.Numeric(5, 2), nullable=True),
            sa.Column("disk_usage_percent", sa.Numeric(5, 2), nullable=True),
            sa.Column("load_average", sa.String(length=64), nullable=True),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("node_code", name="uq_h5_gateway_nodes_node_code"),
        )
    for index_name, columns in (
        ("ix_h5_gateway_nodes_node_code", ["node_code"]),
        ("ix_h5_gateway_nodes_ssh_credential_id", ["ssh_credential_id"]),
    ):
        _create_index_if_missing(inspector, "h5_gateway_nodes", index_name, columns)

    if not _has_table(inspector, "h5_gateway_credentials"):
        op.create_table(
            "h5_gateway_credentials",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("name", sa.String(length=128), nullable=False),
            sa.Column("credential_type", sa.String(length=32), nullable=False),
            sa.Column("encrypted_secret", sa.Text(), nullable=False),
            sa.Column("secret_last4", sa.String(length=8), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
            sa.Column("created_by", sa.String(length=64), nullable=False),
            sa.Column("rotated_at", sa.DateTime(timezone=False), nullable=True),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _has_table(inspector, "h5_gateway_jobs"):
        op.create_table(
            "h5_gateway_jobs",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("node_id", sa.String(length=36), sa.ForeignKey("h5_gateway_nodes.id"), nullable=False),
            sa.Column("job_type", sa.String(length=64), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
            sa.Column("trigger_source", sa.String(length=32), nullable=False, server_default="manual"),
            sa.Column("requested_by", sa.String(length=64), nullable=True),
            sa.Column("idempotency_key", sa.String(length=128), nullable=True),
            sa.Column("input_json", sa.JSON(), nullable=True),
            sa.Column("result_json", sa.JSON(), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=False), nullable=True),
            sa.Column("finished_at", sa.DateTime(timezone=False), nullable=True),
            sa.Column("failure_code", sa.String(length=128), nullable=True),
            sa.Column("failure_message", sa.Text(), nullable=True),
            sa.Column("lock_key", sa.String(length=128), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("idempotency_key", name="uq_h5_gateway_jobs_idempotency_key"),
        )
    for index_name, columns in (
        ("ix_h5_gateway_jobs_node_id", ["node_id"]),
        ("ix_h5_gateway_jobs_job_type", ["job_type"]),
        ("ix_h5_gateway_jobs_idempotency_key", ["idempotency_key"]),
        ("ix_h5_gateway_jobs_lock_key", ["lock_key"]),
    ):
        _create_index_if_missing(inspector, "h5_gateway_jobs", index_name, columns)

    if not _has_table(inspector, "h5_gateway_job_steps"):
        op.create_table(
            "h5_gateway_job_steps",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("job_id", sa.String(length=36), sa.ForeignKey("h5_gateway_jobs.id"), nullable=False),
            sa.Column("node_id", sa.String(length=36), sa.ForeignKey("h5_gateway_nodes.id"), nullable=False),
            sa.Column("step_name", sa.String(length=128), nullable=False),
            sa.Column("command_name", sa.String(length=128), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
            sa.Column("started_at", sa.DateTime(timezone=False), nullable=True),
            sa.Column("finished_at", sa.DateTime(timezone=False), nullable=True),
            sa.Column("exit_code", sa.Integer(), nullable=True),
            sa.Column("stdout_tail", sa.Text(), nullable=True),
            sa.Column("stderr_tail", sa.Text(), nullable=True),
            sa.Column("result_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing(inspector, "h5_gateway_job_steps", "ix_h5_gateway_job_steps_job_id", ["job_id"])
    _create_index_if_missing(inspector, "h5_gateway_job_steps", "ix_h5_gateway_job_steps_node_id", ["node_id"])

    if not _has_table(inspector, "h5_frontend_releases"):
        op.create_table(
            "h5_frontend_releases",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("version", sa.String(length=64), nullable=False),
            sa.Column("artifact_url", sa.String(length=1024), nullable=False),
            sa.Column("artifact_sha256", sa.String(length=128), nullable=False),
            sa.Column("build_commit", sa.String(length=64), nullable=True),
            sa.Column("build_time", sa.DateTime(timezone=False), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("version", name="uq_h5_frontend_releases_version"),
        )
    _create_index_if_missing(inspector, "h5_frontend_releases", "ix_h5_frontend_releases_version", ["version"])

    if not _has_table(inspector, "h5_gateway_node_releases"):
        op.create_table(
            "h5_gateway_node_releases",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("node_id", sa.String(length=36), sa.ForeignKey("h5_gateway_nodes.id"), nullable=False),
            sa.Column("release_id", sa.String(length=36), sa.ForeignKey("h5_frontend_releases.id"), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="deployed"),
            sa.Column("deployed_at", sa.DateTime(timezone=False), nullable=True),
            sa.Column("deployed_by", sa.String(length=64), nullable=True),
            sa.Column("previous_release_id", sa.String(length=36), nullable=True),
            sa.Column("rollback_at", sa.DateTime(timezone=False), nullable=True),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing(inspector, "h5_gateway_node_releases", "ix_h5_gateway_node_releases_node_id", ["node_id"])
    _create_index_if_missing(inspector, "h5_gateway_node_releases", "ix_h5_gateway_node_releases_release_id", ["release_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for table_name in (
        "h5_gateway_node_releases",
        "h5_frontend_releases",
        "h5_gateway_job_steps",
        "h5_gateway_jobs",
        "h5_gateway_credentials",
        "h5_gateway_nodes",
        "ai_handover_policies",
        "handover_queues",
        "conversation_assignments",
        "customer_ownership_assignments",
        "staff_team_assignments",
        "staff_teams",
        "data_scope_grants",
        "permission_grants",
        "whatsapp_auto_bind_invites",
        "whatsapp_auth_sessions",
        "user_whatsapp_service_assignments",
        "whatsapp_identities",
        "site_whatsapp_phone_pools",
        "payment_reconciliation_items",
    ):
        if _has_table(inspector, table_name):
            op.drop_table(table_name)

    for table_name, index_names in (
        (
            "h5_site_configs",
            [
                "ix_h5_site_configs_last_verify_job_id",
                "ix_h5_site_configs_last_deploy_job_id",
                "ix_h5_site_configs_gateway_node_id",
            ],
        ),
        (
            "recharge_repair_orders",
            [
                "ix_recharge_repair_orders_site_id_snapshot",
                "ix_recharge_repair_orders_agency_id_snapshot",
                "ix_recharge_repair_orders_team_id_snapshot",
                "ix_recharge_repair_orders_supervisor_id_snapshot",
                "ix_recharge_repair_orders_owner_staff_id_snapshot",
            ],
        ),
        (
            "wallet_bonus_grant_records",
            [
                "ix_wallet_bonus_grant_records_site_id_snapshot",
                "ix_wallet_bonus_grant_records_agency_id_snapshot",
                "ix_wallet_bonus_grant_records_team_id_snapshot",
                "ix_wallet_bonus_grant_records_supervisor_id_snapshot",
                "ix_wallet_bonus_grant_records_owner_staff_id_snapshot",
            ],
        ),
        (
            "withdrawal_requests",
            [
                "ix_withdrawal_requests_site_id_snapshot",
                "ix_withdrawal_requests_agency_id_snapshot",
                "ix_withdrawal_requests_team_id_snapshot",
                "ix_withdrawal_requests_supervisor_id_snapshot",
                "ix_withdrawal_requests_owner_staff_id_snapshot",
            ],
        ),
        (
            "wallet_ledger_entries",
            [
                "ix_wallet_ledger_entries_site_id_snapshot",
                "ix_wallet_ledger_entries_agency_id_snapshot",
                "ix_wallet_ledger_entries_team_id_snapshot",
                "ix_wallet_ledger_entries_supervisor_id_snapshot",
                "ix_wallet_ledger_entries_owner_staff_id_snapshot",
            ],
        ),
        (
            "member_profiles",
            [
                "ix_member_profiles_current_team_id",
                "ix_member_profiles_current_supervisor_id",
            ],
        ),
    ):
        if _has_table(inspector, table_name):
            for index_name in index_names:
                _drop_index_if_exists(inspector, table_name, index_name)

    for table_name, columns in (
        ("h5_site_configs", ["last_verify_job_id", "last_deploy_job_id", "dns_current_values_json", "dns_expected_value", "dns_target_type", "certificate_last_renewed_at", "certificate_expires_at", "certificate_status", "certificate_mode", "actual_gateway_config_version", "desired_gateway_config_version", "gateway_node_id"]),
        ("recharge_repair_orders", ["site_id_snapshot", "agency_id_snapshot", "team_id_snapshot", "supervisor_id_snapshot", "owner_staff_id_snapshot"]),
        ("wallet_bonus_grant_records", ["site_id_snapshot", "agency_id_snapshot", "team_id_snapshot", "supervisor_id_snapshot", "owner_staff_id_snapshot"]),
        ("withdrawal_requests", ["site_id_snapshot", "agency_id_snapshot", "team_id_snapshot", "supervisor_id_snapshot", "owner_staff_id_snapshot"]),
        ("wallet_ledger_entries", ["site_id_snapshot", "agency_id_snapshot", "team_id_snapshot", "supervisor_id_snapshot", "owner_staff_id_snapshot"]),
        ("member_profiles", ["owner_source", "owner_assigned_by", "current_team_id", "current_supervisor_id"]),
    ):
        if _has_table(inspector, table_name):
            existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
            for column_name in columns:
                if column_name in existing_columns:
                    op.drop_column(table_name, column_name)
