"""Add agency_id to support_knowledge_entries.

Revision ID: 20260619_0096
Revises: 20260619_0095
"""
from __future__ import annotations
from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa

revision: str = "20260619_0096"
down_revision: str | None = "20260619_0095"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def upgrade() -> None:
    bind = op.get_bind()
    op.add_column("support_knowledge_entries", sa.Column("agency_id", sa.String(36), nullable=True))
    op.create_index("ix_support_knowledge_entries_agency_id", "support_knowledge_entries", ["agency_id"])
    if bind.dialect.name != "sqlite":
        op.create_foreign_key(
            "fk_support_knowledge_entries_agency_id_agencies",
            "support_knowledge_entries",
            "agencies",
            ["agency_id"],
            ["id"],
        )

def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        op.drop_constraint(
            "fk_support_knowledge_entries_agency_id_agencies",
            "support_knowledge_entries",
            type_="foreignkey",
        )
    op.drop_index("ix_support_knowledge_entries_agency_id", table_name="support_knowledge_entries")
    op.drop_column("support_knowledge_entries", "agency_id")
