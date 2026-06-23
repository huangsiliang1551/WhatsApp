"""Add missing updated_at columns to h5_languages and site_permissions.

Revision ID: 20260617_0083
Revises: 20260617_0082
Create Date: 2026-06-17 08:30:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260617_0083"
down_revision: str | None = "20260617_0082"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "h5_languages",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.add_column(
        "site_permissions",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_column("site_permissions", "updated_at")
    op.drop_column("h5_languages", "updated_at")
