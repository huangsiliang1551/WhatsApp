"""Add user_type and agency_id to agents (support agents).

Revision ID: 20260619_0097
Revises: 20260619_0096
"""
from __future__ import annotations
from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa

revision: str = "20260619_0097"
down_revision: str | None = "20260619_0096"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def upgrade() -> None:
    bind = op.get_bind()
    op.add_column("agents", sa.Column("user_type", sa.String(32), nullable=False, server_default=sa.text("'super_admin'")))
    op.add_column("agents", sa.Column("agency_id", sa.String(36), nullable=True))
    op.create_index("ix_agents_agency_id", "agents", ["agency_id"])
    if bind.dialect.name != "sqlite":
        op.create_foreign_key(
            "fk_agents_agency_id_agencies",
            "agents",
            "agencies",
            ["agency_id"],
            ["id"],
        )
    op.create_index("ix_agents_user_type", "agents", ["user_type"])

def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        op.drop_constraint("fk_agents_agency_id_agencies", "agents", type_="foreignkey")
    op.drop_index("ix_agents_agency_id", table_name="agents")
    op.drop_index("ix_agents_user_type", table_name="agents")
    op.drop_column("agents", "agency_id")
    op.drop_column("agents", "user_type")
