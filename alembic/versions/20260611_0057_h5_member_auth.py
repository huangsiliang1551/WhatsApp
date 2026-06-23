"""Add H5 member auth profile and session tables.

Revision ID: 20260611_0057
Revises: 20260610_0056
Create Date: 2026-06-11 15:40:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260611_0057"
down_revision: str | None = "20260610_0056"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "member_profiles",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=128), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("member_no", sa.String(length=8), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("password_salt", sa.String(length=64), nullable=False),
        sa.Column("password_updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.account_id"]),
        sa.ForeignKeyConstraint(["user_id"], ["app_users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", "user_id", name="uq_member_profiles_account_user"),
        sa.UniqueConstraint("account_id", "member_no", name="uq_member_profiles_account_member_no"),
    )
    op.create_index("ix_member_profiles_account_id", "member_profiles", ["account_id"], unique=False)
    op.create_index("ix_member_profiles_user_id", "member_profiles", ["user_id"], unique=False)
    op.create_index("ix_member_profiles_member_no", "member_profiles", ["member_no"], unique=False)

    op.create_table(
        "member_auth_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=128), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("member_profile_id", sa.String(length=36), nullable=False),
        sa.Column("session_token_hash", sa.String(length=64), nullable=False),
        sa.Column("refresh_token_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("refresh_expires_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("client_ip", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=1024), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.account_id"]),
        sa.ForeignKeyConstraint(["member_profile_id"], ["member_profiles.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["app_users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_token_hash", name="uq_member_auth_sessions_session_token_hash"),
        sa.UniqueConstraint("refresh_token_hash", name="uq_member_auth_sessions_refresh_token_hash"),
    )
    op.create_index("ix_member_auth_sessions_account_id", "member_auth_sessions", ["account_id"], unique=False)
    op.create_index("ix_member_auth_sessions_user_id", "member_auth_sessions", ["user_id"], unique=False)
    op.create_index(
        "ix_member_auth_sessions_member_profile_id",
        "member_auth_sessions",
        ["member_profile_id"],
        unique=False,
    )
    op.create_index(
        "ix_member_auth_sessions_session_token_hash",
        "member_auth_sessions",
        ["session_token_hash"],
        unique=False,
    )
    op.create_index(
        "ix_member_auth_sessions_refresh_token_hash",
        "member_auth_sessions",
        ["refresh_token_hash"],
        unique=False,
    )

    op.create_table(
        "member_verification_requests",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=128), nullable=False),
        sa.Column("member_profile_id", sa.String(length=36), nullable=False),
        sa.Column("request_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.account_id"]),
        sa.ForeignKeyConstraint(["member_profile_id"], ["member_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_member_verification_requests_account_id",
        "member_verification_requests",
        ["account_id"],
        unique=False,
    )
    op.create_index(
        "ix_member_verification_requests_member_profile_id",
        "member_verification_requests",
        ["member_profile_id"],
        unique=False,
    )

    op.create_table(
        "member_verification_documents",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=128), nullable=False),
        sa.Column("verification_request_id", sa.String(length=36), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=128), nullable=True),
        sa.Column("storage_key", sa.String(length=512), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.account_id"]),
        sa.ForeignKeyConstraint(["verification_request_id"], ["member_verification_requests.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_member_verification_documents_account_id",
        "member_verification_documents",
        ["account_id"],
        unique=False,
    )
    op.create_index(
        "ix_member_verification_documents_verification_request_id",
        "member_verification_documents",
        ["verification_request_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_member_verification_documents_verification_request_id", table_name="member_verification_documents")
    op.drop_index("ix_member_verification_documents_account_id", table_name="member_verification_documents")
    op.drop_table("member_verification_documents")

    op.drop_index("ix_member_verification_requests_member_profile_id", table_name="member_verification_requests")
    op.drop_index("ix_member_verification_requests_account_id", table_name="member_verification_requests")
    op.drop_table("member_verification_requests")

    op.drop_index("ix_member_auth_sessions_refresh_token_hash", table_name="member_auth_sessions")
    op.drop_index("ix_member_auth_sessions_session_token_hash", table_name="member_auth_sessions")
    op.drop_index("ix_member_auth_sessions_member_profile_id", table_name="member_auth_sessions")
    op.drop_index("ix_member_auth_sessions_user_id", table_name="member_auth_sessions")
    op.drop_index("ix_member_auth_sessions_account_id", table_name="member_auth_sessions")
    op.drop_table("member_auth_sessions")

    op.drop_index("ix_member_profiles_member_no", table_name="member_profiles")
    op.drop_index("ix_member_profiles_user_id", table_name="member_profiles")
    op.drop_index("ix_member_profiles_account_id", table_name="member_profiles")
    op.drop_table("member_profiles")
