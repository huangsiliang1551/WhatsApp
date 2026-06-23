"""Create agency_members table.

Revision ID: 20260619_0091
Revises: 20260619_0090
"""
from __future__ import annotations
from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa

revision: str = "20260619_0091"
down_revision: str | None = "20260619_0090"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def upgrade() -> None:
    op.create_table(
        "agency_members",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("agency_id", sa.String(36), sa.ForeignKey("agencies.id"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("agency_id", "user_id", name="uq_agency_members_agency_user"),
    )
    op.create_index("ix_agency_members_agency", "agency_members", ["agency_id"])
    op.create_index("ix_agency_members_user", "agency_members", ["user_id"])

def downgrade() -> None:
    op.drop_table("agency_members")
