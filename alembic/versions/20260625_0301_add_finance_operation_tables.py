"""Add finance operation tables for bonus grants and recharge repairs.

Revision ID: 20260625_0301
Revises: 20260625_0300
Create Date: 2026-06-25 03:01:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op


revision: str = "20260625_0301"
down_revision: str | Sequence[str] | None = "20260625_0300"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "wallet_bonus_grant_records",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("grant_no", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=16), nullable=False, server_default="USD"),
        sa.Column("source_type", sa.String(length=64), nullable=False, server_default="admin_bonus"),
        sa.Column("reason", sa.String(length=128), nullable=False),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("operator_id", sa.String(length=64), nullable=False),
        sa.Column("approved_by", sa.String(length=64), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("credited_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("ledger_id", sa.String(length=36), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.account_id"]),
        sa.ForeignKeyConstraint(["user_id"], ["app_users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("grant_no"),
    )
    op.create_index(
        "ix_wallet_bonus_grant_records_account_id",
        "wallet_bonus_grant_records",
        ["account_id"],
        unique=False,
    )
    op.create_index(
        "ix_wallet_bonus_grant_records_grant_no",
        "wallet_bonus_grant_records",
        ["grant_no"],
        unique=False,
    )
    op.create_index(
        "ix_wallet_bonus_grant_records_user_id",
        "wallet_bonus_grant_records",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_wallet_bonus_grant_records_operator_id",
        "wallet_bonus_grant_records",
        ["operator_id"],
        unique=False,
    )
    op.create_index(
        "ix_wallet_bonus_grant_records_approved_by",
        "wallet_bonus_grant_records",
        ["approved_by"],
        unique=False,
    )
    op.create_index(
        "ix_wallet_bonus_grant_records_ledger_id",
        "wallet_bonus_grant_records",
        ["ledger_id"],
        unique=False,
    )

    op.create_table(
        "recharge_repair_orders",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("repair_no", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("channel_id", sa.String(length=36), nullable=True),
        sa.Column("platform_order_no", sa.String(length=128), nullable=True),
        sa.Column("channel_order_no", sa.String(length=128), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=16), nullable=False, server_default="USD"),
        sa.Column("repair_type", sa.String(length=64), nullable=False, server_default="callback_missing"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("reason", sa.String(length=256), nullable=False),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("operator_id", sa.String(length=64), nullable=False),
        sa.Column("approved_by", sa.String(length=64), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("credited_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("recharge_record_id", sa.String(length=36), nullable=True),
        sa.Column("ledger_id", sa.String(length=36), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.account_id"]),
        sa.ForeignKeyConstraint(["user_id"], ["app_users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("repair_no"),
    )
    op.create_index(
        "ix_recharge_repair_orders_account_id",
        "recharge_repair_orders",
        ["account_id"],
        unique=False,
    )
    op.create_index(
        "ix_recharge_repair_orders_repair_no",
        "recharge_repair_orders",
        ["repair_no"],
        unique=False,
    )
    op.create_index(
        "ix_recharge_repair_orders_user_id",
        "recharge_repair_orders",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_recharge_repair_orders_channel_id",
        "recharge_repair_orders",
        ["channel_id"],
        unique=False,
    )
    op.create_index(
        "ix_recharge_repair_orders_platform_order_no",
        "recharge_repair_orders",
        ["platform_order_no"],
        unique=False,
    )
    op.create_index(
        "ix_recharge_repair_orders_channel_order_no",
        "recharge_repair_orders",
        ["channel_order_no"],
        unique=False,
    )
    op.create_index(
        "ix_recharge_repair_orders_operator_id",
        "recharge_repair_orders",
        ["operator_id"],
        unique=False,
    )
    op.create_index(
        "ix_recharge_repair_orders_approved_by",
        "recharge_repair_orders",
        ["approved_by"],
        unique=False,
    )
    op.create_index(
        "ix_recharge_repair_orders_recharge_record_id",
        "recharge_repair_orders",
        ["recharge_record_id"],
        unique=False,
    )
    op.create_index(
        "ix_recharge_repair_orders_ledger_id",
        "recharge_repair_orders",
        ["ledger_id"],
        unique=False,
    )

    with op.batch_alter_table("wallet_bonus_grant_records", schema=None) as batch_op:
        batch_op.alter_column("currency", server_default=None)
        batch_op.alter_column("source_type", server_default=None)
        batch_op.alter_column("status", server_default=None)

    with op.batch_alter_table("recharge_repair_orders", schema=None) as batch_op:
        batch_op.alter_column("currency", server_default=None)
        batch_op.alter_column("repair_type", server_default=None)
        batch_op.alter_column("status", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_recharge_repair_orders_ledger_id", table_name="recharge_repair_orders")
    op.drop_index("ix_recharge_repair_orders_recharge_record_id", table_name="recharge_repair_orders")
    op.drop_index("ix_recharge_repair_orders_approved_by", table_name="recharge_repair_orders")
    op.drop_index("ix_recharge_repair_orders_operator_id", table_name="recharge_repair_orders")
    op.drop_index("ix_recharge_repair_orders_channel_order_no", table_name="recharge_repair_orders")
    op.drop_index("ix_recharge_repair_orders_platform_order_no", table_name="recharge_repair_orders")
    op.drop_index("ix_recharge_repair_orders_channel_id", table_name="recharge_repair_orders")
    op.drop_index("ix_recharge_repair_orders_user_id", table_name="recharge_repair_orders")
    op.drop_index("ix_recharge_repair_orders_repair_no", table_name="recharge_repair_orders")
    op.drop_index("ix_recharge_repair_orders_account_id", table_name="recharge_repair_orders")
    op.drop_table("recharge_repair_orders")

    op.drop_index("ix_wallet_bonus_grant_records_ledger_id", table_name="wallet_bonus_grant_records")
    op.drop_index("ix_wallet_bonus_grant_records_approved_by", table_name="wallet_bonus_grant_records")
    op.drop_index("ix_wallet_bonus_grant_records_operator_id", table_name="wallet_bonus_grant_records")
    op.drop_index("ix_wallet_bonus_grant_records_user_id", table_name="wallet_bonus_grant_records")
    op.drop_index("ix_wallet_bonus_grant_records_grant_no", table_name="wallet_bonus_grant_records")
    op.drop_index("ix_wallet_bonus_grant_records_account_id", table_name="wallet_bonus_grant_records")
    op.drop_table("wallet_bonus_grant_records")
