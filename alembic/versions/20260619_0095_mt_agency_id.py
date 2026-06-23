"""Add agency_id to message_templates.

Revision ID: 20260619_0095
Revises: 20260619_0094
"""
from __future__ import annotations
from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa

revision: str = "20260619_0095"
down_revision: str | None = "20260619_0094"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def upgrade() -> None:
    bind = op.get_bind()
    op.add_column("message_templates", sa.Column("agency_id", sa.String(36), nullable=True))
    op.create_index("ix_message_templates_agency_id", "message_templates", ["agency_id"])
    if bind.dialect.name != "sqlite":
        op.create_foreign_key(
            "fk_message_templates_agency_id_agencies",
            "message_templates",
            "agencies",
            ["agency_id"],
            ["id"],
        )

def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        op.drop_constraint(
            "fk_message_templates_agency_id_agencies",
            "message_templates",
            type_="foreignkey",
        )
    op.drop_index("ix_message_templates_agency_id", table_name="message_templates")
    op.drop_column("message_templates", "agency_id")
