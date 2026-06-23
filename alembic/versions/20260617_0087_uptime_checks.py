"""Add uptime_checks table for H5 site heartbeat monitoring.

Revision ID: 20260617_0087
Revises: 20260617_0086
Create Date: 2026-06-17 09:30:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260617_0087"
down_revision: str | None = "20260617_0086"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "uptime_checks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("site_id", sa.String(36), sa.ForeignKey("h5_sites.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("response_time_ms", sa.Integer(), nullable=True),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_uptime_checks_site_id", "uptime_checks", ["site_id"])
    op.create_index("ix_uptime_checks_created_at", "uptime_checks", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_uptime_checks_created_at", table_name="uptime_checks")
    op.drop_index("ix_uptime_checks_site_id", table_name="uptime_checks")
    op.drop_table("uptime_checks")
