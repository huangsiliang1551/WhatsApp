"""Add registration_ip column to app_users.

Revision ID: 20260612_0072
Revises: 086f5f9b9ad6
Create Date: 2026-06-12 20:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260612_0072"
down_revision: str | None = "086f5f9b9ad6"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "app_users",
        sa.Column("registration_ip", sa.String(length=45), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("app_users", "registration_ip")
