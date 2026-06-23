"""Add client_errors table for frontend JS error tracking.

Revision ID: 20260617_0086
Revises: 20260617_0085
Create Date: 2026-06-17 09:20:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260617_0086"
down_revision: str | None = "20260617_0085"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "client_errors",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("site_key", sa.String(50), nullable=True),
        sa.Column("error_type", sa.String(50), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("stack_trace", sa.Text(), nullable=True),
        sa.Column("url", sa.String(500), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_client_errors_created_at", "client_errors", ["created_at"])
    op.create_index("ix_client_errors_error_type", "client_errors", ["error_type"])


def downgrade() -> None:
    op.drop_index("ix_client_errors_error_type", table_name="client_errors")
    op.drop_index("ix_client_errors_created_at", table_name="client_errors")
    op.drop_table("client_errors")
