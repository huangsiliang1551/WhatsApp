"""Add translation provider configs table.

Revision ID: 20260618_0088
Revises: 20260617_0087
Create Date: 2026-06-18 10:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260618_0088"
down_revision: str | None = "20260617_0087"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "translation_provider_configs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(128), unique=True, nullable=False, index=True),
        sa.Column("provider_type", sa.String(64), nullable=False),
        sa.Column("secret_id_encrypted", sa.String(1024), nullable=True),
        sa.Column("secret_key_encrypted", sa.String(2048), nullable=True),
        sa.Column("region", sa.String(64), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False, server_default=sa.text("15")),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
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
    )
    op.create_index("ix_translation_provider_configs_priority", "translation_provider_configs", ["priority"])


def downgrade() -> None:
    op.drop_index("ix_translation_provider_configs_priority", table_name="translation_provider_configs")
    op.drop_table("translation_provider_configs")
