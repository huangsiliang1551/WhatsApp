"""add task system v3 runtime generation fields

Revision ID: 20260626_0403
Revises: 20260626_0402
Create Date: 2026-06-26 04:03:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260626_0403"
down_revision = "20260626_0402"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "member_task_batches",
        sa.Column("completed_package_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "member_task_batches",
        sa.Column("current_package_index", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "member_task_batches",
        sa.Column("reward_ratio_snapshot", sa.Numeric(12, 4), nullable=False, server_default="0.10"),
    )
    op.add_column(
        "member_task_batches",
        sa.Column("products_generated", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "member_task_batches",
        sa.Column("product_generation_run_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "member_task_batches",
        sa.Column("claimed_at", sa.DateTime(timezone=False), nullable=True),
    )
    op.create_index(
        "ix_member_task_batches_product_generation_run_id",
        "member_task_batches",
        ["product_generation_run_id"],
    )
    op.execute("UPDATE member_task_batches SET status = 'pending_claim' WHERE status = 'pending'")

    op.add_column(
        "task_product_pool_items",
        sa.Column("product_description", sa.Text(), nullable=True),
    )
    op.add_column(
        "task_product_pool_items",
        sa.Column("reference_price", sa.Numeric(18, 2), nullable=True),
    )
    op.add_column(
        "task_product_pool_items",
        sa.Column("min_task_price", sa.Numeric(18, 2), nullable=True),
    )
    op.add_column(
        "task_product_pool_items",
        sa.Column("max_task_price", sa.Numeric(18, 2), nullable=True),
    )
    op.add_column(
        "task_product_pool_items",
        sa.Column("weight", sa.Integer(), nullable=False, server_default="100"),
    )

    op.add_column(
        "task_package_instances",
        sa.Column("batch_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "task_package_instances",
        sa.Column("quota_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "task_package_instances",
        sa.Column("batch_day_no", sa.Integer(), nullable=True),
    )
    op.add_column(
        "task_package_instances",
        sa.Column("batch_index", sa.Integer(), nullable=True),
    )
    op.add_column(
        "task_package_instances",
        sa.Column("batch_total", sa.Integer(), nullable=True),
    )
    op.add_column(
        "task_package_instances",
        sa.Column("planned_amount", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
    )
    op.add_column(
        "task_package_instances",
        sa.Column("system_generated_amount", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
    )
    op.add_column(
        "task_package_instances",
        sa.Column("manual_added_amount", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
    )
    op.add_column(
        "task_package_instances",
        sa.Column("effective_amount", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
    )
    op.add_column(
        "task_package_instances",
        sa.Column("reward_amount_final", sa.Numeric(18, 2), nullable=True),
    )
    op.add_column(
        "task_package_instances",
        sa.Column("reward_ledger_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "task_package_instances",
        sa.Column("current_item_index", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "task_package_instances",
        sa.Column("visible_item_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "task_package_instances",
        sa.Column("required_item_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "task_package_instances",
        sa.Column("completed_required_item_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "task_package_instances",
        sa.Column("manual_added_item_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "task_package_instances",
        sa.Column("last_manual_added_at", sa.DateTime(timezone=False), nullable=True),
    )
    op.add_column(
        "task_package_instances",
        sa.Column("has_adjustment_notice", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "task_package_instances",
        sa.Column("adjustment_notice", sa.Text(), nullable=True),
    )
    op.add_column(
        "task_package_instances",
        sa.Column("claim_gate_snapshot", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "task_package_instances",
        sa.Column("required_recharge_amount_snapshot", sa.Numeric(18, 2), nullable=True),
    )
    op.add_column(
        "task_package_instances",
        sa.Column("locked_reason", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "task_package_instances",
        sa.Column("pause_reason", sa.String(length=128), nullable=True),
    )
    op.create_index("ix_task_package_instances_batch_id", "task_package_instances", ["batch_id"])
    op.create_index("ix_task_package_instances_quota_id", "task_package_instances", ["quota_id"])
    op.create_index("ix_task_package_instances_batch_day_no", "task_package_instances", ["batch_day_no"])
    op.create_index("ix_task_package_instances_reward_ledger_id", "task_package_instances", ["reward_ledger_id"])
    op.create_index("ix_task_package_instances_visible_item_id", "task_package_instances", ["visible_item_id"])

    op.add_column(
        "task_package_instance_items",
        sa.Column("batch_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "task_package_instance_items",
        sa.Column("quota_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "task_package_instance_items",
        sa.Column("item_origin", sa.String(length=32), nullable=False, server_default="system_generated"),
    )
    op.add_column(
        "task_package_instance_items",
        sa.Column("is_required", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "task_package_instance_items",
        sa.Column("product_pool_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "task_package_instance_items",
        sa.Column("pool_item_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "task_package_instance_items",
        sa.Column("product_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "task_package_instance_items",
        sa.Column("product_name_snapshot", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "task_package_instance_items",
        sa.Column("product_image_url_snapshot", sa.String(length=512), nullable=True),
    )
    op.add_column(
        "task_package_instance_items",
        sa.Column("product_description_snapshot", sa.Text(), nullable=True),
    )
    op.add_column(
        "task_package_instance_items",
        sa.Column("price_snapshot", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
    )
    op.add_column(
        "task_package_instance_items",
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
    )
    op.add_column(
        "task_package_instance_items",
        sa.Column("visible_to_user", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "task_package_instance_items",
        sa.Column("available_at", sa.DateTime(timezone=False), nullable=True),
    )
    op.add_column(
        "task_package_instance_items",
        sa.Column("started_at", sa.DateTime(timezone=False), nullable=True),
    )
    op.add_column(
        "task_package_instance_items",
        sa.Column("debit_ledger_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "task_package_instance_items",
        sa.Column("manual_add_log_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "task_package_instance_items",
        sa.Column("selection_seed", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "task_package_instance_items",
        sa.Column("selection_algorithm", sa.String(length=64), nullable=True),
    )
    op.create_index("ix_task_package_instance_items_batch_id", "task_package_instance_items", ["batch_id"])
    op.create_index("ix_task_package_instance_items_quota_id", "task_package_instance_items", ["quota_id"])
    op.create_index("ix_task_package_instance_items_product_pool_id", "task_package_instance_items", ["product_pool_id"])
    op.create_index("ix_task_package_instance_items_pool_item_id", "task_package_instance_items", ["pool_item_id"])
    op.create_index("ix_task_package_instance_items_product_id", "task_package_instance_items", ["product_id"])
    op.create_index("ix_task_package_instance_items_debit_ledger_id", "task_package_instance_items", ["debit_ledger_id"])
    op.create_index("ix_task_package_instance_items_manual_add_log_id", "task_package_instance_items", ["manual_add_log_id"])

    op.create_table(
        "task_product_generation_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("site_id", sa.String(length=36), nullable=True),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("quota_id", sa.String(length=36), nullable=False),
        sa.Column("batch_id", sa.String(length=36), nullable=True),
        sa.Column("product_pool_id", sa.String(length=36), nullable=False),
        sa.Column("selection_seed", sa.String(length=128), nullable=False),
        sa.Column("selection_algorithm", sa.String(length=64), nullable=False, server_default="weighted_random_unique_v1"),
        sa.Column("target_day_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("actual_day_system_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("tolerance_amount", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
        sa.Column("generated_package_count", sa.Integer(), nullable=False),
        sa.Column("generated_item_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="success"),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.account_id"]),
        sa.ForeignKeyConstraint(["product_pool_id"], ["task_product_pools.id"]),
        sa.ForeignKeyConstraint(["quota_id"], ["member_task_day_quotas.id"]),
        sa.ForeignKeyConstraint(["site_id"], ["h5_sites.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["app_users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index("ix_task_product_generation_runs_account_id", "task_product_generation_runs", ["account_id"])
    op.create_index("ix_task_product_generation_runs_site_id", "task_product_generation_runs", ["site_id"])
    op.create_index("ix_task_product_generation_runs_user_id", "task_product_generation_runs", ["user_id"])
    op.create_index("ix_task_product_generation_runs_quota_id", "task_product_generation_runs", ["quota_id"])
    op.create_index("ix_task_product_generation_runs_batch_id", "task_product_generation_runs", ["batch_id"])
    op.create_index("ix_task_product_generation_runs_product_pool_id", "task_product_generation_runs", ["product_pool_id"])
    op.create_index("ix_task_product_generation_runs_idempotency_key", "task_product_generation_runs", ["idempotency_key"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_task_product_generation_runs_idempotency_key", table_name="task_product_generation_runs")
    op.drop_index("ix_task_product_generation_runs_product_pool_id", table_name="task_product_generation_runs")
    op.drop_index("ix_task_product_generation_runs_batch_id", table_name="task_product_generation_runs")
    op.drop_index("ix_task_product_generation_runs_quota_id", table_name="task_product_generation_runs")
    op.drop_index("ix_task_product_generation_runs_user_id", table_name="task_product_generation_runs")
    op.drop_index("ix_task_product_generation_runs_site_id", table_name="task_product_generation_runs")
    op.drop_index("ix_task_product_generation_runs_account_id", table_name="task_product_generation_runs")
    op.drop_table("task_product_generation_runs")

    op.drop_index("ix_task_package_instance_items_manual_add_log_id", table_name="task_package_instance_items")
    op.drop_index("ix_task_package_instance_items_debit_ledger_id", table_name="task_package_instance_items")
    op.drop_index("ix_task_package_instance_items_product_id", table_name="task_package_instance_items")
    op.drop_index("ix_task_package_instance_items_pool_item_id", table_name="task_package_instance_items")
    op.drop_index("ix_task_package_instance_items_product_pool_id", table_name="task_package_instance_items")
    op.drop_index("ix_task_package_instance_items_quota_id", table_name="task_package_instance_items")
    op.drop_index("ix_task_package_instance_items_batch_id", table_name="task_package_instance_items")
    op.drop_column("task_package_instance_items", "selection_algorithm")
    op.drop_column("task_package_instance_items", "selection_seed")
    op.drop_column("task_package_instance_items", "manual_add_log_id")
    op.drop_column("task_package_instance_items", "debit_ledger_id")
    op.drop_column("task_package_instance_items", "started_at")
    op.drop_column("task_package_instance_items", "available_at")
    op.drop_column("task_package_instance_items", "visible_to_user")
    op.drop_column("task_package_instance_items", "status")
    op.drop_column("task_package_instance_items", "price_snapshot")
    op.drop_column("task_package_instance_items", "product_description_snapshot")
    op.drop_column("task_package_instance_items", "product_image_url_snapshot")
    op.drop_column("task_package_instance_items", "product_name_snapshot")
    op.drop_column("task_package_instance_items", "product_id")
    op.drop_column("task_package_instance_items", "pool_item_id")
    op.drop_column("task_package_instance_items", "product_pool_id")
    op.drop_column("task_package_instance_items", "is_required")
    op.drop_column("task_package_instance_items", "item_origin")
    op.drop_column("task_package_instance_items", "quota_id")
    op.drop_column("task_package_instance_items", "batch_id")

    op.drop_index("ix_task_package_instances_visible_item_id", table_name="task_package_instances")
    op.drop_index("ix_task_package_instances_reward_ledger_id", table_name="task_package_instances")
    op.drop_index("ix_task_package_instances_batch_day_no", table_name="task_package_instances")
    op.drop_index("ix_task_package_instances_quota_id", table_name="task_package_instances")
    op.drop_index("ix_task_package_instances_batch_id", table_name="task_package_instances")
    op.drop_column("task_package_instances", "pause_reason")
    op.drop_column("task_package_instances", "locked_reason")
    op.drop_column("task_package_instances", "required_recharge_amount_snapshot")
    op.drop_column("task_package_instances", "claim_gate_snapshot")
    op.drop_column("task_package_instances", "adjustment_notice")
    op.drop_column("task_package_instances", "has_adjustment_notice")
    op.drop_column("task_package_instances", "last_manual_added_at")
    op.drop_column("task_package_instances", "manual_added_item_count")
    op.drop_column("task_package_instances", "completed_required_item_count")
    op.drop_column("task_package_instances", "required_item_count")
    op.drop_column("task_package_instances", "visible_item_id")
    op.drop_column("task_package_instances", "current_item_index")
    op.drop_column("task_package_instances", "reward_ledger_id")
    op.drop_column("task_package_instances", "reward_amount_final")
    op.drop_column("task_package_instances", "effective_amount")
    op.drop_column("task_package_instances", "manual_added_amount")
    op.drop_column("task_package_instances", "system_generated_amount")
    op.drop_column("task_package_instances", "planned_amount")
    op.drop_column("task_package_instances", "batch_total")
    op.drop_column("task_package_instances", "batch_index")
    op.drop_column("task_package_instances", "batch_day_no")
    op.drop_column("task_package_instances", "quota_id")
    op.drop_column("task_package_instances", "batch_id")

    op.drop_column("task_product_pool_items", "weight")
    op.drop_column("task_product_pool_items", "max_task_price")
    op.drop_column("task_product_pool_items", "min_task_price")
    op.drop_column("task_product_pool_items", "reference_price")
    op.drop_column("task_product_pool_items", "product_description")

    op.drop_index("ix_member_task_batches_product_generation_run_id", table_name="member_task_batches")
    op.drop_column("member_task_batches", "claimed_at")
    op.drop_column("member_task_batches", "product_generation_run_id")
    op.drop_column("member_task_batches", "products_generated")
    op.drop_column("member_task_batches", "reward_ratio_snapshot")
    op.drop_column("member_task_batches", "current_package_index")
    op.drop_column("member_task_batches", "completed_package_count")
