"""add meta status enum check constraints

Revision ID: 20260610_0054
Revises: 20260610_0053
Create Date: 2026-06-10 15:55:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260610_0054"
down_revision: str | None = "20260610_0053"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


_WABA_WEBHOOK_VERIFICATION_STATUS_CHECK = (
    "webhook_verification_status IN ('pending', 'verified', 'failed', 'unavailable')"
)
_WABA_WEBHOOK_RUNTIME_STATUS_CHECK = (
    "webhook_runtime_status IN ("
    "'pending', 'healthy', 'verification_pending', 'signature_failed', 'payload_invalid'"
    ")"
)
_META_BUSINESS_PORTFOLIO_STATUS_CHECK = "status IN ('active')"
_WEBHOOK_SUBSCRIPTION_STATUS_CHECK = (
    "status IN ('pending', 'mock_subscribed', 'remote_subscribed', 'remote_pending', 'subscribed')"
)
_EMBEDDED_SIGNUP_SESSION_STATUS_CHECK = "status IN ('created', 'completed', 'failed')"
_EMBEDDED_SIGNUP_COMPLETION_STAGE_CHECK = (
    "completion_stage IN ("
    "'pending_callback', 'callback_recorded', 'remote_confirmed', "
    "'local_waba_linked', 'webhook_verification_pending', 'failed'"
    ")"
)
_EMBEDDED_SIGNUP_EVENT_SOURCE_CHECK = (
    "last_event_source IN ('operator', 'provider_callback', 'system_sync')"
)


def upgrade() -> None:
    _assert_allowed_values(
        table_name="meta_business_portfolios",
        column_name="status",
        allowed_values=("active",),
    )
    _assert_allowed_values(
        table_name="whatsapp_business_accounts",
        column_name="webhook_verification_status",
        allowed_values=("pending", "verified", "failed", "unavailable"),
    )
    _assert_allowed_values(
        table_name="whatsapp_business_accounts",
        column_name="webhook_runtime_status",
        allowed_values=("pending", "healthy", "verification_pending", "signature_failed", "payload_invalid"),
    )
    _assert_allowed_values(
        table_name="webhook_subscriptions",
        column_name="status",
        allowed_values=("pending", "mock_subscribed", "remote_subscribed", "remote_pending", "subscribed"),
    )
    _assert_allowed_values(
        table_name="embedded_signup_sessions",
        column_name="status",
        allowed_values=("created", "completed", "failed"),
    )
    _assert_allowed_values(
        table_name="embedded_signup_sessions",
        column_name="completion_stage",
        allowed_values=(
            "pending_callback",
            "callback_recorded",
            "remote_confirmed",
            "local_waba_linked",
            "webhook_verification_pending",
            "failed",
        ),
    )
    _assert_allowed_values(
        table_name="embedded_signup_sessions",
        column_name="last_event_source",
        allowed_values=("operator", "provider_callback", "system_sync"),
    )

    with op.batch_alter_table("meta_business_portfolios") as batch_op:
        batch_op.create_check_constraint(
            "ck_meta_business_portfolios_status",
            _META_BUSINESS_PORTFOLIO_STATUS_CHECK,
        )

    with op.batch_alter_table("whatsapp_business_accounts") as batch_op:
        batch_op.create_check_constraint(
            "ck_whatsapp_business_accounts_webhook_verification_status",
            _WABA_WEBHOOK_VERIFICATION_STATUS_CHECK,
        )
        batch_op.create_check_constraint(
            "ck_whatsapp_business_accounts_webhook_runtime_status",
            _WABA_WEBHOOK_RUNTIME_STATUS_CHECK,
        )

    with op.batch_alter_table("webhook_subscriptions") as batch_op:
        batch_op.create_check_constraint(
            "ck_webhook_subscriptions_status",
            _WEBHOOK_SUBSCRIPTION_STATUS_CHECK,
        )

    with op.batch_alter_table("embedded_signup_sessions") as batch_op:
        batch_op.create_check_constraint(
            "ck_embedded_signup_sessions_status",
            _EMBEDDED_SIGNUP_SESSION_STATUS_CHECK,
        )
        batch_op.create_check_constraint(
            "ck_embedded_signup_sessions_completion_stage",
            _EMBEDDED_SIGNUP_COMPLETION_STAGE_CHECK,
        )
        batch_op.create_check_constraint(
            "ck_embedded_signup_sessions_last_event_source",
            _EMBEDDED_SIGNUP_EVENT_SOURCE_CHECK,
        )


def downgrade() -> None:
    with op.batch_alter_table("embedded_signup_sessions") as batch_op:
        batch_op.drop_constraint("ck_embedded_signup_sessions_last_event_source", type_="check")
        batch_op.drop_constraint("ck_embedded_signup_sessions_completion_stage", type_="check")
        batch_op.drop_constraint("ck_embedded_signup_sessions_status", type_="check")

    with op.batch_alter_table("webhook_subscriptions") as batch_op:
        batch_op.drop_constraint("ck_webhook_subscriptions_status", type_="check")

    with op.batch_alter_table("whatsapp_business_accounts") as batch_op:
        batch_op.drop_constraint("ck_whatsapp_business_accounts_webhook_runtime_status", type_="check")
        batch_op.drop_constraint("ck_whatsapp_business_accounts_webhook_verification_status", type_="check")

    with op.batch_alter_table("meta_business_portfolios") as batch_op:
        batch_op.drop_constraint("ck_meta_business_portfolios_status", type_="check")


def _assert_allowed_values(
    *,
    table_name: str,
    column_name: str,
    allowed_values: tuple[str, ...],
) -> None:
    connection = op.get_bind()
    table = sa.table(
        table_name,
        sa.column(column_name, sa.String(length=32)),
    )
    invalid_rows = connection.execute(
        sa.select(table.c[column_name])
        .where(~table.c[column_name].in_(allowed_values))
        .group_by(table.c[column_name])
    ).all()
    if invalid_rows:
        invalid_values = ", ".join(sorted(str(row[0]) for row in invalid_rows))
        raise RuntimeError(
            f"Cannot add enum constraint on {table_name}.{column_name}; "
            f"unexpected values remain: {invalid_values}."
        )
