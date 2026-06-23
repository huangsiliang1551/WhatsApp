"""Add AI provider config and account override tables.

Revision ID: 20260613_0071
Revises: 20260612_0065
Create Date: 2026-06-13 10:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260613_0071"
down_revision: str | None = "20260612_0065"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_provider_configs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(128), unique=True, nullable=False, index=True),
        sa.Column("provider_type", sa.String(64), nullable=False),
        sa.Column("api_base_url", sa.String(512), nullable=True),
        sa.Column("api_key_encrypted", sa.String(1024), nullable=True),
        sa.Column("model", sa.String(128), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False, server_default=sa.text("30")),
        sa.Column("use_responses_api", sa.Boolean(), nullable=False, server_default=sa.text("false")),
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
    op.create_index("ix_ai_provider_configs_priority", "ai_provider_configs", ["priority"])

    op.create_table(
        "account_ai_provider_overrides",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("account_id", sa.String(128), unique=True, nullable=False, index=True),
        sa.Column(
            "provider_config_id",
            sa.String(36),
            sa.ForeignKey("ai_provider_configs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
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


def downgrade() -> None:
    op.drop_table("account_ai_provider_overrides")
    op.drop_table("ai_provider_configs")
