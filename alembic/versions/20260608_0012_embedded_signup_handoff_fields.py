"""expand embedded signup handoff fields

Revision ID: 20260608_0012
Revises: 20260607_0011
Create Date: 2026-06-08 12:40:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260608_0012"
down_revision: str | None = "20260607_0011"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("embedded_signup_sessions") as batch_op:
        batch_op.add_column(sa.Column("provider_name", sa.String(length=32), nullable=False, server_default="mock"))
        batch_op.add_column(
            sa.Column(
                "completion_stage",
                sa.String(length=32),
                nullable=False,
                server_default="pending_callback",
            )
        )
        batch_op.add_column(
            sa.Column("last_event_source", sa.String(length=32), nullable=False, server_default="operator")
        )
        batch_op.add_column(
            sa.Column("remote_confirmed", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.add_column(sa.Column("provider_waba_id", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("provider_business_portfolio_id", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("setup_session_id", sa.String(length=128), nullable=True))
        batch_op.add_column(
            sa.Column("linked_phone_number_ids_json", sa.JSON(), nullable=False, server_default="[]")
        )
        batch_op.add_column(
            sa.Column(
                "authorization_code_present",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch_op.add_column(
            sa.Column(
                "system_user_access_token_present",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch_op.add_column(sa.Column("callback_received_at", sa.DateTime(timezone=False), nullable=True))
        batch_op.add_column(sa.Column("completion_message", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("completion_payload", sa.JSON(), nullable=True))

    with op.batch_alter_table("embedded_signup_sessions") as batch_op:
        batch_op.alter_column("provider_name", server_default=None)
        batch_op.alter_column("completion_stage", server_default=None)
        batch_op.alter_column("last_event_source", server_default=None)
        batch_op.alter_column("remote_confirmed", server_default=None)
        batch_op.alter_column("linked_phone_number_ids_json", server_default=None)
        batch_op.alter_column("authorization_code_present", server_default=None)
        batch_op.alter_column("system_user_access_token_present", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("embedded_signup_sessions") as batch_op:
        batch_op.drop_column("completion_payload")
        batch_op.drop_column("completion_message")
        batch_op.drop_column("callback_received_at")
        batch_op.drop_column("system_user_access_token_present")
        batch_op.drop_column("authorization_code_present")
        batch_op.drop_column("linked_phone_number_ids_json")
        batch_op.drop_column("setup_session_id")
        batch_op.drop_column("provider_business_portfolio_id")
        batch_op.drop_column("provider_waba_id")
        batch_op.drop_column("remote_confirmed")
        batch_op.drop_column("last_event_source")
        batch_op.drop_column("completion_stage")
        batch_op.drop_column("provider_name")
