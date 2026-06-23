"""add duplicate submission guard index

Revision ID: 20260608_0022
Revises: 20260608_0021
Create Date: 2026-06-09 00:10:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260608_0022"
down_revision = "20260608_0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "uq_task_submissions_active_per_task_instance",
        "task_submissions",
        ["task_instance_id"],
        unique=True,
        sqlite_where=sa.text("status IN ('submitted', 'under_review')"),
        postgresql_where=sa.text("status IN ('submitted', 'under_review')"),
    )


def downgrade() -> None:
    op.drop_index("uq_task_submissions_active_per_task_instance", table_name="task_submissions")
