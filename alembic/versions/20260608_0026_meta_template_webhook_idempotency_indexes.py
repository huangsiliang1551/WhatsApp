"""add meta webhook and template idempotency indexes

Revision ID: 20260608_0026
Revises: 20260608_0025
Create Date: 2026-06-08 23:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260608_0026"
down_revision = "20260608_0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "uq_webhook_subscriptions_waba_callback",
        "webhook_subscriptions",
        ["waba_account_id", "callback_url"],
        unique=True,
    )
    op.create_index(
        "uq_message_templates_account_waba_meta_template_id",
        "message_templates",
        ["account_id", "waba_account_id", "meta_template_id"],
        unique=True,
        sqlite_where=sa.text("waba_account_id IS NOT NULL AND meta_template_id IS NOT NULL"),
        postgresql_where=sa.text("waba_account_id IS NOT NULL AND meta_template_id IS NOT NULL"),
    )
    op.create_index(
        "uq_message_templates_account_waba_name_language",
        "message_templates",
        ["account_id", "waba_account_id", "name", "language"],
        unique=True,
        sqlite_where=sa.text("waba_account_id IS NOT NULL"),
        postgresql_where=sa.text("waba_account_id IS NOT NULL"),
    )
    op.create_index(
        "uq_template_send_logs_account_message_id",
        "template_send_logs",
        ["account_id", "message_id"],
        unique=True,
        sqlite_where=sa.text("message_id IS NOT NULL"),
        postgresql_where=sa.text("message_id IS NOT NULL"),
    )
    op.create_index(
        "uq_template_send_logs_account_idempotency_key",
        "template_send_logs",
        ["account_id", "idempotency_key"],
        unique=True,
        sqlite_where=sa.text("idempotency_key IS NOT NULL"),
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_template_send_logs_account_idempotency_key", table_name="template_send_logs")
    op.drop_index("uq_template_send_logs_account_message_id", table_name="template_send_logs")
    op.drop_index("uq_message_templates_account_waba_name_language", table_name="message_templates")
    op.drop_index("uq_message_templates_account_waba_meta_template_id", table_name="message_templates")
    op.drop_index("uq_webhook_subscriptions_waba_callback", table_name="webhook_subscriptions")
