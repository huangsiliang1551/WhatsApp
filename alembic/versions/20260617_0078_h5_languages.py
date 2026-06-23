"""Add h5_languages table for dynamic language support.

Revision ID: 20260617_0078
Revises: 20260617_0077
Create Date: 2026-06-17 06:10:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260617_0078"
down_revision: str | None = "20260617_0077"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "h5_languages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("language_code", sa.String(10), nullable=False, unique=True),
        sa.Column("display_name", sa.String(50), nullable=False),
        sa.Column("flag_emoji", sa.String(10), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("h5_languages")
