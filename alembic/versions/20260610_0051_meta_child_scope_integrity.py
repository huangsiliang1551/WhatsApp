"""Harden Meta child scope integrity against parent account scope.

Revision ID: 20260610_0051
Revises: 20260609_0050
Create Date: 2026-06-10 11:20:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260610_0051"
down_revision: str | None = "20260609_0050"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("whatsapp_business_accounts") as batch_op:
        batch_op.create_unique_constraint(
            "uq_whatsapp_business_accounts_id_account",
            ["id", "account_id"],
        )

    with op.batch_alter_table("webhook_subscriptions") as batch_op:
        batch_op.create_unique_constraint(
            "uq_webhook_subscriptions_id_account",
            ["id", "account_id"],
        )
        batch_op.create_foreign_key(
            "fk_webhook_subscriptions_waba_account_scope",
            "whatsapp_business_accounts",
            ["waba_account_id", "account_id"],
            ["id", "account_id"],
        )

    with op.batch_alter_table("whatsapp_phone_numbers") as batch_op:
        batch_op.create_foreign_key(
            "fk_whatsapp_phone_numbers_waba_account_scope",
            "whatsapp_business_accounts",
            ["waba_account_id", "account_id"],
            ["id", "account_id"],
        )

    with op.batch_alter_table("message_templates") as batch_op:
        batch_op.create_foreign_key(
            "fk_message_templates_waba_account_scope",
            "whatsapp_business_accounts",
            ["waba_account_id", "account_id"],
            ["id", "account_id"],
        )

    with op.batch_alter_table("embedded_signup_sessions") as batch_op:
        batch_op.create_foreign_key(
            "fk_embedded_signup_sessions_waba_account_scope",
            "whatsapp_business_accounts",
            ["waba_account_id", "account_id"],
            ["id", "account_id"],
        )
        batch_op.create_foreign_key(
            "fk_embedded_signup_sessions_created_webhook_subscription_scope",
            "webhook_subscriptions",
            ["created_webhook_subscription_id", "account_id"],
            ["id", "account_id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("embedded_signup_sessions") as batch_op:
        batch_op.drop_constraint(
            "fk_embedded_signup_sessions_created_webhook_subscription_scope",
            type_="foreignkey",
        )
        batch_op.drop_constraint(
            "fk_embedded_signup_sessions_waba_account_scope",
            type_="foreignkey",
        )

    with op.batch_alter_table("message_templates") as batch_op:
        batch_op.drop_constraint(
            "fk_message_templates_waba_account_scope",
            type_="foreignkey",
        )

    with op.batch_alter_table("whatsapp_phone_numbers") as batch_op:
        batch_op.drop_constraint(
            "fk_whatsapp_phone_numbers_waba_account_scope",
            type_="foreignkey",
        )

    with op.batch_alter_table("webhook_subscriptions") as batch_op:
        batch_op.drop_constraint(
            "fk_webhook_subscriptions_waba_account_scope",
            type_="foreignkey",
        )
        batch_op.drop_constraint(
            "uq_webhook_subscriptions_id_account",
            type_="unique",
        )

    with op.batch_alter_table("whatsapp_business_accounts") as batch_op:
        batch_op.drop_constraint(
            "uq_whatsapp_business_accounts_id_account",
            type_="unique",
        )
