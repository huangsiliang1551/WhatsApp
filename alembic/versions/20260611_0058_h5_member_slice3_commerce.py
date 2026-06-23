"""Add H5 member Slice 3 commerce tables.

Revision ID: 20260611_0058
Revises: 20260611_0057
Create Date: 2026-06-11 17:05:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260611_0058"
down_revision: str | None = "20260611_0057"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "task_package_templates",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("package_type", sa.String(length=32), nullable=False),
        sa.Column("reward_ratio", sa.Numeric(12, 4), nullable=False),
        sa.Column("completion_window_hours", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("promotion_metric", sa.String(length=64), nullable=True),
        sa.Column("promotion_target_value", sa.Integer(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.account_id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_task_package_templates_account_id", "task_package_templates", ["account_id"], unique=False)

    op.create_table(
        "task_package_template_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=128), nullable=False),
        sa.Column("template_id", sa.String(length=36), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("product_name", sa.String(length=255), nullable=False),
        sa.Column("image_url", sa.String(length=1024), nullable=True),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=16), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.account_id"]),
        sa.ForeignKeyConstraint(["template_id"], ["task_package_templates.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("template_id", "sort_order", name="uq_task_package_template_items_order"),
    )
    op.create_index(
        "ix_task_package_template_items_account_id",
        "task_package_template_items",
        ["account_id"],
        unique=False,
    )
    op.create_index(
        "ix_task_package_template_items_template_id",
        "task_package_template_items",
        ["template_id"],
        unique=False,
    )

    op.create_table(
        "task_package_instances",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=128), nullable=False),
        sa.Column("template_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("site_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("reward_ratio_snapshot", sa.Numeric(12, 4), nullable=False),
        sa.Column("dispatched_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("task_balance_awarded_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("completion_window_hours_snapshot", sa.Integer(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.account_id"]),
        sa.ForeignKeyConstraint(["site_id"], ["h5_sites.id"]),
        sa.ForeignKeyConstraint(["template_id"], ["task_package_templates.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["app_users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_task_package_instances_account_id", "task_package_instances", ["account_id"], unique=False)
    op.create_index("ix_task_package_instances_template_id", "task_package_instances", ["template_id"], unique=False)
    op.create_index("ix_task_package_instances_user_id", "task_package_instances", ["user_id"], unique=False)
    op.create_index("ix_task_package_instances_site_id", "task_package_instances", ["site_id"], unique=False)

    op.create_table(
        "wallet_accounts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=128), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("system_balance", sa.Numeric(12, 2), nullable=False),
        sa.Column("task_balance", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=16), nullable=False),
        sa.Column("withdraw_threshold", sa.Numeric(12, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.account_id"]),
        sa.ForeignKeyConstraint(["user_id"], ["app_users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", "user_id", name="uq_wallet_accounts_account_user"),
    )
    op.create_index("ix_wallet_accounts_account_id", "wallet_accounts", ["account_id"], unique=False)
    op.create_index("ix_wallet_accounts_user_id", "wallet_accounts", ["user_id"], unique=False)

    op.create_table(
        "wallet_ledger_entries",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=128), nullable=False),
        sa.Column("wallet_account_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("ledger_type", sa.String(length=32), nullable=False),
        sa.Column("transaction_type", sa.String(length=64), nullable=False),
        sa.Column("direction", sa.String(length=16), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("note", sa.String(length=1024), nullable=True),
        sa.Column("reference_type", sa.String(length=64), nullable=True),
        sa.Column("reference_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.account_id"]),
        sa.ForeignKeyConstraint(["user_id"], ["app_users.id"]),
        sa.ForeignKeyConstraint(["wallet_account_id"], ["wallet_accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_wallet_ledger_entries_account_id", "wallet_ledger_entries", ["account_id"], unique=False)
    op.create_index("ix_wallet_ledger_entries_wallet_account_id", "wallet_ledger_entries", ["wallet_account_id"], unique=False)
    op.create_index("ix_wallet_ledger_entries_user_id", "wallet_ledger_entries", ["user_id"], unique=False)
    op.create_index("ix_wallet_ledger_entries_reference_id", "wallet_ledger_entries", ["reference_id"], unique=False)

    op.create_table(
        "wallet_transfer_requests",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=128), nullable=False),
        sa.Column("wallet_account_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.account_id"]),
        sa.ForeignKeyConstraint(["user_id"], ["app_users.id"]),
        sa.ForeignKeyConstraint(["wallet_account_id"], ["wallet_accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_wallet_transfer_requests_account_id", "wallet_transfer_requests", ["account_id"], unique=False)
    op.create_index("ix_wallet_transfer_requests_wallet_account_id", "wallet_transfer_requests", ["wallet_account_id"], unique=False)
    op.create_index("ix_wallet_transfer_requests_user_id", "wallet_transfer_requests", ["user_id"], unique=False)

    op.create_table(
        "wallet_recharge_orders",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=128), nullable=False),
        sa.Column("wallet_account_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("credited_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.account_id"]),
        sa.ForeignKeyConstraint(["user_id"], ["app_users.id"]),
        sa.ForeignKeyConstraint(["wallet_account_id"], ["wallet_accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_wallet_recharge_orders_account_id", "wallet_recharge_orders", ["account_id"], unique=False)
    op.create_index("ix_wallet_recharge_orders_wallet_account_id", "wallet_recharge_orders", ["wallet_account_id"], unique=False)
    op.create_index("ix_wallet_recharge_orders_user_id", "wallet_recharge_orders", ["user_id"], unique=False)

    op.create_table(
        "member_orders",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=128), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("package_instance_id", sa.String(length=36), nullable=True),
        sa.Column("order_no", sa.String(length=64), nullable=False),
        sa.Column("package_title", sa.String(length=255), nullable=True),
        sa.Column("product_name", sa.String(length=255), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("source_label", sa.String(length=255), nullable=True),
        sa.Column("ordered_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.account_id"]),
        sa.ForeignKeyConstraint(["package_instance_id"], ["task_package_instances.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["app_users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_member_orders_account_id", "member_orders", ["account_id"], unique=False)
    op.create_index("ix_member_orders_user_id", "member_orders", ["user_id"], unique=False)
    op.create_index("ix_member_orders_package_instance_id", "member_orders", ["package_instance_id"], unique=False)
    op.create_index("ix_member_orders_order_no", "member_orders", ["order_no"], unique=True)

    op.create_table(
        "task_package_instance_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=128), nullable=False),
        sa.Column("package_instance_id", sa.String(length=36), nullable=False),
        sa.Column("template_item_id", sa.String(length=36), nullable=False),
        sa.Column("order_id", sa.String(length=36), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("product_name", sa.String(length=255), nullable=False),
        sa.Column("image_url", sa.String(length=1024), nullable=True),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=16), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.account_id"]),
        sa.ForeignKeyConstraint(["order_id"], ["member_orders.id"]),
        sa.ForeignKeyConstraint(["package_instance_id"], ["task_package_instances.id"]),
        sa.ForeignKeyConstraint(["template_item_id"], ["task_package_template_items.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("package_instance_id", "sort_order", name="uq_task_package_instance_items_order"),
    )
    op.create_index("ix_task_package_instance_items_account_id", "task_package_instance_items", ["account_id"], unique=False)
    op.create_index("ix_task_package_instance_items_package_instance_id", "task_package_instance_items", ["package_instance_id"], unique=False)
    op.create_index("ix_task_package_instance_items_template_item_id", "task_package_instance_items", ["template_item_id"], unique=False)
    op.create_index("ix_task_package_instance_items_order_id", "task_package_instance_items", ["order_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_task_package_instance_items_order_id", table_name="task_package_instance_items")
    op.drop_index("ix_task_package_instance_items_template_item_id", table_name="task_package_instance_items")
    op.drop_index("ix_task_package_instance_items_package_instance_id", table_name="task_package_instance_items")
    op.drop_index("ix_task_package_instance_items_account_id", table_name="task_package_instance_items")
    op.drop_table("task_package_instance_items")

    op.drop_index("ix_member_orders_order_no", table_name="member_orders")
    op.drop_index("ix_member_orders_package_instance_id", table_name="member_orders")
    op.drop_index("ix_member_orders_user_id", table_name="member_orders")
    op.drop_index("ix_member_orders_account_id", table_name="member_orders")
    op.drop_table("member_orders")

    op.drop_index("ix_wallet_recharge_orders_user_id", table_name="wallet_recharge_orders")
    op.drop_index("ix_wallet_recharge_orders_wallet_account_id", table_name="wallet_recharge_orders")
    op.drop_index("ix_wallet_recharge_orders_account_id", table_name="wallet_recharge_orders")
    op.drop_table("wallet_recharge_orders")

    op.drop_index("ix_wallet_transfer_requests_user_id", table_name="wallet_transfer_requests")
    op.drop_index("ix_wallet_transfer_requests_wallet_account_id", table_name="wallet_transfer_requests")
    op.drop_index("ix_wallet_transfer_requests_account_id", table_name="wallet_transfer_requests")
    op.drop_table("wallet_transfer_requests")

    op.drop_index("ix_wallet_ledger_entries_reference_id", table_name="wallet_ledger_entries")
    op.drop_index("ix_wallet_ledger_entries_user_id", table_name="wallet_ledger_entries")
    op.drop_index("ix_wallet_ledger_entries_wallet_account_id", table_name="wallet_ledger_entries")
    op.drop_index("ix_wallet_ledger_entries_account_id", table_name="wallet_ledger_entries")
    op.drop_table("wallet_ledger_entries")

    op.drop_index("ix_wallet_accounts_user_id", table_name="wallet_accounts")
    op.drop_index("ix_wallet_accounts_account_id", table_name="wallet_accounts")
    op.drop_table("wallet_accounts")

    op.drop_index("ix_task_package_instances_site_id", table_name="task_package_instances")
    op.drop_index("ix_task_package_instances_user_id", table_name="task_package_instances")
    op.drop_index("ix_task_package_instances_template_id", table_name="task_package_instances")
    op.drop_index("ix_task_package_instances_account_id", table_name="task_package_instances")
    op.drop_table("task_package_instances")

    op.drop_index("ix_task_package_template_items_template_id", table_name="task_package_template_items")
    op.drop_index("ix_task_package_template_items_account_id", table_name="task_package_template_items")
    op.drop_table("task_package_template_items")

    op.drop_index("ix_task_package_templates_account_id", table_name="task_package_templates")
    op.drop_table("task_package_templates")
