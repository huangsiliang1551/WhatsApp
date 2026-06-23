"""Create agencies table.

Revision ID: 20260619_0090
Revises: 20260619_0089
"""
from __future__ import annotations
from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa

revision: str = "20260619_0090"
down_revision: str | None = "20260619_0089"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def upgrade() -> None:
    op.create_table(
        "agencies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("brand_name", sa.String(200)),
        sa.Column("logo_url", sa.String(500)),
        sa.Column("contact_name", sa.String(100)),
        sa.Column("contact_phone", sa.String(20)),
        sa.Column("contact_email", sa.String(200)),
        sa.Column("status", sa.String(32), nullable=False, server_default=sa.text("'active'")),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.text("now()")),
    )

def downgrade() -> None:
    op.drop_table("agencies")
