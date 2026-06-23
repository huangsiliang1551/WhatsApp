"""Add H5 member promotion task skeleton tables.

Revision ID: 20260611_0062
Revises: 20260611_0061
Create Date: 2026-06-11 23:40:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260611_0062"
down_revision: str | None = "20260611_0061"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "promotion_task_templates",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=128), nullable=False),
        sa.Column("task_package_template_id", sa.String(length=36), nullable=False),
        sa.Column("metric", sa.String(length=64), nullable=False),
        sa.Column("target_value", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.account_id"]),
        sa.ForeignKeyConstraint(["task_package_template_id"], ["task_package_templates.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "task_package_template_id",
            name="uq_promotion_task_templates_task_package_template_id",
        ),
    )
    op.create_index(
        "ix_promotion_task_templates_account_id",
        "promotion_task_templates",
        ["account_id"],
        unique=False,
    )
    op.create_index(
        "ix_promotion_task_templates_task_package_template_id",
        "promotion_task_templates",
        ["task_package_template_id"],
        unique=False,
    )

    op.create_table(
        "promotion_task_instances",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=128), nullable=False),
        sa.Column("promotion_task_template_id", sa.String(length=36), nullable=False),
        sa.Column("task_package_instance_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("member_profile_id", sa.String(length=36), nullable=False),
        sa.Column("metric", sa.String(length=64), nullable=False),
        sa.Column("target_value", sa.Integer(), nullable=False),
        sa.Column("invite_code_snapshot", sa.String(length=64), nullable=True),
        sa.Column("current_value", sa.Integer(), nullable=False),
        sa.Column("achieved_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("rewarded_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.account_id"]),
        sa.ForeignKeyConstraint(["member_profile_id"], ["member_profiles.id"]),
        sa.ForeignKeyConstraint(["promotion_task_template_id"], ["promotion_task_templates.id"]),
        sa.ForeignKeyConstraint(["task_package_instance_id"], ["task_package_instances.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["app_users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "task_package_instance_id",
            name="uq_promotion_task_instances_task_package_instance_id",
        ),
    )
    op.create_index(
        "ix_promotion_task_instances_account_id",
        "promotion_task_instances",
        ["account_id"],
        unique=False,
    )
    op.create_index(
        "ix_promotion_task_instances_promotion_task_template_id",
        "promotion_task_instances",
        ["promotion_task_template_id"],
        unique=False,
    )
    op.create_index(
        "ix_promotion_task_instances_task_package_instance_id",
        "promotion_task_instances",
        ["task_package_instance_id"],
        unique=False,
    )
    op.create_index(
        "ix_promotion_task_instances_user_id",
        "promotion_task_instances",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_promotion_task_instances_member_profile_id",
        "promotion_task_instances",
        ["member_profile_id"],
        unique=False,
    )
    op.create_index(
        "ix_promotion_task_instances_invite_code_snapshot",
        "promotion_task_instances",
        ["invite_code_snapshot"],
        unique=False,
    )

    op.create_table(
        "user_referrals",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=128), nullable=False),
        sa.Column("site_id", sa.String(length=36), nullable=True),
        sa.Column("invite_code", sa.String(length=64), nullable=False),
        sa.Column("referrer_user_id", sa.String(length=36), nullable=False),
        sa.Column("referred_user_id", sa.String(length=36), nullable=False),
        sa.Column("referred_member_profile_id", sa.String(length=36), nullable=True),
        sa.Column("registered_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("first_recharged_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("first_recharge_order_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.account_id"]),
        sa.ForeignKeyConstraint(["referred_member_profile_id"], ["member_profiles.id"]),
        sa.ForeignKeyConstraint(["referred_user_id"], ["app_users.id"]),
        sa.ForeignKeyConstraint(["referrer_user_id"], ["app_users.id"]),
        sa.ForeignKeyConstraint(["site_id"], ["h5_sites.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "account_id",
            "referrer_user_id",
            "referred_user_id",
            name="uq_user_referrals_account_referrer_referred",
        ),
    )
    op.create_index("ix_user_referrals_account_id", "user_referrals", ["account_id"], unique=False)
    op.create_index("ix_user_referrals_site_id", "user_referrals", ["site_id"], unique=False)
    op.create_index("ix_user_referrals_invite_code", "user_referrals", ["invite_code"], unique=False)
    op.create_index("ix_user_referrals_referrer_user_id", "user_referrals", ["referrer_user_id"], unique=False)
    op.create_index("ix_user_referrals_referred_user_id", "user_referrals", ["referred_user_id"], unique=False)
    op.create_index(
        "ix_user_referrals_referred_member_profile_id",
        "user_referrals",
        ["referred_member_profile_id"],
        unique=False,
    )
    op.create_index(
        "ix_user_referrals_first_recharge_order_id",
        "user_referrals",
        ["first_recharge_order_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_user_referrals_first_recharge_order_id", table_name="user_referrals")
    op.drop_index("ix_user_referrals_referred_member_profile_id", table_name="user_referrals")
    op.drop_index("ix_user_referrals_referred_user_id", table_name="user_referrals")
    op.drop_index("ix_user_referrals_referrer_user_id", table_name="user_referrals")
    op.drop_index("ix_user_referrals_invite_code", table_name="user_referrals")
    op.drop_index("ix_user_referrals_site_id", table_name="user_referrals")
    op.drop_index("ix_user_referrals_account_id", table_name="user_referrals")
    op.drop_table("user_referrals")

    op.drop_index(
        "ix_promotion_task_instances_invite_code_snapshot",
        table_name="promotion_task_instances",
    )
    op.drop_index(
        "ix_promotion_task_instances_member_profile_id",
        table_name="promotion_task_instances",
    )
    op.drop_index("ix_promotion_task_instances_user_id", table_name="promotion_task_instances")
    op.drop_index(
        "ix_promotion_task_instances_task_package_instance_id",
        table_name="promotion_task_instances",
    )
    op.drop_index(
        "ix_promotion_task_instances_promotion_task_template_id",
        table_name="promotion_task_instances",
    )
    op.drop_index("ix_promotion_task_instances_account_id", table_name="promotion_task_instances")
    op.drop_table("promotion_task_instances")

    op.drop_index(
        "ix_promotion_task_templates_task_package_template_id",
        table_name="promotion_task_templates",
    )
    op.drop_index("ix_promotion_task_templates_account_id", table_name="promotion_task_templates")
    op.drop_table("promotion_task_templates")
