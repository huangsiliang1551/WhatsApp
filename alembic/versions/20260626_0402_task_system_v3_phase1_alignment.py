"""align task system v3 phase 1 foundation fields

Revision ID: 20260626_0402
Revises: 20260626_0401
Create Date: 2026-06-26 04:02:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260626_0402"
down_revision = "20260626_0401"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "task_issue_plans",
        sa.Column("default_tolerance_amount", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
    )
    op.add_column(
        "task_issue_plans",
        sa.Column("default_reward_ratio", sa.Numeric(12, 4), nullable=False, server_default="0.10"),
    )
    op.add_column(
        "task_issue_plan_day_rules",
        sa.Column("issue_time_of_day", sa.String(length=16), nullable=True),
    )
    op.add_column(
        "task_issue_plan_day_rules",
        sa.Column("elapsed_delay_hours", sa.Integer(), nullable=True),
    )
    op.add_column(
        "task_product_pools",
        sa.Column("price_mode", sa.String(length=32), nullable=False, server_default="task_price_snapshot"),
    )
    op.add_column(
        "task_product_pools",
        sa.Column("allow_repeat_in_same_batch", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "task_product_pools",
        sa.Column("allow_repeat_in_same_package", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("task_product_pools", "allow_repeat_in_same_package")
    op.drop_column("task_product_pools", "allow_repeat_in_same_batch")
    op.drop_column("task_product_pools", "price_mode")
    op.drop_column("task_issue_plan_day_rules", "elapsed_delay_hours")
    op.drop_column("task_issue_plan_day_rules", "issue_time_of_day")
    op.drop_column("task_issue_plans", "default_reward_ratio")
    op.drop_column("task_issue_plans", "default_tolerance_amount")
