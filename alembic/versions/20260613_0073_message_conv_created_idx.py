"""Add composite index on messages (conversation_id, created_at DESC, id DESC)

Revision ID: 20260613_0073
Revises: 20260612_0072
Create Date: 2026-06-13 12:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260613_0073"
down_revision: str | None = "20260612_0072"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_messages_conv_created_id_desc",
        "messages",
        ["conversation_id", sa.text("created_at DESC"), sa.text("id DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_messages_conv_created_id_desc", table_name="messages")
