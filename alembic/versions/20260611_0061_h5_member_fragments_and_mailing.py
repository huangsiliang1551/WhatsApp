"""Add H5 member fragment and mailing tables.

Revision ID: 20260611_0061
Revises: 20260611_0060
Create Date: 2026-06-11 21:20:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260611_0061"
down_revision: str | None = "20260611_0060"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "fragment_definitions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=128), nullable=False),
        sa.Column("fragment_key", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("rarity", sa.String(length=32), nullable=False),
        sa.Column("color", sa.String(length=32), nullable=False),
        sa.Column("required_count", sa.Integer(), nullable=False),
        sa.Column("reward_name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.account_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", "fragment_key", name="uq_fragment_definitions_account_key"),
    )
    op.create_index("ix_fragment_definitions_account_id", "fragment_definitions", ["account_id"], unique=False)
    op.create_index("ix_fragment_definitions_fragment_key", "fragment_definitions", ["fragment_key"], unique=False)

    op.create_table(
        "fragment_inventory",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=128), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("member_profile_id", sa.String(length=36), nullable=False),
        sa.Column("fragment_definition_id", sa.String(length=36), nullable=False),
        sa.Column("owned_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.account_id"]),
        sa.ForeignKeyConstraint(["fragment_definition_id"], ["fragment_definitions.id"]),
        sa.ForeignKeyConstraint(["member_profile_id"], ["member_profiles.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["app_users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "account_id",
            "user_id",
            "fragment_definition_id",
            name="uq_fragment_inventory_account_user_definition",
        ),
    )
    op.create_index("ix_fragment_inventory_account_id", "fragment_inventory", ["account_id"], unique=False)
    op.create_index("ix_fragment_inventory_user_id", "fragment_inventory", ["user_id"], unique=False)
    op.create_index(
        "ix_fragment_inventory_member_profile_id",
        "fragment_inventory",
        ["member_profile_id"],
        unique=False,
    )
    op.create_index(
        "ix_fragment_inventory_fragment_definition_id",
        "fragment_inventory",
        ["fragment_definition_id"],
        unique=False,
    )

    op.create_table(
        "fragment_ledger_entries",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=128), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("member_profile_id", sa.String(length=36), nullable=False),
        sa.Column("fragment_definition_id", sa.String(length=36), nullable=False),
        sa.Column("entry_type", sa.String(length=32), nullable=False),
        sa.Column("direction", sa.String(length=16), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_id", sa.String(length=36), nullable=True),
        sa.Column("note", sa.String(length=1024), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.account_id"]),
        sa.ForeignKeyConstraint(["fragment_definition_id"], ["fragment_definitions.id"]),
        sa.ForeignKeyConstraint(["member_profile_id"], ["member_profiles.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["app_users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_fragment_ledger_entries_account_id", "fragment_ledger_entries", ["account_id"], unique=False)
    op.create_index(
        "ix_fragment_ledger_entries_fragment_definition_id",
        "fragment_ledger_entries",
        ["fragment_definition_id"],
        unique=False,
    )
    op.create_index(
        "ix_fragment_ledger_entries_member_profile_id",
        "fragment_ledger_entries",
        ["member_profile_id"],
        unique=False,
    )
    op.create_index("ix_fragment_ledger_entries_user_id", "fragment_ledger_entries", ["user_id"], unique=False)
    op.create_index("ix_fragment_ledger_entries_source_id", "fragment_ledger_entries", ["source_id"], unique=False)

    op.create_table(
        "fragment_drop_logs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=128), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("member_profile_id", sa.String(length=36), nullable=False),
        sa.Column("fragment_definition_id", sa.String(length=36), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("fragment_ledger_entry_id", sa.String(length=36), nullable=True),
        sa.Column("source_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.account_id"]),
        sa.ForeignKeyConstraint(["fragment_definition_id"], ["fragment_definitions.id"]),
        sa.ForeignKeyConstraint(["fragment_ledger_entry_id"], ["fragment_ledger_entries.id"]),
        sa.ForeignKeyConstraint(["member_profile_id"], ["member_profiles.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["app_users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_fragment_drop_logs_account_id", "fragment_drop_logs", ["account_id"], unique=False)
    op.create_index("ix_fragment_drop_logs_user_id", "fragment_drop_logs", ["user_id"], unique=False)
    op.create_index(
        "ix_fragment_drop_logs_member_profile_id",
        "fragment_drop_logs",
        ["member_profile_id"],
        unique=False,
    )
    op.create_index(
        "ix_fragment_drop_logs_fragment_definition_id",
        "fragment_drop_logs",
        ["fragment_definition_id"],
        unique=False,
    )
    op.create_index(
        "ix_fragment_drop_logs_fragment_ledger_entry_id",
        "fragment_drop_logs",
        ["fragment_ledger_entry_id"],
        unique=False,
    )
    op.create_index("ix_fragment_drop_logs_source_id", "fragment_drop_logs", ["source_id"], unique=False)

    op.create_table(
        "fragment_exchange_requests",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=128), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("member_profile_id", sa.String(length=36), nullable=False),
        sa.Column("reward_name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("mailing_request_id", sa.String(length=36), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.account_id"]),
        sa.ForeignKeyConstraint(["member_profile_id"], ["member_profiles.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["app_users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_fragment_exchange_requests_account_id",
        "fragment_exchange_requests",
        ["account_id"],
        unique=False,
    )
    op.create_index(
        "ix_fragment_exchange_requests_user_id",
        "fragment_exchange_requests",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_fragment_exchange_requests_member_profile_id",
        "fragment_exchange_requests",
        ["member_profile_id"],
        unique=False,
    )
    op.create_index(
        "ix_fragment_exchange_requests_mailing_request_id",
        "fragment_exchange_requests",
        ["mailing_request_id"],
        unique=False,
    )

    op.create_table(
        "mailing_requests",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=128), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("member_profile_id", sa.String(length=36), nullable=False),
        sa.Column("fragment_exchange_request_id", sa.String(length=36), nullable=True),
        sa.Column("reward_name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("receiver", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=False),
        sa.Column("country", sa.String(length=128), nullable=False),
        sa.Column("province", sa.String(length=128), nullable=False),
        sa.Column("city", sa.String(length=128), nullable=False),
        sa.Column("address_line", sa.Text(), nullable=False),
        sa.Column("tracking_no", sa.String(length=128), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("packed_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("shipped_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.account_id"]),
        sa.ForeignKeyConstraint(["fragment_exchange_request_id"], ["fragment_exchange_requests.id"]),
        sa.ForeignKeyConstraint(["member_profile_id"], ["member_profiles.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["app_users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mailing_requests_account_id", "mailing_requests", ["account_id"], unique=False)
    op.create_index("ix_mailing_requests_user_id", "mailing_requests", ["user_id"], unique=False)
    op.create_index(
        "ix_mailing_requests_member_profile_id",
        "mailing_requests",
        ["member_profile_id"],
        unique=False,
    )
    op.create_index(
        "ix_mailing_requests_fragment_exchange_request_id",
        "mailing_requests",
        ["fragment_exchange_request_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_mailing_requests_fragment_exchange_request_id", table_name="mailing_requests")
    op.drop_index("ix_mailing_requests_member_profile_id", table_name="mailing_requests")
    op.drop_index("ix_mailing_requests_user_id", table_name="mailing_requests")
    op.drop_index("ix_mailing_requests_account_id", table_name="mailing_requests")
    op.drop_table("mailing_requests")

    op.drop_index(
        "ix_fragment_exchange_requests_mailing_request_id",
        table_name="fragment_exchange_requests",
    )
    op.drop_index(
        "ix_fragment_exchange_requests_member_profile_id",
        table_name="fragment_exchange_requests",
    )
    op.drop_index("ix_fragment_exchange_requests_user_id", table_name="fragment_exchange_requests")
    op.drop_index("ix_fragment_exchange_requests_account_id", table_name="fragment_exchange_requests")
    op.drop_table("fragment_exchange_requests")

    op.drop_index("ix_fragment_drop_logs_source_id", table_name="fragment_drop_logs")
    op.drop_index(
        "ix_fragment_drop_logs_fragment_ledger_entry_id",
        table_name="fragment_drop_logs",
    )
    op.drop_index(
        "ix_fragment_drop_logs_fragment_definition_id",
        table_name="fragment_drop_logs",
    )
    op.drop_index("ix_fragment_drop_logs_member_profile_id", table_name="fragment_drop_logs")
    op.drop_index("ix_fragment_drop_logs_user_id", table_name="fragment_drop_logs")
    op.drop_index("ix_fragment_drop_logs_account_id", table_name="fragment_drop_logs")
    op.drop_table("fragment_drop_logs")

    op.drop_index("ix_fragment_ledger_entries_source_id", table_name="fragment_ledger_entries")
    op.drop_index(
        "ix_fragment_ledger_entries_user_id",
        table_name="fragment_ledger_entries",
    )
    op.drop_index(
        "ix_fragment_ledger_entries_member_profile_id",
        table_name="fragment_ledger_entries",
    )
    op.drop_index(
        "ix_fragment_ledger_entries_fragment_definition_id",
        table_name="fragment_ledger_entries",
    )
    op.drop_index("ix_fragment_ledger_entries_account_id", table_name="fragment_ledger_entries")
    op.drop_table("fragment_ledger_entries")

    op.drop_index(
        "ix_fragment_inventory_fragment_definition_id",
        table_name="fragment_inventory",
    )
    op.drop_index("ix_fragment_inventory_member_profile_id", table_name="fragment_inventory")
    op.drop_index("ix_fragment_inventory_user_id", table_name="fragment_inventory")
    op.drop_index("ix_fragment_inventory_account_id", table_name="fragment_inventory")
    op.drop_table("fragment_inventory")

    op.drop_index("ix_fragment_definitions_fragment_key", table_name="fragment_definitions")
    op.drop_index("ix_fragment_definitions_account_id", table_name="fragment_definitions")
    op.drop_table("fragment_definitions")
