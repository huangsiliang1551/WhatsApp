"""Add H5 member withdrawal tables.

Revision ID: 20260611_0059
Revises: 20260611_0058
Create Date: 2026-06-11 18:10:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260611_0059"
down_revision: str | None = "20260611_0058"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "withdrawal_requests",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=128), nullable=False),
        sa.Column("wallet_account_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("member_profile_id", sa.String(length=36), nullable=True),
        sa.Column("request_no", sa.String(length=64), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.account_id"]),
        sa.ForeignKeyConstraint(["wallet_account_id"], ["wallet_accounts.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["app_users.id"]),
        sa.ForeignKeyConstraint(["member_profile_id"], ["member_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_withdrawal_requests_account_id", "withdrawal_requests", ["account_id"], unique=False)
    op.create_index(
        "ix_withdrawal_requests_wallet_account_id",
        "withdrawal_requests",
        ["wallet_account_id"],
        unique=False,
    )
    op.create_index("ix_withdrawal_requests_user_id", "withdrawal_requests", ["user_id"], unique=False)
    op.create_index(
        "ix_withdrawal_requests_member_profile_id",
        "withdrawal_requests",
        ["member_profile_id"],
        unique=False,
    )
    op.create_index("ix_withdrawal_requests_request_no", "withdrawal_requests", ["request_no"], unique=True)

    op.create_table(
        "withdrawal_audit_logs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=128), nullable=False),
        sa.Column("withdrawal_request_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("actor_type", sa.String(length=32), nullable=False),
        sa.Column("actor_id", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.account_id"]),
        sa.ForeignKeyConstraint(["withdrawal_request_id"], ["withdrawal_requests.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_withdrawal_audit_logs_account_id", "withdrawal_audit_logs", ["account_id"], unique=False)
    op.create_index(
        "ix_withdrawal_audit_logs_withdrawal_request_id",
        "withdrawal_audit_logs",
        ["withdrawal_request_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_withdrawal_audit_logs_withdrawal_request_id",
        table_name="withdrawal_audit_logs",
    )
    op.drop_index("ix_withdrawal_audit_logs_account_id", table_name="withdrawal_audit_logs")
    op.drop_table("withdrawal_audit_logs")

    op.drop_index("ix_withdrawal_requests_request_no", table_name="withdrawal_requests")
    op.drop_index("ix_withdrawal_requests_member_profile_id", table_name="withdrawal_requests")
    op.drop_index("ix_withdrawal_requests_user_id", table_name="withdrawal_requests")
    op.drop_index("ix_withdrawal_requests_wallet_account_id", table_name="withdrawal_requests")
    op.drop_index("ix_withdrawal_requests_account_id", table_name="withdrawal_requests")
    op.drop_table("withdrawal_requests")
