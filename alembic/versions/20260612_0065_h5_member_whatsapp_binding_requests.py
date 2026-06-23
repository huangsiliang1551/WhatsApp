"""Add persistent H5 member WhatsApp binding request placeholder table.

Revision ID: 20260612_0065
Revises: 20260612_0064
Create Date: 2026-06-12 12:30:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260612_0065"
down_revision: str | None = "20260612_0064"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "member_whatsapp_binding_requests",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("member_profile_id", sa.String(length=36), nullable=False),
        sa.Column("site_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("requested_phone_number", sa.String(length=32), nullable=True),
        sa.Column("start_count", sa.Integer(), nullable=False),
        sa.Column("last_started_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("bound_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.account_id"]),
        sa.ForeignKeyConstraint(["user_id"], ["app_users.id"]),
        sa.ForeignKeyConstraint(["member_profile_id"], ["member_profiles.id"]),
        sa.ForeignKeyConstraint(["site_id"], ["h5_sites.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "account_id",
            "member_profile_id",
            name="uq_member_whatsapp_binding_requests_account_member_profile",
        ),
    )
    op.create_index(
        "ix_member_whatsapp_binding_requests_account_id",
        "member_whatsapp_binding_requests",
        ["account_id"],
        unique=False,
    )
    op.create_index(
        "ix_member_whatsapp_binding_requests_user_id",
        "member_whatsapp_binding_requests",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_member_whatsapp_binding_requests_member_profile_id",
        "member_whatsapp_binding_requests",
        ["member_profile_id"],
        unique=False,
    )
    op.create_index(
        "ix_member_whatsapp_binding_requests_site_id",
        "member_whatsapp_binding_requests",
        ["site_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_member_whatsapp_binding_requests_site_id",
        table_name="member_whatsapp_binding_requests",
    )
    op.drop_index(
        "ix_member_whatsapp_binding_requests_member_profile_id",
        table_name="member_whatsapp_binding_requests",
    )
    op.drop_index(
        "ix_member_whatsapp_binding_requests_user_id",
        table_name="member_whatsapp_binding_requests",
    )
    op.drop_index(
        "ix_member_whatsapp_binding_requests_account_id",
        table_name="member_whatsapp_binding_requests",
    )
    op.drop_table("member_whatsapp_binding_requests")
