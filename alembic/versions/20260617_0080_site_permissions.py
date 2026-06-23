"""Add site_permissions table for 4-role site access control.

Revision ID: 20260617_0080
Revises: 20260617_0079
Create Date: 2026-06-17 06:30:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260617_0080"
down_revision: str | None = "20260617_0079"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "site_permissions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("site_id", sa.String(36), sa.ForeignKey("h5_sites.id"), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),  # admin/editor/analyst/support
        sa.Column(
            "created_at",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("user_id", "site_id", name="uq_site_permission"),
    )
    op.create_index("ix_site_permission_user", "site_permissions", ["user_id"])
    op.create_index("ix_site_permission_site", "site_permissions", ["site_id"])


def downgrade() -> None:
    op.drop_table("site_permissions")
