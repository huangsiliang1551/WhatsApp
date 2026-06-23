"""Create h5_templates table.

Revision ID: 20260619_0098
Revises: 20260619_0097
"""
from __future__ import annotations
from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa

revision: str = "20260619_0098"
down_revision: str | None = "20260619_0097"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def upgrade() -> None:
    op.create_table(
        "h5_templates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("preview_url", sa.String(500)),
        sa.Column("template_data", sa.JSON),
        sa.Column("created_by", sa.String(36)),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.text("now()")),
    )

def downgrade() -> None:
    op.drop_table("h5_templates")
