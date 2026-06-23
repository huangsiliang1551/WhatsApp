"""make_notifications_account_id_nullable

Revision ID: ae789a13b2c5
Revises: 9eded4d8393d
Create Date: 2026-06-17 19:17:12.170964
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ae789a13b2c5'
down_revision = '9eded4d8393d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("notifications") as batch_op:
        batch_op.alter_column(
            "account_id",
            existing_type=sa.VARCHAR(length=128),
            nullable=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("notifications") as batch_op:
        batch_op.alter_column(
            "account_id",
            existing_type=sa.VARCHAR(length=128),
            nullable=False,
        )
