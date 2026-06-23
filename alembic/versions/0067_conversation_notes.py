"""conversation_notes

Revision ID: 0067
Revises: 0066
Create Date: 2026-06-12 12:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0067"
down_revision: str | None = "0066"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "conversation_notes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("account_id", sa.String(128), sa.ForeignKey("accounts.account_id"), nullable=False, index=True),
        sa.Column("conversation_id", sa.String(128), nullable=False, index=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("agent_id", sa.String(128), nullable=False),
        sa.Column("agent_name", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_conversation_notes_account_conversation",
        "conversation_notes",
        ["account_id", "conversation_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_conversation_notes_account_conversation", table_name="conversation_notes")
    op.drop_table("conversation_notes")
