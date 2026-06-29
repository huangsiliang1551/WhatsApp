"""add task system v3 phase 1 foundation tables

Revision ID: 20260626_0401
Revises: 20260625_0301
Create Date: 2026-06-26 04:01:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260626_0401"
down_revision = "20260625_0301"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "task_product_pools",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("site_id", sa.String(length=36), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=True),
        sa.Column("pool_type", sa.String(length=32), nullable=False, server_default="general"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("currency", sa.String(length=16), nullable=False, server_default="USD"),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.account_id"]),
        sa.ForeignKeyConstraint(["site_id"], ["h5_sites.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_task_product_pools_account_id", "task_product_pools", ["account_id"])
    op.create_index("ix_task_product_pools_site_id", "task_product_pools", ["site_id"])
    op.create_index("ix_task_product_pools_code", "task_product_pools", ["code"])

    op.create_table(
        "task_issue_plans",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("site_id", sa.String(length=36), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("plan_type", sa.String(length=32), nullable=False, server_default="official"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("claim_gate", sa.String(length=32), nullable=False, server_default="certified_member"),
        sa.Column("issue_anchor", sa.String(length=32), nullable=False, server_default="certified_at"),
        sa.Column("issue_mode", sa.String(length=32), nullable=False, server_default="calendar_day"),
        sa.Column("require_previous_batch_completed", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("max_unfinished_batches", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("after_last_rule_mode", sa.String(length=32), nullable=False, server_default="arithmetic_growth"),
        sa.Column("growth_package_count_step", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("growth_amount_step", sa.Numeric(18, 2), nullable=True),
        sa.Column("default_product_pool_id", sa.String(length=36), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.account_id"]),
        sa.ForeignKeyConstraint(["site_id"], ["h5_sites.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_task_issue_plans_account_id", "task_issue_plans", ["account_id"])
    op.create_index("ix_task_issue_plans_site_id", "task_issue_plans", ["site_id"])
    op.create_index("ix_task_issue_plans_default_product_pool_id", "task_issue_plans", ["default_product_pool_id"])

    op.create_table(
        "task_system_configs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("site_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("whatsapp_binding_reward_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("whatsapp_binding_reward_amount", sa.Numeric(18, 2), nullable=False, server_default="20.00"),
        sa.Column("whatsapp_binding_reward_wallet_type", sa.String(length=32), nullable=False, server_default="task_balance"),
        sa.Column("whatsapp_binding_reward_currency", sa.String(length=16), nullable=False, server_default="USD"),
        sa.Column("certified_member_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("certified_recharge_threshold", sa.Numeric(18, 2), nullable=False, server_default="50.00"),
        sa.Column("certified_recharge_scope", sa.String(length=32), nullable=False, server_default="real_recharge"),
        sa.Column("auto_certify_on_recharge", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("newbie_task_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("newbie_plan_id", sa.String(length=36), nullable=True),
        sa.Column("newbie_auto_popup", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("official_plan_id", sa.String(length=36), nullable=True),
        sa.Column("show_task_balance_transfer_prompt", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("min_task_balance_transfer_prompt_amount", sa.Numeric(18, 2), nullable=False, server_default="0.01"),
        sa.Column("max_active_batches_per_user", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("max_active_packages_per_user", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.account_id"]),
        sa.ForeignKeyConstraint(["site_id"], ["h5_sites.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", "site_id", name="uq_task_system_configs_account_site"),
    )
    op.create_index("ix_task_system_configs_account_id", "task_system_configs", ["account_id"])
    op.create_index("ix_task_system_configs_site_id", "task_system_configs", ["site_id"])
    op.create_index("ix_task_system_configs_newbie_plan_id", "task_system_configs", ["newbie_plan_id"])
    op.create_index("ix_task_system_configs_official_plan_id", "task_system_configs", ["official_plan_id"])

    op.create_table(
        "task_issue_plan_day_rules",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("site_id", sa.String(length=36), nullable=True),
        sa.Column("plan_id", sa.String(length=36), nullable=False),
        sa.Column("day_no", sa.Integer(), nullable=False),
        sa.Column("package_count", sa.Integer(), nullable=False),
        sa.Column("day_total_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("tolerance_amount", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
        sa.Column("amount_allocation_mode", sa.String(length=32), nullable=False, server_default="average"),
        sa.Column("package_amounts_json", sa.JSON(), nullable=False),
        sa.Column("product_pool_id", sa.String(length=36), nullable=True),
        sa.Column("product_count_mode", sa.String(length=32), nullable=False, server_default="range"),
        sa.Column("product_count_fixed", sa.Integer(), nullable=True),
        sa.Column("product_count_min", sa.Integer(), nullable=True),
        sa.Column("product_count_max", sa.Integer(), nullable=True),
        sa.Column("reward_ratio", sa.Numeric(12, 4), nullable=False, server_default="0.10"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.account_id"]),
        sa.ForeignKeyConstraint(["plan_id"], ["task_issue_plans.id"]),
        sa.ForeignKeyConstraint(["product_pool_id"], ["task_product_pools.id"]),
        sa.ForeignKeyConstraint(["site_id"], ["h5_sites.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plan_id", "day_no", name="uq_task_issue_plan_day_rules_plan_day"),
    )
    op.create_index("ix_task_issue_plan_day_rules_account_id", "task_issue_plan_day_rules", ["account_id"])
    op.create_index("ix_task_issue_plan_day_rules_site_id", "task_issue_plan_day_rules", ["site_id"])
    op.create_index("ix_task_issue_plan_day_rules_plan_id", "task_issue_plan_day_rules", ["plan_id"])
    op.create_index("ix_task_issue_plan_day_rules_day_no", "task_issue_plan_day_rules", ["day_no"])
    op.create_index("ix_task_issue_plan_day_rules_product_pool_id", "task_issue_plan_day_rules", ["product_pool_id"])

    op.create_table(
        "member_task_batches",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("site_id", sa.String(length=36), nullable=True),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("quota_id", sa.String(length=36), nullable=True),
        sa.Column("plan_id", sa.String(length=36), nullable=True),
        sa.Column("day_no", sa.Integer(), nullable=False),
        sa.Column("package_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("planned_amount", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
        sa.Column("system_generated_amount", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
        sa.Column("manual_added_amount", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
        sa.Column("effective_day_amount", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("issued_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.account_id"]),
        sa.ForeignKeyConstraint(["plan_id"], ["task_issue_plans.id"]),
        sa.ForeignKeyConstraint(["site_id"], ["h5_sites.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["app_users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_member_task_batches_account_id", "member_task_batches", ["account_id"])
    op.create_index("ix_member_task_batches_site_id", "member_task_batches", ["site_id"])
    op.create_index("ix_member_task_batches_user_id", "member_task_batches", ["user_id"])
    op.create_index("ix_member_task_batches_quota_id", "member_task_batches", ["quota_id"])
    op.create_index("ix_member_task_batches_plan_id", "member_task_batches", ["plan_id"])
    op.create_index("ix_member_task_batches_day_no", "member_task_batches", ["day_no"])

    op.create_table(
        "member_task_day_quotas",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("site_id", sa.String(length=36), nullable=True),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("plan_id", sa.String(length=36), nullable=True),
        sa.Column("day_no", sa.Integer(), nullable=False),
        sa.Column("package_count", sa.Integer(), nullable=False),
        sa.Column("day_total_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("tolerance_amount", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
        sa.Column("amount_allocation_mode", sa.String(length=32), nullable=False, server_default="average"),
        sa.Column("package_amounts_json", sa.JSON(), nullable=False),
        sa.Column("product_pool_id", sa.String(length=36), nullable=False),
        sa.Column("product_count_mode", sa.String(length=32), nullable=False, server_default="range"),
        sa.Column("product_count_fixed", sa.Integer(), nullable=True),
        sa.Column("product_count_min", sa.Integer(), nullable=True),
        sa.Column("product_count_max", sa.Integer(), nullable=True),
        sa.Column("reward_ratio", sa.Numeric(12, 4), nullable=False, server_default="0.10"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("issued_batch_id", sa.String(length=36), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("generated_by", sa.String(length=64), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("created_by", sa.String(length=64), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.account_id"]),
        sa.ForeignKeyConstraint(["issued_batch_id"], ["member_task_batches.id"]),
        sa.ForeignKeyConstraint(["plan_id"], ["task_issue_plans.id"]),
        sa.ForeignKeyConstraint(["product_pool_id"], ["task_product_pools.id"]),
        sa.ForeignKeyConstraint(["site_id"], ["h5_sites.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["app_users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", "user_id", "plan_id", "day_no", name="uq_member_task_day_quotas_scope"),
    )
    op.create_index("ix_member_task_day_quotas_account_id", "member_task_day_quotas", ["account_id"])
    op.create_index("ix_member_task_day_quotas_site_id", "member_task_day_quotas", ["site_id"])
    op.create_index("ix_member_task_day_quotas_user_id", "member_task_day_quotas", ["user_id"])
    op.create_index("ix_member_task_day_quotas_plan_id", "member_task_day_quotas", ["plan_id"])
    op.create_index("ix_member_task_day_quotas_day_no", "member_task_day_quotas", ["day_no"])
    op.create_index("ix_member_task_day_quotas_product_pool_id", "member_task_day_quotas", ["product_pool_id"])
    op.create_index("ix_member_task_day_quotas_issued_batch_id", "member_task_day_quotas", ["issued_batch_id"])
    op.create_index("ix_member_task_day_quotas_created_by", "member_task_day_quotas", ["created_by"])

    op.create_table(
        "task_product_pool_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("pool_id", sa.String(length=36), nullable=False),
        sa.Column("product_id", sa.String(length=64), nullable=False),
        sa.Column("product_name", sa.String(length=255), nullable=False),
        sa.Column("image_url", sa.String(length=1024), nullable=True),
        sa.Column("price", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
        sa.Column("currency", sa.String(length=16), nullable=False, server_default="USD"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.account_id"]),
        sa.ForeignKeyConstraint(["pool_id"], ["task_product_pools.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("pool_id", "product_id", name="uq_task_product_pool_items_pool_product"),
    )
    op.create_index("ix_task_product_pool_items_account_id", "task_product_pool_items", ["account_id"])
    op.create_index("ix_task_product_pool_items_pool_id", "task_product_pool_items", ["pool_id"])
    op.create_index("ix_task_product_pool_items_product_id", "task_product_pool_items", ["product_id"])


def downgrade() -> None:
    op.drop_index("ix_task_product_pool_items_product_id", table_name="task_product_pool_items")
    op.drop_index("ix_task_product_pool_items_pool_id", table_name="task_product_pool_items")
    op.drop_index("ix_task_product_pool_items_account_id", table_name="task_product_pool_items")
    op.drop_table("task_product_pool_items")

    op.drop_index("ix_member_task_day_quotas_created_by", table_name="member_task_day_quotas")
    op.drop_index("ix_member_task_day_quotas_issued_batch_id", table_name="member_task_day_quotas")
    op.drop_index("ix_member_task_day_quotas_product_pool_id", table_name="member_task_day_quotas")
    op.drop_index("ix_member_task_day_quotas_day_no", table_name="member_task_day_quotas")
    op.drop_index("ix_member_task_day_quotas_plan_id", table_name="member_task_day_quotas")
    op.drop_index("ix_member_task_day_quotas_user_id", table_name="member_task_day_quotas")
    op.drop_index("ix_member_task_day_quotas_site_id", table_name="member_task_day_quotas")
    op.drop_index("ix_member_task_day_quotas_account_id", table_name="member_task_day_quotas")
    op.drop_table("member_task_day_quotas")

    op.drop_index("ix_member_task_batches_day_no", table_name="member_task_batches")
    op.drop_index("ix_member_task_batches_plan_id", table_name="member_task_batches")
    op.drop_index("ix_member_task_batches_quota_id", table_name="member_task_batches")
    op.drop_index("ix_member_task_batches_user_id", table_name="member_task_batches")
    op.drop_index("ix_member_task_batches_site_id", table_name="member_task_batches")
    op.drop_index("ix_member_task_batches_account_id", table_name="member_task_batches")
    op.drop_table("member_task_batches")

    op.drop_index("ix_task_issue_plan_day_rules_product_pool_id", table_name="task_issue_plan_day_rules")
    op.drop_index("ix_task_issue_plan_day_rules_day_no", table_name="task_issue_plan_day_rules")
    op.drop_index("ix_task_issue_plan_day_rules_plan_id", table_name="task_issue_plan_day_rules")
    op.drop_index("ix_task_issue_plan_day_rules_site_id", table_name="task_issue_plan_day_rules")
    op.drop_index("ix_task_issue_plan_day_rules_account_id", table_name="task_issue_plan_day_rules")
    op.drop_table("task_issue_plan_day_rules")

    op.drop_index("ix_task_system_configs_official_plan_id", table_name="task_system_configs")
    op.drop_index("ix_task_system_configs_newbie_plan_id", table_name="task_system_configs")
    op.drop_index("ix_task_system_configs_site_id", table_name="task_system_configs")
    op.drop_index("ix_task_system_configs_account_id", table_name="task_system_configs")
    op.drop_table("task_system_configs")

    op.drop_index("ix_task_issue_plans_default_product_pool_id", table_name="task_issue_plans")
    op.drop_index("ix_task_issue_plans_site_id", table_name="task_issue_plans")
    op.drop_index("ix_task_issue_plans_account_id", table_name="task_issue_plans")
    op.drop_table("task_issue_plans")

    op.drop_index("ix_task_product_pools_code", table_name="task_product_pools")
    op.drop_index("ix_task_product_pools_site_id", table_name="task_product_pools")
    op.drop_index("ix_task_product_pools_account_id", table_name="task_product_pools")
    op.drop_table("task_product_pools")
