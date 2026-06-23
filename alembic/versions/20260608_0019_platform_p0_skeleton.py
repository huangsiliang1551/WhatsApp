"""add platform p0 skeleton tables

Revision ID: 20260608_0019
Revises: 20260608_0018
Create Date: 2026-06-08 23:20:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260608_0019"
down_revision = "20260608_0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "h5_sites",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("site_key", sa.String(length=64), nullable=False),
        sa.Column("domain", sa.String(length=255), nullable=False),
        sa.Column("brand_name", sa.String(length=255), nullable=False),
        sa.Column("logo_url", sa.String(length=1024), nullable=True),
        sa.Column("default_language", sa.String(length=32), nullable=False, server_default="zh-CN"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("domain"),
        sa.UniqueConstraint("site_key"),
    )
    op.create_index("ix_h5_sites_domain", "h5_sites", ["domain"])
    op.create_index("ix_h5_sites_site_key", "h5_sites", ["site_key"])

    op.create_table(
        "app_users",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("public_user_id", sa.String(length=128), nullable=False),
        sa.Column("registration_site_id", sa.String(length=36), nullable=True),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("country_code", sa.String(length=8), nullable=True),
        sa.Column("language_code", sa.String(length=32), nullable=False, server_default="zh-CN"),
        sa.Column("is_anonymous", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("lifecycle_status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("has_phone", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("has_email", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("has_whatsapp", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_invited_user", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_new_user", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("restrict_task_claim", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("registration_invite_code", sa.String(length=64), nullable=True),
        sa.Column("last_active_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(["registration_site_id"], ["h5_sites.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("public_user_id"),
    )
    op.create_index("ix_app_users_public_user_id", "app_users", ["public_user_id"])
    op.create_index("ix_app_users_registration_site_id", "app_users", ["registration_site_id"])
    op.create_index("ix_app_users_registration_invite_code", "app_users", ["registration_invite_code"])

    op.create_table(
        "user_identities",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("identity_type", sa.String(length=32), nullable=False, server_default="anonymous"),
        sa.Column("identity_value", sa.String(length=255), nullable=False),
        sa.Column("country_code", sa.String(length=8), nullable=True),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["app_users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("identity_type", "identity_value", name="uq_user_identities_value"),
        sa.UniqueConstraint("user_id", "identity_type", "identity_value", name="uq_user_identities_user_value"),
    )
    op.create_index("ix_user_identities_user_id", "user_identities", ["user_id"])

    op.create_table(
        "invite_codes",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("site_id", sa.String(length=36), nullable=True),
        sa.Column("inviter_user_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("usage_limit", sa.Integer(), nullable=True),
        sa.Column("usage_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("expires_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(["inviter_user_id"], ["app_users.id"]),
        sa.ForeignKeyConstraint(["site_id"], ["h5_sites.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_invite_codes_code", "invite_codes", ["code"])
    op.create_index("ix_invite_codes_site_id", "invite_codes", ["site_id"])
    op.create_index("ix_invite_codes_inviter_user_id", "invite_codes", ["inviter_user_id"])

    op.create_table(
        "user_tags",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tag_key", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("color", sa.String(length=32), nullable=True),
        sa.Column("source_type", sa.String(length=32), nullable=False, server_default="manual"),
        sa.Column("rule_json", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tag_key"),
    )
    op.create_index("ix_user_tags_tag_key", "user_tags", ["tag_key"])

    op.create_table(
        "user_tag_assignments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("tag_id", sa.String(length=36), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False, server_default="manual"),
        sa.Column("source_rule_key", sa.String(length=64), nullable=True),
        sa.Column("assigned_by", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(["tag_id"], ["user_tags.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["app_users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "tag_id", name="uq_user_tag_assignments_scope"),
    )
    op.create_index("ix_user_tag_assignments_user_id", "user_tag_assignments", ["user_id"])
    op.create_index("ix_user_tag_assignments_tag_id", "user_tag_assignments", ["tag_id"])

    op.create_table(
        "audience_rule_sets",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("rule_key", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("scope_type", sa.String(length=64), nullable=False, server_default="task_template"),
        sa.Column("scope_id", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("rules_json", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(length=128), nullable=True),
        sa.Column("updated_by", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("rule_key"),
    )
    op.create_index("ix_audience_rule_sets_rule_key", "audience_rule_sets", ["rule_key"])
    op.create_index("ix_audience_rule_sets_scope_id", "audience_rule_sets", ["scope_id"])


def downgrade() -> None:
    op.drop_index("ix_audience_rule_sets_scope_id", table_name="audience_rule_sets")
    op.drop_index("ix_audience_rule_sets_rule_key", table_name="audience_rule_sets")
    op.drop_table("audience_rule_sets")

    op.drop_index("ix_user_tag_assignments_tag_id", table_name="user_tag_assignments")
    op.drop_index("ix_user_tag_assignments_user_id", table_name="user_tag_assignments")
    op.drop_table("user_tag_assignments")

    op.drop_index("ix_user_tags_tag_key", table_name="user_tags")
    op.drop_table("user_tags")

    op.drop_index("ix_invite_codes_inviter_user_id", table_name="invite_codes")
    op.drop_index("ix_invite_codes_site_id", table_name="invite_codes")
    op.drop_index("ix_invite_codes_code", table_name="invite_codes")
    op.drop_table("invite_codes")

    op.drop_index("ix_user_identities_user_id", table_name="user_identities")
    op.drop_table("user_identities")

    op.drop_index("ix_app_users_registration_invite_code", table_name="app_users")
    op.drop_index("ix_app_users_registration_site_id", table_name="app_users")
    op.drop_index("ix_app_users_public_user_id", table_name="app_users")
    op.drop_table("app_users")

    op.drop_index("ix_h5_sites_site_key", table_name="h5_sites")
    op.drop_index("ix_h5_sites_domain", table_name="h5_sites")
    op.drop_table("h5_sites")
