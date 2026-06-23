"""Add account-scoped agent fields.

Revision ID: 20260608_0017
Revises: 20260608_0016
Create Date: 2026-06-08 00:40:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260608_0017"
down_revision = "20260608_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("agents") as batch_op:
        batch_op.add_column(sa.Column("account_id", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("agent_key", sa.String(length=128), nullable=True))
        batch_op.create_index("ix_agents_account_id", ["account_id"], unique=False)
        batch_op.create_index("ix_agents_agent_key", ["agent_key"], unique=False)

    op.execute("UPDATE agents SET agent_key = id WHERE agent_key IS NULL")

    with op.batch_alter_table("agents") as batch_op:
        batch_op.alter_column("agent_key", existing_type=sa.String(length=128), nullable=False)
        batch_op.create_foreign_key(
            "fk_agents_account_id_accounts",
            "accounts",
            ["account_id"],
            ["account_id"],
        )
        batch_op.create_unique_constraint(
            "uq_agents_account_agent_key",
            ["account_id", "agent_key"],
        )


def downgrade() -> None:
    with op.batch_alter_table("agents") as batch_op:
        batch_op.drop_constraint("uq_agents_account_agent_key", type_="unique")
        batch_op.drop_constraint("fk_agents_account_id_accounts", type_="foreignkey")
        batch_op.drop_index("ix_agents_agent_key")
        batch_op.drop_index("ix_agents_account_id")
        batch_op.drop_column("agent_key")
        batch_op.drop_column("account_id")
