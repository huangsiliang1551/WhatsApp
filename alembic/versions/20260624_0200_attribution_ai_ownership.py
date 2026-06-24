"""Add customer attribution / AI ownership / entry link tables and snapshot columns.

Implements whatsapp_attribution_ai_implementation_spec.md section 5:
- New tables: entry_links, ai_agents, member_owner_assignments, member_ai_assignments,
  conversation_ai_assignments, member_owner_transfer_batches/items,
  member_ai_transfer_batches/items, ai_failover_events, ownership_audit_events,
  ai_outbound_jobs.
- Extend member_profiles, conversations, messages, h5_sites with current/snapshot fields.

All new columns on existing tables are nullable to stay backward compatible.
Backfill of current_* attribution is performed by a separate idempotent service
(spec 15.2-15.4); this migration only creates structure.

Revision ID: 20260624_0200
Revises: 20260623_0108
Create Date: 2026-06-24 02:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op


revision: str = "20260624_0200"
down_revision: str | Sequence[str] | None = "20260623_0108"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── ai_agents（先建，entry_links 引用它） ──
    op.create_table(
        "ai_agents",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("account_id", sa.String(length=128), sa.ForeignKey("accounts.account_id"), nullable=False),
        sa.Column("agency_id", sa.String(length=36), sa.ForeignKey("agencies.id"), nullable=True),
        sa.Column("site_id", sa.String(length=36), sa.ForeignKey("h5_sites.id"), nullable=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("provider_name", sa.String(length=64), nullable=False, server_default="openai"),
        sa.Column("model_name", sa.String(length=128), nullable=False, server_default="gpt-4o-mini"),
        sa.Column("prompt_version", sa.String(length=64), nullable=True),
        sa.Column("system_prompt", sa.Text(), nullable=True),
        sa.Column("waba_id", sa.String(length=128), nullable=True),
        sa.Column("phone_number_id", sa.String(length=128), nullable=True),
        sa.Column("owning_staff_user_id", sa.String(length=128), nullable=True),
        sa.Column("owning_agency_member_id", sa.String(length=128), nullable=True),
        sa.Column("fallback_staff_user_id", sa.String(length=128), nullable=True),
        sa.Column("fallback_agency_member_id", sa.String(length=128), nullable=True),
        sa.Column("fallback_ai_agent_id", sa.String(length=36), sa.ForeignKey("ai_agents.id"), nullable=True),
        sa.Column("default_entry_link_id", sa.String(length=36), nullable=True),
        sa.Column("auto_reply_enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("proactive_send_enabled", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("health_status", sa.String(length=32), nullable=False, server_default="healthy"),
        sa.Column("last_health_check_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_ai_agents_account_site", "ai_agents", ["account_id", "site_id"])
    op.create_index("ix_ai_agents_status", "ai_agents", ["status"])

    # ── entry_links ──
    op.create_table(
        "entry_links",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("account_id", sa.String(length=128), sa.ForeignKey("accounts.account_id"), nullable=False),
        sa.Column("agency_id", sa.String(length=36), sa.ForeignKey("agencies.id"), nullable=True),
        sa.Column("site_id", sa.String(length=36), sa.ForeignKey("h5_sites.id"), nullable=True),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("link_type", sa.String(length=32), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False, server_default="h5"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("target_staff_user_id", sa.String(length=128), nullable=True),
        sa.Column("target_agency_member_id", sa.String(length=128), nullable=True),
        sa.Column("target_ai_agent_id", sa.String(length=36), sa.ForeignKey("ai_agents.id"), nullable=True),
        sa.Column("referrer_user_id", sa.String(length=36), sa.ForeignKey("app_users.id"), nullable=True),
        sa.Column("waba_id", sa.String(length=128), nullable=True),
        sa.Column("phone_number_id", sa.String(length=128), nullable=True),
        sa.Column("whatsapp_phone_number", sa.String(length=64), nullable=True),
        sa.Column("usage_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("usage_limit", sa.Integer(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("created_by_actor_id", sa.String(length=128), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("code", name="uq_entry_links_code"),
    )
    op.create_index("ix_entry_links_account_id", "entry_links", ["account_id"])
    op.create_index("ix_entry_links_site_type", "entry_links", ["site_id", "link_type"])
    op.create_index("ix_entry_links_target", "entry_links", ["target_type", "target_staff_user_id", "target_ai_agent_id"])

    # ── member_owner_transfer_batches（先于 assignments，因 assignments FK 它） ──
    op.create_table(
        "member_owner_transfer_batches",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("account_id", sa.String(length=128), sa.ForeignKey("accounts.account_id"), nullable=False),
        sa.Column("agency_id", sa.String(length=36), sa.ForeignKey("agencies.id"), nullable=True),
        sa.Column("site_id", sa.String(length=36), sa.ForeignKey("h5_sites.id"), nullable=True),
        sa.Column("from_staff_user_id", sa.String(length=128), nullable=False),
        sa.Column("to_staff_user_id", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="completed"),
        sa.Column("total_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("dry_run", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("changed_by_actor_id", sa.String(length=128), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_member_owner_transfer_batches_account_id", "member_owner_transfer_batches", ["account_id"])

    op.create_table(
        "member_owner_transfer_items",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("batch_id", sa.String(length=36), sa.ForeignKey("member_owner_transfer_batches.id"), nullable=False),
        sa.Column("member_profile_id", sa.String(length=36), sa.ForeignKey("member_profiles.id"), nullable=False),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("app_users.id"), nullable=False),
        sa.Column("from_staff_user_id", sa.String(length=128), nullable=False),
        sa.Column("to_staff_user_id", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="transferred"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_member_owner_transfer_items_batch", "member_owner_transfer_items", ["batch_id"])
    op.create_index("ix_member_owner_transfer_items_member_profile_id", "member_owner_transfer_items", ["member_profile_id"])

    # ── member_ai_transfer_batches ──
    op.create_table(
        "member_ai_transfer_batches",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("account_id", sa.String(length=128), sa.ForeignKey("accounts.account_id"), nullable=False),
        sa.Column("agency_id", sa.String(length=36), sa.ForeignKey("agencies.id"), nullable=True),
        sa.Column("site_id", sa.String(length=36), sa.ForeignKey("h5_sites.id"), nullable=True),
        sa.Column("from_ai_agent_id", sa.String(length=36), sa.ForeignKey("ai_agents.id"), nullable=False),
        sa.Column("to_ai_agent_id", sa.String(length=36), sa.ForeignKey("ai_agents.id"), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="completed"),
        sa.Column("total_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("include_open_conversations", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("dry_run", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("changed_by_actor_id", sa.String(length=128), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_member_ai_transfer_batches_account_id", "member_ai_transfer_batches", ["account_id"])

    op.create_table(
        "member_ai_transfer_items",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("batch_id", sa.String(length=36), sa.ForeignKey("member_ai_transfer_batches.id"), nullable=False),
        sa.Column("member_profile_id", sa.String(length=36), sa.ForeignKey("member_profiles.id"), nullable=False),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("app_users.id"), nullable=False),
        sa.Column("from_ai_agent_id", sa.String(length=36), sa.ForeignKey("ai_agents.id"), nullable=False),
        sa.Column("to_ai_agent_id", sa.String(length=36), sa.ForeignKey("ai_agents.id"), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="transferred"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_member_ai_transfer_items_batch", "member_ai_transfer_items", ["batch_id"])
    op.create_index("ix_member_ai_transfer_items_member_profile_id", "member_ai_transfer_items", ["member_profile_id"])

    # ── member_owner_assignments ──
    op.create_table(
        "member_owner_assignments",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("account_id", sa.String(length=128), sa.ForeignKey("accounts.account_id"), nullable=False),
        sa.Column("agency_id", sa.String(length=36), sa.ForeignKey("agencies.id"), nullable=True),
        sa.Column("site_id", sa.String(length=36), sa.ForeignKey("h5_sites.id"), nullable=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("app_users.id"), nullable=False),
        sa.Column("member_profile_id", sa.String(length=36), sa.ForeignKey("member_profiles.id"), nullable=False),
        sa.Column("owner_staff_user_id", sa.String(length=128), nullable=False),
        sa.Column("owner_agency_member_id", sa.String(length=128), nullable=True),
        sa.Column("source_type", sa.String(length=48), nullable=False),
        sa.Column("source_entry_link_id", sa.String(length=36), sa.ForeignKey("entry_links.id"), nullable=True),
        sa.Column("source_invite_code", sa.String(length=64), nullable=True),
        sa.Column("source_referrer_user_id", sa.String(length=36), sa.ForeignKey("app_users.id"), nullable=True),
        sa.Column("assigned_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("ended_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("changed_by_actor_id", sa.String(length=128), nullable=True),
        sa.Column("transfer_batch_id", sa.String(length=36), sa.ForeignKey("member_owner_transfer_batches.id"), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_member_owner_assignments_account_id", "member_owner_assignments", ["account_id"])
    op.create_index("ix_member_owner_assignments_current", "member_owner_assignments", ["account_id", "user_id", "is_current"])
    op.create_index("ix_member_owner_assignments_staff", "member_owner_assignments", ["owner_staff_user_id", "is_current"])

    # ── member_ai_assignments ──
    op.create_table(
        "member_ai_assignments",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("account_id", sa.String(length=128), sa.ForeignKey("accounts.account_id"), nullable=False),
        sa.Column("agency_id", sa.String(length=36), sa.ForeignKey("agencies.id"), nullable=True),
        sa.Column("site_id", sa.String(length=36), sa.ForeignKey("h5_sites.id"), nullable=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("app_users.id"), nullable=False),
        sa.Column("member_profile_id", sa.String(length=36), sa.ForeignKey("member_profiles.id"), nullable=False),
        sa.Column("ai_agent_id", sa.String(length=36), sa.ForeignKey("ai_agents.id"), nullable=False),
        sa.Column("source_type", sa.String(length=48), nullable=False),
        sa.Column("source_entry_link_id", sa.String(length=36), sa.ForeignKey("entry_links.id"), nullable=True),
        sa.Column("source_invite_code", sa.String(length=64), nullable=True),
        sa.Column("source_referrer_user_id", sa.String(length=36), sa.ForeignKey("app_users.id"), nullable=True),
        sa.Column("assigned_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("ended_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("changed_by_actor_id", sa.String(length=128), nullable=True),
        sa.Column("transfer_batch_id", sa.String(length=36), sa.ForeignKey("member_ai_transfer_batches.id"), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_member_ai_assignments_account_id", "member_ai_assignments", ["account_id"])
    op.create_index("ix_member_ai_assignments_current", "member_ai_assignments", ["account_id", "user_id", "is_current"])
    op.create_index("ix_member_ai_assignments_agent", "member_ai_assignments", ["ai_agent_id", "is_current"])

    # ── conversation_ai_assignments ──
    op.create_table(
        "conversation_ai_assignments",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("account_id", sa.String(length=128), sa.ForeignKey("accounts.account_id"), nullable=False),
        sa.Column("conversation_id", sa.String(length=36), sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column("waba_id", sa.String(length=128), nullable=True),
        sa.Column("phone_number_id", sa.String(length=128), nullable=True),
        sa.Column("customer_wa_id", sa.String(length=128), nullable=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("app_users.id"), nullable=True),
        sa.Column("member_profile_id", sa.String(length=36), sa.ForeignKey("member_profiles.id"), nullable=True),
        sa.Column("bound_ai_agent_id", sa.String(length=36), sa.ForeignKey("ai_agents.id"), nullable=True),
        sa.Column("actual_ai_agent_id", sa.String(length=36), sa.ForeignKey("ai_agents.id"), nullable=False),
        sa.Column("source_type", sa.String(length=48), nullable=False),
        sa.Column("source_entry_link_id", sa.String(length=36), sa.ForeignKey("entry_links.id"), nullable=True),
        sa.Column("source_invite_code", sa.String(length=64), nullable=True),
        sa.Column("failover_from_ai_agent_id", sa.String(length=36), sa.ForeignKey("ai_agents.id"), nullable=True),
        sa.Column("failover_reason", sa.String(length=128), nullable=True),
        sa.Column("assigned_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("ended_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("changed_by_actor_id", sa.String(length=128), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_conversation_ai_assignments_account_id", "conversation_ai_assignments", ["account_id"])
    op.create_index("ix_conversation_ai_assignments_current", "conversation_ai_assignments", ["account_id", "conversation_id", "is_current"])
    op.create_index("ix_conversation_ai_assignments_agent", "conversation_ai_assignments", ["actual_ai_agent_id", "is_current"])

    # ── ai_failover_events ──
    op.create_table(
        "ai_failover_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("account_id", sa.String(length=128), sa.ForeignKey("accounts.account_id"), nullable=False),
        sa.Column("agency_id", sa.String(length=36), sa.ForeignKey("agencies.id"), nullable=True),
        sa.Column("site_id", sa.String(length=36), sa.ForeignKey("h5_sites.id"), nullable=True),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("from_ai_agent_id", sa.String(length=36), sa.ForeignKey("ai_agents.id"), nullable=True),
        sa.Column("to_ai_agent_id", sa.String(length=36), sa.ForeignKey("ai_agents.id"), nullable=True),
        sa.Column("conversation_id", sa.String(length=36), sa.ForeignKey("conversations.id"), nullable=True),
        sa.Column("member_profile_id", sa.String(length=36), sa.ForeignKey("member_profiles.id"), nullable=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("app_users.id"), nullable=True),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("affected_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("changed_by_actor_id", sa.String(length=128), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_ai_failover_events_account_id", "ai_failover_events", ["account_id"])
    op.create_index("ix_ai_failover_events_agent", "ai_failover_events", ["from_ai_agent_id", "to_ai_agent_id", "event_type"])

    # ── ownership_audit_events ──
    op.create_table(
        "ownership_audit_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("account_id", sa.String(length=128), sa.ForeignKey("accounts.account_id"), nullable=True),
        sa.Column("agency_id", sa.String(length=36), sa.ForeignKey("agencies.id"), nullable=True),
        sa.Column("site_id", sa.String(length=36), sa.ForeignKey("h5_sites.id"), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=48), nullable=False),
        sa.Column("target_id", sa.String(length=128), nullable=False),
        sa.Column("actor_type", sa.String(length=32), nullable=False, server_default="system"),
        sa.Column("actor_id", sa.String(length=128), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_ownership_audit_events_target", "ownership_audit_events", ["target_type", "target_id"])
    op.create_index("ix_ownership_audit_events_action", "ownership_audit_events", ["action", "created_at"])

    # ── ai_outbound_jobs ──
    op.create_table(
        "ai_outbound_jobs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("account_id", sa.String(length=128), sa.ForeignKey("accounts.account_id"), nullable=False),
        sa.Column("agency_id", sa.String(length=36), sa.ForeignKey("agencies.id"), nullable=True),
        sa.Column("site_id", sa.String(length=36), sa.ForeignKey("h5_sites.id"), nullable=True),
        sa.Column("ai_agent_id", sa.String(length=36), sa.ForeignKey("ai_agents.id"), nullable=False),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("app_users.id"), nullable=True),
        sa.Column("member_profile_id", sa.String(length=36), sa.ForeignKey("member_profiles.id"), nullable=True),
        sa.Column("conversation_id", sa.String(length=36), sa.ForeignKey("conversations.id"), nullable=True),
        sa.Column("waba_id", sa.String(length=128), nullable=True),
        sa.Column("phone_number_id", sa.String(length=128), nullable=True),
        sa.Column("recipient_wa_id", sa.String(length=128), nullable=True),
        sa.Column("trigger_type", sa.String(length=48), nullable=False),
        sa.Column("message_policy", sa.String(length=32), nullable=False, server_default="service_window"),
        sa.Column("template_id", sa.String(length=36), sa.ForeignKey("message_templates.id"), nullable=True),
        sa.Column("template_name", sa.String(length=255), nullable=True),
        sa.Column("template_language", sa.String(length=32), nullable=True),
        sa.Column("generated_text", sa.Text(), nullable=True),
        sa.Column("send_payload_json", sa.JSON(), nullable=True),
        sa.Column("source_entry_link_id", sa.String(length=36), sa.ForeignKey("entry_links.id"), nullable=True),
        sa.Column("owner_agency_id_snapshot", sa.String(length=128), nullable=True),
        sa.Column("owner_staff_user_id_snapshot", sa.String(length=128), nullable=True),
        sa.Column("owner_agency_member_id_snapshot", sa.String(length=128), nullable=True),
        sa.Column("owner_assignment_id_snapshot", sa.String(length=36), nullable=True),
        sa.Column("ai_assignment_id_snapshot", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("scheduled_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("provider_message_id", sa.String(length=255), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_ai_outbound_jobs_account_id", "ai_outbound_jobs", ["account_id"])
    op.create_index("ix_ai_outbound_jobs_status", "ai_outbound_jobs", ["status", "scheduled_at"])
    op.create_index("ix_ai_outbound_jobs_agent", "ai_outbound_jobs", ["ai_agent_id", "status"])

    # ── 扩展现有表：member_profiles ──
    op.add_column("member_profiles", sa.Column("current_owner_agency_id", sa.String(length=128), nullable=True))
    op.add_column("member_profiles", sa.Column("current_owner_staff_user_id", sa.String(length=128), nullable=True))
    op.add_column("member_profiles", sa.Column("current_owner_agency_member_id", sa.String(length=128), nullable=True))
    op.add_column("member_profiles", sa.Column("current_owner_assignment_id", sa.String(length=36), nullable=True))
    op.add_column("member_profiles", sa.Column("owner_assigned_at", sa.DateTime(timezone=False), nullable=True))
    op.add_column("member_profiles", sa.Column("current_ai_agent_id", sa.String(length=36), nullable=True))
    op.add_column("member_profiles", sa.Column("current_ai_assignment_id", sa.String(length=36), nullable=True))
    op.add_column("member_profiles", sa.Column("ai_assigned_at", sa.DateTime(timezone=False), nullable=True))
    op.add_column("member_profiles", sa.Column("registration_entry_link_id", sa.String(length=36), nullable=True))
    op.add_column("member_profiles", sa.Column("registration_ai_agent_id", sa.String(length=36), nullable=True))
    op.add_column("member_profiles", sa.Column("registration_staff_user_id", sa.String(length=128), nullable=True))
    op.add_column("member_profiles", sa.Column("registration_channel", sa.String(length=32), nullable=True))
    op.add_column("member_profiles", sa.Column("registration_source_type", sa.String(length=48), nullable=True))
    op.add_column("member_profiles", sa.Column("attribution_status", sa.String(length=32), nullable=False, server_default="unattributed"))
    op.create_index("ix_member_profiles_current_owner_staff_user_id", "member_profiles", ["current_owner_staff_user_id"])
    op.create_index("ix_member_profiles_current_ai_agent_id", "member_profiles", ["current_ai_agent_id"])
    op.create_index("ix_member_profiles_registration_entry_link_id", "member_profiles", ["registration_entry_link_id"])
    op.create_index("ix_member_profiles_attribution_status", "member_profiles", ["attribution_status"])

    # ── 扩展 conversations ──
    op.add_column("conversations", sa.Column("current_ai_agent_id", sa.String(length=36), nullable=True))
    op.add_column("conversations", sa.Column("current_ai_assignment_id", sa.String(length=36), nullable=True))
    op.add_column("conversations", sa.Column("current_entry_link_id", sa.String(length=36), nullable=True))
    op.add_column("conversations", sa.Column("current_owner_agency_id_snapshot", sa.String(length=128), nullable=True))
    op.add_column("conversations", sa.Column("current_owner_staff_user_id_snapshot", sa.String(length=128), nullable=True))
    op.add_column("conversations", sa.Column("current_owner_agency_member_id_snapshot", sa.String(length=128), nullable=True))
    op.add_column("conversations", sa.Column("current_owner_assignment_id_snapshot", sa.String(length=36), nullable=True))
    op.add_column("conversations", sa.Column("ai_failover_active", sa.Boolean(), nullable=False, server_default=sa.text("0")))
    op.add_column("conversations", sa.Column("ai_failover_from_agent_id", sa.String(length=36), nullable=True))
    op.add_column("conversations", sa.Column("ai_failover_reason", sa.String(length=255), nullable=True))
    op.create_index("ix_conversations_current_ai_agent_id", "conversations", ["current_ai_agent_id"])
    op.create_index("ix_conversations_current_entry_link_id", "conversations", ["current_entry_link_id"])

    # ── 扩展 messages ──
    op.add_column("messages", sa.Column("actor_type", sa.String(length=32), nullable=True))
    op.add_column("messages", sa.Column("actor_id", sa.String(length=128), nullable=True))
    op.add_column("messages", sa.Column("ai_agent_id", sa.String(length=36), nullable=True))
    op.add_column("messages", sa.Column("ai_assignment_id_snapshot", sa.String(length=36), nullable=True))
    op.add_column("messages", sa.Column("ai_provider", sa.String(length=64), nullable=True))
    op.add_column("messages", sa.Column("ai_model", sa.String(length=128), nullable=True))
    op.add_column("messages", sa.Column("ai_prompt_version", sa.String(length=64), nullable=True))
    op.add_column("messages", sa.Column("source_entry_link_id_snapshot", sa.String(length=36), nullable=True))
    op.add_column("messages", sa.Column("owner_agency_id_snapshot", sa.String(length=128), nullable=True))
    op.add_column("messages", sa.Column("owner_staff_user_id_snapshot", sa.String(length=128), nullable=True))
    op.add_column("messages", sa.Column("owner_agency_member_id_snapshot", sa.String(length=128), nullable=True))
    op.add_column("messages", sa.Column("owner_assignment_id_snapshot", sa.String(length=36), nullable=True))
    op.add_column("messages", sa.Column("source_job_id", sa.String(length=64), nullable=True))
    op.add_column("messages", sa.Column("delivery_mode", sa.String(length=48), nullable=True))
    op.add_column("messages", sa.Column("failover_from_ai_agent_id", sa.String(length=36), nullable=True))
    op.add_column("messages", sa.Column("failover_reason", sa.String(length=255), nullable=True))
    op.create_index("ix_messages_ai_agent_id", "messages", ["ai_agent_id"])
    op.create_index("ix_messages_source_entry_link_id_snapshot", "messages", ["source_entry_link_id_snapshot"])
    op.create_index("ix_messages_owner_staff_user_id_snapshot", "messages", ["owner_staff_user_id_snapshot"])
    op.create_index("ix_messages_source_job_id", "messages", ["source_job_id"])

    # ── 扩展 h5_sites：注册与接待配置 ──
    op.add_column("h5_sites", sa.Column("registration_entry_required", sa.Boolean(), nullable=False, server_default=sa.text("1")))
    op.add_column("h5_sites", sa.Column("allow_invite_code_alias", sa.Boolean(), nullable=False, server_default=sa.text("1")))
    op.add_column("h5_sites", sa.Column("allow_unattributed_waba_inbound", sa.Boolean(), nullable=False, server_default=sa.text("0")))
    op.add_column("h5_sites", sa.Column("default_staff_entry_link_id", sa.String(length=36), nullable=True))
    op.add_column("h5_sites", sa.Column("default_ai_agent_id", sa.String(length=36), nullable=True))
    op.add_column("h5_sites", sa.Column("default_ai_entry_link_id", sa.String(length=36), nullable=True))
    op.add_column("h5_sites", sa.Column("default_waba_id", sa.String(length=128), nullable=True))
    op.add_column("h5_sites", sa.Column("default_phone_number_id", sa.String(length=128), nullable=True))
    op.add_column("h5_sites", sa.Column("member_invite_inherits_human_owner", sa.Boolean(), nullable=False, server_default=sa.text("1")))
    op.add_column("h5_sites", sa.Column("member_invite_inherits_ai", sa.Boolean(), nullable=False, server_default=sa.text("1")))
    op.add_column("h5_sites", sa.Column("existing_member_link_override_policy", sa.String(length=32), nullable=False, server_default="do_not_override"))
    op.add_column("h5_sites", sa.Column("ai_failover_policy", sa.String(length=48), nullable=False, server_default="temporary_then_auto_reassign"))
    op.add_column("h5_sites", sa.Column("ai_failover_threshold_minutes", sa.Integer(), nullable=False, server_default="30"))
    op.create_index("ix_h5_sites_default_ai_agent_id", "h5_sites", ["default_ai_agent_id"])


def downgrade() -> None:
    # h5_sites
    for col in [
        "ai_failover_threshold_minutes", "ai_failover_policy", "existing_member_link_override_policy",
        "member_invite_inherits_ai", "member_invite_inherits_human_owner",
        "default_phone_number_id", "default_waba_id", "default_ai_entry_link_id",
        "default_ai_agent_id", "default_staff_entry_link_id",
        "allow_unattributed_waba_inbound", "allow_invite_code_alias", "registration_entry_required",
    ]:
        op.drop_column("h5_sites", col)

    # messages
    for col in [
        "failover_reason", "failover_from_ai_agent_id", "delivery_mode", "source_job_id",
        "owner_assignment_id_snapshot", "owner_agency_member_id_snapshot", "owner_staff_user_id_snapshot",
        "owner_agency_id_snapshot", "source_entry_link_id_snapshot", "ai_prompt_version",
        "ai_model", "ai_provider", "ai_assignment_id_snapshot", "ai_agent_id", "actor_id", "actor_type",
    ]:
        op.drop_column("messages", col)

    # conversations
    for col in [
        "ai_failover_reason", "ai_failover_from_agent_id", "ai_failover_active",
        "current_owner_assignment_id_snapshot", "current_owner_agency_member_id_snapshot",
        "current_owner_staff_user_id_snapshot", "current_owner_agency_id_snapshot",
        "current_entry_link_id", "current_ai_assignment_id", "current_ai_agent_id",
    ]:
        op.drop_column("conversations", col)

    # member_profiles
    for col in [
        "attribution_status", "registration_source_type", "registration_channel",
        "registration_staff_user_id", "registration_ai_agent_id", "registration_entry_link_id",
        "ai_assigned_at", "current_ai_assignment_id", "current_ai_agent_id",
        "owner_assigned_at", "current_owner_assignment_id", "current_owner_agency_member_id",
        "current_owner_staff_user_id", "current_owner_agency_id",
    ]:
        op.drop_column("member_profiles", col)

    for tbl in [
        "ai_outbound_jobs", "ownership_audit_events", "ai_failover_events",
        "conversation_ai_assignments", "member_ai_assignments", "member_owner_assignments",
        "member_ai_transfer_items", "member_ai_transfer_batches",
        "member_owner_transfer_items", "member_owner_transfer_batches",
        "entry_links", "ai_agents",
    ]:
        op.drop_table(tbl)
