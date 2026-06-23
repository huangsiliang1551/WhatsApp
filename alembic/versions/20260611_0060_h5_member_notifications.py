"""Add H5 member notification center table.

Revision ID: 20260611_0060
Revises: 20260611_0059
Create Date: 2026-06-11 20:15:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260611_0060"
down_revision: str | None = "20260611_0059"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "member_notifications",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=128), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("member_profile_id", sa.String(length=36), nullable=False),
        sa.Column("site_id", sa.String(length=36), nullable=True),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column("reference_type", sa.String(length=64), nullable=True),
        sa.Column("reference_id", sa.String(length=36), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.account_id"]),
        sa.ForeignKeyConstraint(["member_profile_id"], ["member_profiles.id"]),
        sa.ForeignKeyConstraint(["site_id"], ["h5_sites.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["app_users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_member_notifications_account_id", "member_notifications", ["account_id"], unique=False)
    op.create_index("ix_member_notifications_user_id", "member_notifications", ["user_id"], unique=False)
    op.create_index(
        "ix_member_notifications_member_profile_id",
        "member_notifications",
        ["member_profile_id"],
        unique=False,
    )
    op.create_index("ix_member_notifications_site_id", "member_notifications", ["site_id"], unique=False)
    op.create_index("ix_member_notifications_is_read", "member_notifications", ["is_read"], unique=False)
    op.create_index("ix_member_notifications_reference_id", "member_notifications", ["reference_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_member_notifications_reference_id", table_name="member_notifications")
    op.drop_index("ix_member_notifications_is_read", table_name="member_notifications")
    op.drop_index("ix_member_notifications_site_id", table_name="member_notifications")
    op.drop_index("ix_member_notifications_member_profile_id", table_name="member_notifications")
    op.drop_index("ix_member_notifications_user_id", table_name="member_notifications")
    op.drop_index("ix_member_notifications_account_id", table_name="member_notifications")
    op.drop_table("member_notifications")
