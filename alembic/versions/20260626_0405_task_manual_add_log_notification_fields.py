"""add notification fields to task manual add logs

Revision ID: 20260626_0405
Revises: 20260626_0404
Create Date: 2026-06-26 04:05:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260626_0405"
down_revision = "20260626_0404"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("task_manual_add_item_logs"):
        op.create_table(
            "task_manual_add_item_logs",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("account_id", sa.String(length=36), nullable=False),
            sa.Column("site_id", sa.String(length=36), nullable=True),
            sa.Column("user_id", sa.String(length=36), nullable=False),
            sa.Column("batch_id", sa.String(length=36), nullable=True),
            sa.Column("package_instance_id", sa.String(length=36), nullable=False),
            sa.Column("operator_id", sa.String(length=128), nullable=False),
            sa.Column("reason_text", sa.Text(), nullable=True),
            sa.Column("notify_user", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("user_notice_text", sa.Text(), nullable=True),
            sa.Column("user_notified_at", sa.DateTime(timezone=False), nullable=True),
            sa.Column("added_item_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("added_amount", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
            sa.Column("before_manual_added_amount", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
            sa.Column("after_manual_added_amount", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
            sa.Column("before_effective_amount", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
            sa.Column("after_effective_amount", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
            sa.ForeignKeyConstraint(["account_id"], ["accounts.account_id"]),
            sa.ForeignKeyConstraint(["site_id"], ["h5_sites.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["app_users.id"]),
            sa.ForeignKeyConstraint(["batch_id"], ["member_task_batches.id"]),
            sa.ForeignKeyConstraint(["package_instance_id"], ["task_package_instances.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_task_manual_add_item_logs_account_id", "task_manual_add_item_logs", ["account_id"])
        op.create_index("ix_task_manual_add_item_logs_site_id", "task_manual_add_item_logs", ["site_id"])
        op.create_index("ix_task_manual_add_item_logs_user_id", "task_manual_add_item_logs", ["user_id"])
        op.create_index("ix_task_manual_add_item_logs_batch_id", "task_manual_add_item_logs", ["batch_id"])
        op.create_index(
            "ix_task_manual_add_item_logs_package_instance_id",
            "task_manual_add_item_logs",
            ["package_instance_id"],
        )
        op.create_index("ix_task_manual_add_item_logs_operator_id", "task_manual_add_item_logs", ["operator_id"])
    else:
        existing_columns = {column["name"] for column in inspector.get_columns("task_manual_add_item_logs")}
        if "notify_user" not in existing_columns:
            op.add_column(
                "task_manual_add_item_logs",
                sa.Column("notify_user", sa.Boolean(), nullable=False, server_default=sa.true()),
            )
        if "user_notice_text" not in existing_columns:
            op.add_column(
                "task_manual_add_item_logs",
                sa.Column("user_notice_text", sa.Text(), nullable=True),
            )
        if "user_notified_at" not in existing_columns:
            op.add_column(
                "task_manual_add_item_logs",
                sa.Column("user_notified_at", sa.DateTime(timezone=False), nullable=True),
            )

    try:
        op.alter_column("task_manual_add_item_logs", "notify_user", server_default=None)
    except Exception:
        pass


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("task_manual_add_item_logs"):
        return

    existing_columns = {column["name"] for column in inspector.get_columns("task_manual_add_item_logs")}
    if {"notify_user", "user_notice_text", "user_notified_at"}.issubset(existing_columns):
        op.drop_column("task_manual_add_item_logs", "user_notified_at")
        op.drop_column("task_manual_add_item_logs", "user_notice_text")
        op.drop_column("task_manual_add_item_logs", "notify_user")
