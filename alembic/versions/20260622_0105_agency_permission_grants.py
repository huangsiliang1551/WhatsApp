"""Create agency_permission_grants table.

Revision ID: 20260622_0105
Revises: 20260619_0201
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260622_0105"
down_revision: str | None = "20260619_0201"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agency_permission_grants",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("agency_id", sa.String(36), sa.ForeignKey("agencies.id"), nullable=False),
        sa.Column("permissions", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("agency_id", name="uq_agency_permission_grants_agency_id"),
    )
    op.create_index(
        "ix_agency_permission_grants_agency_id",
        "agency_permission_grants",
        ["agency_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_agency_permission_grants_agency_id", table_name="agency_permission_grants")
    op.drop_table("agency_permission_grants")
