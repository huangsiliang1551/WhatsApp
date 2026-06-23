"""Create agency_templates table (one agency one template).

Revision ID: 20260619_0099
Revises: 20260619_0098
"""
from __future__ import annotations
from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa

revision: str = "20260619_0099"
down_revision: str | None = "20260619_0098"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def upgrade() -> None:
    op.create_table(
        "agency_templates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("agency_id", sa.String(36), sa.ForeignKey("agencies.id"), nullable=False, unique=True),
        sa.Column("template_id", sa.String(36), sa.ForeignKey("h5_templates.id"), nullable=False),
        sa.Column("selected_at", sa.DateTime, nullable=False, server_default=sa.text("now()")),
    )

def downgrade() -> None:
    op.drop_table("agency_templates")
