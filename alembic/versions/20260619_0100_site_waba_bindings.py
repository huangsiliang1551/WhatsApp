"""Create site_waba_bindings table (many-to-many site-WABA).

Revision ID: 20260619_0100
Revises: 20260619_0099
"""
from __future__ import annotations
from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa

revision: str = "20260619_0100"
down_revision: str | None = "20260619_0099"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def upgrade() -> None:
    op.create_table(
        "site_waba_bindings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("site_id", sa.String(36), sa.ForeignKey("h5_sites.id"), nullable=False, index=True),
        sa.Column("waba_id", sa.String(36), sa.ForeignKey("whatsapp_business_accounts.id"), nullable=False, index=True),
        sa.Column("assigned_at", sa.DateTime, nullable=False, server_default=sa.text("now()")),
        sa.Column("assigned_by", sa.String(36)),
        sa.UniqueConstraint("site_id", "waba_id", name="uq_site_waba_binding"),
    )

def downgrade() -> None:
    op.drop_table("site_waba_bindings")
