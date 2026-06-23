"""Add deploy_history table.

Revision ID: 20260619_0089
Revises: 20260618_0088
Create Date: 2026-06-19 08:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260619_0089"
down_revision: str | None = "20260618_0088"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "deploy_history",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("site_id", sa.String(36), sa.ForeignKey("h5_sites.id"), nullable=False, index=True),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("details", sa.JSON, nullable=True),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_deploy_history_site_created", "deploy_history", ["site_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_deploy_history_site_created", table_name="deploy_history")
    op.drop_table("deploy_history")
