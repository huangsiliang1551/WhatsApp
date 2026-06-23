"""Create agency_billing table.

Revision ID: 20260619_0092
Revises: 20260619_0091
"""
from __future__ import annotations
from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa

revision: str = "20260619_0092"
down_revision: str | None = "20260619_0091"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def upgrade() -> None:
    op.create_table(
        "agency_billing",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("agency_id", sa.String(36), sa.ForeignKey("agencies.id"), nullable=False, index=True),
        sa.Column("billing_type", sa.String(32), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("billing_period_start", sa.Date, nullable=True),
        sa.Column("billing_period_end", sa.Date, nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_agency_billing_agency_status", "agency_billing", ["agency_id", "status"])

def downgrade() -> None:
    op.drop_table("agency_billing")
