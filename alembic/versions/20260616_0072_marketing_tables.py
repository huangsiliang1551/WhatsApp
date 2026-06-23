"""Add marketing: products, packages, tasks, sign-in, invite tables.

Revision ID: 20260616_0072
Revises: 20260613_0071
Create Date: 2026-06-16 10:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260616_0072"
down_revision: str | None = "698b1cc1f0c7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ---- products ----
    op.create_table(
        "products",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("account_id", sa.String(128), sa.ForeignKey("accounts.account_id"), nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("image_asset_id", sa.String(36), sa.ForeignKey("media_assets.id"), nullable=True),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=True),
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
        sa.UniqueConstraint("account_id", "name", name="uq_products_name_account"),
    )

    # ---- product_packages ----
    op.create_table(
        "product_packages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("account_id", sa.String(128), sa.ForeignKey("accounts.account_id"), nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("target_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("amount_tolerance_pct", sa.Integer(), nullable=False, server_default=sa.text("10")),
        sa.Column("product_count", sa.Integer(), nullable=False),
        sa.Column("product_ids", sa.JSON(), nullable=True),
        sa.Column("product_snapshot", sa.JSON(), nullable=True),
        sa.Column("total_value", sa.Numeric(12, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("completion_reward", sa.Numeric(12, 2), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    # ---- task_rules ----
    op.create_table(
        "task_rules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("account_id", sa.String(128), sa.ForeignKey("accounts.account_id"), nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("rule_type", sa.String(32), nullable=False),
        sa.Column("trigger_type", sa.String(32), nullable=False),
        sa.Column("trigger_config", sa.JSON(), nullable=True),
        sa.Column("package_id", sa.String(36), sa.ForeignKey("product_packages.id"), nullable=True),
        sa.Column("follow_up_chain", sa.JSON(), nullable=True),
        sa.Column("expiry_config", sa.JSON(), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
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
    op.create_index("ix_task_rules_trigger_type", "task_rules", ["trigger_type"])

    # ---- mkt_task_instances ----
    op.create_table(
        "mkt_task_instances",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("account_id", sa.String(128), sa.ForeignKey("accounts.account_id"), nullable=False, index=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("app_users.id"), nullable=False, index=True),
        sa.Column("rule_id", sa.String(36), sa.ForeignKey("task_rules.id"), nullable=False, index=True),
        sa.Column("package_id", sa.String(36), sa.ForeignKey("product_packages.id"), nullable=True),
        sa.Column("task_type", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("product_progress", sa.JSON(), nullable=True),
        sa.Column("total_paid", sa.Numeric(12, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("reward_amount", sa.Numeric(12, 2), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("started_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_mkt_task_instances_user_status", "mkt_task_instances", ["user_id", "status"])

    # ---- sign_in_records ----
    op.create_table(
        "sign_in_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("account_id", sa.String(128), sa.ForeignKey("accounts.account_id"), nullable=False, index=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("app_users.id"), nullable=False, index=True),
        sa.Column("sign_date", sa.Date(), nullable=False),
        sa.Column("consecutive_days", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("is_rewarded", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("user_id", "sign_date", name="uq_sign_in_records_user_date"),
    )
    op.create_index("ix_sign_in_records_user_date", "sign_in_records", ["user_id", "sign_date"])

    # ---- invite_records ----
    op.create_table(
        "invite_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("account_id", sa.String(128), sa.ForeignKey("accounts.account_id"), nullable=False, index=True),
        sa.Column("inviter_user_id", sa.String(36), sa.ForeignKey("app_users.id"), nullable=False, index=True),
        sa.Column("invitee_user_id", sa.String(36), sa.ForeignKey("app_users.id"), nullable=False, index=True),
        sa.Column("invite_type", sa.String(32), nullable=False),
        sa.Column("reward_amount", sa.Numeric(12, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("is_rewarded", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_invite_records_inviter", "invite_records", ["inviter_user_id"])
    op.create_index("ix_invite_records_invitee", "invite_records", ["invitee_user_id"])

    # ---- invite_links ----
    op.create_table(
        "invite_links",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("account_id", sa.String(128), sa.ForeignKey("accounts.account_id"), nullable=False, index=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("app_users.id"), nullable=False, unique=True, index=True),
        sa.Column("invite_code", sa.String(32), nullable=False, unique=True, index=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )



def downgrade() -> None:
    op.drop_table("invite_links")
    op.drop_table("invite_records")
    op.drop_table("sign_in_records")
    op.drop_table("mkt_task_instances")
    op.drop_table("task_rules")
    op.drop_table("product_packages")
    op.drop_table("products")
