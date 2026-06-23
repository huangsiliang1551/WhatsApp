"""add support knowledge entries

Revision ID: 20260606_0002
Revises: 20260606_0001
Create Date: 2026-06-06 21:40:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260606_0002"
down_revision = "20260606_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "support_knowledge_entries",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("account_id", sa.String(length=128), nullable=False),
        sa.Column("article_id", sa.String(length=128), nullable=False),
        sa.Column("route_name", sa.String(length=128), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("answer_text", sa.Text(), nullable=False),
        sa.Column("source_language", sa.String(length=32), nullable=False, server_default="en"),
        sa.Column("keywords_json", sa.JSON(), nullable=False),
        sa.Column("minimum_score", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.account_id"]),
        sa.UniqueConstraint("account_id", "article_id", name="uq_support_knowledge_entries_account_article"),
        sa.UniqueConstraint("account_id", "route_name", name="uq_support_knowledge_entries_account_route"),
    )
    op.create_index("ix_support_knowledge_entries_account_id", "support_knowledge_entries", ["account_id"])


def downgrade() -> None:
    op.drop_index("ix_support_knowledge_entries_account_id", table_name="support_knowledge_entries")
    op.drop_table("support_knowledge_entries")
