"""Add wallet ledger idempotent reference scope unique constraint.

Revision ID: 20260612_0063
Revises: 20260611_0062
Create Date: 2026-06-12 09:15:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "20260612_0063"
down_revision: str | None = "20260611_0062"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("wallet_ledger_entries", schema=None) as batch_op:
        batch_op.create_unique_constraint(
            "uq_wallet_ledger_entries_reference_scope",
            [
                "account_id",
                "wallet_account_id",
                "user_id",
                "ledger_type",
                "transaction_type",
                "direction",
                "reference_type",
                "reference_id",
            ],
        )


def downgrade() -> None:
    with op.batch_alter_table("wallet_ledger_entries", schema=None) as batch_op:
        batch_op.drop_constraint("uq_wallet_ledger_entries_reference_scope", type_="unique")
