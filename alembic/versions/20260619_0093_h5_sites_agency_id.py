"""Add agency_id to h5_sites.

Revision ID: 20260619_0093
Revises: 20260619_0092
"""
from __future__ import annotations
from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa

revision: str = "20260619_0093"
down_revision: str | None = "20260619_0092"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def upgrade() -> None:
    bind = op.get_bind()
    op.add_column("h5_sites", sa.Column("agency_id", sa.String(36), nullable=True))
    op.create_index("ix_h5_sites_agency_id", "h5_sites", ["agency_id"])
    if bind.dialect.name != "sqlite":
        op.create_foreign_key(
            "fk_h5_sites_agency_id_agencies",
            "h5_sites",
            "agencies",
            ["agency_id"],
            ["id"],
        )

def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        op.drop_constraint("fk_h5_sites_agency_id_agencies", "h5_sites", type_="foreignkey")
    op.drop_index("ix_h5_sites_agency_id", table_name="h5_sites")
    op.drop_column("h5_sites", "agency_id")
