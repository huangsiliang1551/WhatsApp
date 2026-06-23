"""Add ip_blacklist table for IP-based access control.

Revision ID: 20260617_0085
Revises: 20260617_0084
Create Date: 2026-06-17 09:10:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260617_0085"
down_revision: str | None = "20260617_0084"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ip_blacklist",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("ip_address", sa.String(45), nullable=False, unique=True),
        sa.Column("reason", sa.String(500), nullable=True),
        sa.Column("blocked_until", sa.DateTime(timezone=False), nullable=True),
        sa.Column("created_by", sa.String(36), nullable=True),
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


def downgrade() -> None:
    op.drop_table("ip_blacklist")
