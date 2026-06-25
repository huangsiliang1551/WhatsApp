"""Add wallet cash/bonus split columns.

Revision ID: 20260625_0300
Revises: 20260624_0200
Create Date: 2026-06-25 03:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op


revision: str = "20260625_0300"
down_revision: str | Sequence[str] | None = "20260624_0200"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("wallet_accounts", schema=None) as batch_op:
        batch_op.add_column(sa.Column("frozen_balance", sa.Numeric(12, 2), nullable=False, server_default="0"))
        batch_op.add_column(
            sa.Column("system_cash_balance", sa.Numeric(12, 2), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column("system_bonus_balance", sa.Numeric(12, 2), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column("system_cash_frozen", sa.Numeric(12, 2), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column("system_bonus_frozen", sa.Numeric(12, 2), nullable=False, server_default="0")
        )

    with op.batch_alter_table("wallet_ledger_entries", schema=None) as batch_op:
        batch_op.add_column(sa.Column("source_type", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("fund_type", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("cash_amount", sa.Numeric(12, 2), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("bonus_amount", sa.Numeric(12, 2), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("task_amount", sa.Numeric(12, 2), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("balance_before", sa.Numeric(12, 2), nullable=True))
        batch_op.add_column(sa.Column("balance_after", sa.Numeric(12, 2), nullable=True))
        batch_op.add_column(sa.Column("cash_balance_before", sa.Numeric(12, 2), nullable=True))
        batch_op.add_column(sa.Column("cash_balance_after", sa.Numeric(12, 2), nullable=True))
        batch_op.add_column(sa.Column("bonus_balance_before", sa.Numeric(12, 2), nullable=True))
        batch_op.add_column(sa.Column("bonus_balance_after", sa.Numeric(12, 2), nullable=True))
        batch_op.add_column(sa.Column("task_balance_before", sa.Numeric(12, 2), nullable=True))
        batch_op.add_column(sa.Column("task_balance_after", sa.Numeric(12, 2), nullable=True))
        batch_op.add_column(sa.Column("operator_id", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("operator_type", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("idempotency_key", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("display_category", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("display_title", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("is_bonus", sa.Boolean(), nullable=False, server_default=sa.text("false")))
        batch_op.add_column(sa.Column("is_real_recharge", sa.Boolean(), nullable=False, server_default=sa.text("false")))
        batch_op.add_column(sa.Column("metadata_json", sa.JSON(), nullable=True))

    op.create_index("ix_wallet_ledger_entries_source_type", "wallet_ledger_entries", ["source_type"], unique=False)
    op.create_index("ix_wallet_ledger_entries_fund_type", "wallet_ledger_entries", ["fund_type"], unique=False)
    op.create_index("ix_wallet_ledger_entries_operator_id", "wallet_ledger_entries", ["operator_id"], unique=False)
    op.create_index(
        "ix_wallet_ledger_entries_idempotency_key",
        "wallet_ledger_entries",
        ["idempotency_key"],
        unique=False,
    )

    with op.batch_alter_table("withdrawal_requests", schema=None) as batch_op:
        batch_op.add_column(sa.Column("cash_amount", sa.Numeric(12, 2), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("bonus_amount", sa.Numeric(12, 2), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("actual_payout_amount", sa.Numeric(12, 2), nullable=True))
        batch_op.add_column(sa.Column("withdraw_account_type", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("bank_name", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("account_no_masked", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("account_fingerprint", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("account_snapshot_json", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("duplicate_account_count", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("risk_level", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("risk_flags", sa.JSON(), nullable=True))

    op.create_index(
        "ix_withdrawal_requests_account_fingerprint",
        "withdrawal_requests",
        ["account_fingerprint"],
        unique=False,
    )

    op.execute(
        sa.text(
            """
            UPDATE wallet_accounts
            SET system_cash_balance = system_balance
            WHERE system_cash_balance = 0
              AND system_bonus_balance = 0
              AND system_balance > 0
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE wallet_accounts
            SET system_cash_frozen = frozen_balance
            WHERE system_cash_frozen = 0
              AND system_bonus_frozen = 0
              AND frozen_balance > 0
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE withdrawal_requests
            SET cash_amount = amount
            WHERE cash_amount = 0
              AND bonus_amount = 0
              AND amount > 0
            """
        )
    )

    with op.batch_alter_table("wallet_accounts", schema=None) as batch_op:
        batch_op.alter_column("frozen_balance", server_default=None)
        batch_op.alter_column("system_cash_balance", server_default=None)
        batch_op.alter_column("system_bonus_balance", server_default=None)
        batch_op.alter_column("system_cash_frozen", server_default=None)
        batch_op.alter_column("system_bonus_frozen", server_default=None)

    with op.batch_alter_table("wallet_ledger_entries", schema=None) as batch_op:
        batch_op.alter_column("cash_amount", server_default=None)
        batch_op.alter_column("bonus_amount", server_default=None)
        batch_op.alter_column("task_amount", server_default=None)
        batch_op.alter_column("is_bonus", server_default=None)
        batch_op.alter_column("is_real_recharge", server_default=None)

    with op.batch_alter_table("withdrawal_requests", schema=None) as batch_op:
        batch_op.alter_column("cash_amount", server_default=None)
        batch_op.alter_column("bonus_amount", server_default=None)
        batch_op.alter_column("duplicate_account_count", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_withdrawal_requests_account_fingerprint", table_name="withdrawal_requests")

    with op.batch_alter_table("withdrawal_requests", schema=None) as batch_op:
        batch_op.drop_column("risk_flags")
        batch_op.drop_column("risk_level")
        batch_op.drop_column("duplicate_account_count")
        batch_op.drop_column("account_snapshot_json")
        batch_op.drop_column("account_fingerprint")
        batch_op.drop_column("account_no_masked")
        batch_op.drop_column("bank_name")
        batch_op.drop_column("withdraw_account_type")
        batch_op.drop_column("actual_payout_amount")
        batch_op.drop_column("bonus_amount")
        batch_op.drop_column("cash_amount")

    op.drop_index("ix_wallet_ledger_entries_idempotency_key", table_name="wallet_ledger_entries")
    op.drop_index("ix_wallet_ledger_entries_operator_id", table_name="wallet_ledger_entries")
    op.drop_index("ix_wallet_ledger_entries_fund_type", table_name="wallet_ledger_entries")
    op.drop_index("ix_wallet_ledger_entries_source_type", table_name="wallet_ledger_entries")

    with op.batch_alter_table("wallet_ledger_entries", schema=None) as batch_op:
        batch_op.drop_column("metadata_json")
        batch_op.drop_column("is_real_recharge")
        batch_op.drop_column("is_bonus")
        batch_op.drop_column("display_title")
        batch_op.drop_column("display_category")
        batch_op.drop_column("idempotency_key")
        batch_op.drop_column("operator_type")
        batch_op.drop_column("operator_id")
        batch_op.drop_column("task_balance_after")
        batch_op.drop_column("task_balance_before")
        batch_op.drop_column("bonus_balance_after")
        batch_op.drop_column("bonus_balance_before")
        batch_op.drop_column("cash_balance_after")
        batch_op.drop_column("cash_balance_before")
        batch_op.drop_column("balance_after")
        batch_op.drop_column("balance_before")
        batch_op.drop_column("task_amount")
        batch_op.drop_column("bonus_amount")
        batch_op.drop_column("cash_amount")
        batch_op.drop_column("fund_type")
        batch_op.drop_column("source_type")

    with op.batch_alter_table("wallet_accounts", schema=None) as batch_op:
        batch_op.drop_column("system_bonus_frozen")
        batch_op.drop_column("system_cash_frozen")
        batch_op.drop_column("system_bonus_balance")
        batch_op.drop_column("system_cash_balance")
        batch_op.drop_column("frozen_balance")
