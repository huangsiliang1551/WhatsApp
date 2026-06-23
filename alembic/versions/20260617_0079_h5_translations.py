"""Add h5_translations table for pre-translated content with AI fallback.

Revision ID: 20260617_0079
Revises: 20260617_0078
Create Date: 2026-06-17 06:20:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260617_0079"
down_revision: str | None = "20260617_0078"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "h5_translations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("site_id", sa.String(36), sa.ForeignKey("h5_sites.id"), nullable=False),
        sa.Column("language_code", sa.String(10), nullable=False),
        sa.Column("translation_key", sa.String(200), nullable=False),
        sa.Column("translated_text", sa.Text(), nullable=False),
        sa.Column("is_ai_translated", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("site_id", "language_code", "translation_key", name="uq_h5_translation"),
    )
    op.create_index("ix_h5_translation_site_lang", "h5_translations", ["site_id", "language_code"])


def downgrade() -> None:
    op.drop_table("h5_translations")
