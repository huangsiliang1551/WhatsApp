"""Add notifications table for notification center.

Revision ID: 20260616_0076
Revises: a3f5c2d1e6b7
Create Date: 2026-06-16 14:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260616_0076"
down_revision: str | None = "a3f5c2d1e6b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("account_id", sa.String(128), sa.ForeignKey("accounts.account_id"), nullable=False, index=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("app_users.id"), nullable=True),
        sa.Column("type", sa.String(32), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("severity", sa.String(16), nullable=False, server_default=sa.text("'info'")),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("action_url", sa.String(500), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("read_at", sa.DateTime(timezone=False), nullable=True),
    )
    op.create_index("ix_notifications_account_unread", "notifications", ["account_id", "is_read"])
    op.create_index("ix_notifications_created_at", "notifications", ["created_at"])


def downgrade() -> None:
    op.drop_table("notifications")
