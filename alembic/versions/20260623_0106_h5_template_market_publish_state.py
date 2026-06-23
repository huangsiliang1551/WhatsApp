"""Add H5 template market publish state fields.

Revision ID: 20260623_0106
Revises: 20260622_0105_agency_permission_grants
Create Date: 2026-06-23 00:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260623_0106"
down_revision = "20260622_0105"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("h5_templates") as batch_op:
        batch_op.add_column(sa.Column("publish_status", sa.String(length=20), nullable=False, server_default="draft"))
        batch_op.add_column(sa.Column("published_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("published_by", sa.String(length=36), nullable=True))

    op.execute("UPDATE h5_templates SET publish_status = 'draft' WHERE publish_status IS NULL")

    with op.batch_alter_table("h5_templates") as batch_op:
        batch_op.alter_column("publish_status", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("h5_templates") as batch_op:
        batch_op.drop_column("published_by")
        batch_op.drop_column("published_at")
        batch_op.drop_column("publish_status")
