"""Add agency_id to whatsapp_business_accounts.

Revision ID: 20260619_0094
Revises: 20260619_0093
"""
from __future__ import annotations
from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa

revision: str = "20260619_0094"
down_revision: str | None = "20260619_0093"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def upgrade() -> None:
    bind = op.get_bind()
    op.add_column("whatsapp_business_accounts", sa.Column("agency_id", sa.String(36), nullable=True))
    op.create_index("ix_whatsapp_business_accounts_agency_id", "whatsapp_business_accounts", ["agency_id"])
    if bind.dialect.name != "sqlite":
        op.create_foreign_key(
            "fk_whatsapp_business_accounts_agency_id_agencies",
            "whatsapp_business_accounts",
            "agencies",
            ["agency_id"],
            ["id"],
        )

def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        op.drop_constraint(
            "fk_whatsapp_business_accounts_agency_id_agencies",
            "whatsapp_business_accounts",
            type_="foreignkey",
        )
    op.drop_index("ix_whatsapp_business_accounts_agency_id", table_name="whatsapp_business_accounts")
    op.drop_column("whatsapp_business_accounts", "agency_id")
