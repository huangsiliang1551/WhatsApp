"""add estimated cost to template send logs

Revision ID: 20260608_0014
Revises: 20260608_0013
Create Date: 2026-06-08 15:10:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260608_0014"
down_revision: str | None = "20260608_0013"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("template_send_logs") as batch_op:
        batch_op.add_column(sa.Column("estimated_cost", sa.Numeric(12, 4), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("template_send_logs") as batch_op:
        batch_op.drop_column("estimated_cost")
