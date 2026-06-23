"""add embedded signup webhook subscription pointer

Revision ID: 20260609_0043
Revises: 20260609_0042
Create Date: 2026-06-09 03:35:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260609_0043"
down_revision: str | None = "20260609_0042"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("embedded_signup_sessions") as batch_op:
        batch_op.add_column(
            sa.Column("created_webhook_subscription_id", sa.String(length=36), nullable=True)
        )
        batch_op.create_index(
            "ix_embedded_signup_sessions_created_webhook_subscription_id",
            ["created_webhook_subscription_id"],
            unique=False,
        )
        batch_op.create_foreign_key(
            "fk_embedded_signup_sessions_created_webhook_subscription_id",
            "webhook_subscriptions",
            ["created_webhook_subscription_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("embedded_signup_sessions") as batch_op:
        batch_op.drop_constraint(
            "fk_embedded_signup_sessions_created_webhook_subscription_id",
            type_="foreignkey",
        )
        batch_op.drop_index("ix_embedded_signup_sessions_created_webhook_subscription_id")
        batch_op.drop_column("created_webhook_subscription_id")
