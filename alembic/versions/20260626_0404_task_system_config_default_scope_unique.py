"""enforce unique default-scope task system config per account

Revision ID: 20260626_0404
Revises: 20260626_0403
Create Date: 2026-06-26 04:04:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260626_0404"
down_revision = "20260626_0403"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ux_task_system_configs_account_default_scope",
        "task_system_configs",
        ["account_id"],
        unique=True,
        sqlite_where=sa.text("site_id IS NULL"),
        postgresql_where=sa.text("site_id IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ux_task_system_configs_account_default_scope", table_name="task_system_configs")
