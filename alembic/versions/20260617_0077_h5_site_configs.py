"""Add h5_site_configs table for per-site independent configuration.

Revision ID: 20260617_0077
Revises: 20260616_0076
Create Date: 2026-06-17 06:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260617_0077"
down_revision: str | None = "20260616_0076"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "h5_site_configs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("site_id", sa.String(36), sa.ForeignKey("h5_sites.id"), nullable=False, unique=True),
        # 品牌配置
        sa.Column("logo_url", sa.String(500), nullable=True),
        sa.Column("favicon_url", sa.String(500), nullable=True),
        sa.Column("primary_color", sa.String(7), nullable=True, server_default=sa.text("'#1677ff'")),
        sa.Column("font_family", sa.String(100), nullable=True),
        sa.Column("footer_text", sa.String(500), nullable=True),
        # 功能开关
        sa.Column("enabled_pages", sa.JSON(), nullable=True),
        sa.Column("custom_css", sa.Text(), nullable=True),
        # 部署配置
        sa.Column("deploy_type", sa.String(32), nullable=True),
        sa.Column("ssh_host", sa.String(200), nullable=True),
        sa.Column("ssh_user", sa.String(50), nullable=True),
        sa.Column("ssh_key_path", sa.String(500), nullable=True),
        sa.Column("domain", sa.String(200), nullable=True),
        sa.Column("ssl_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
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
    op.drop_table("h5_site_configs")
