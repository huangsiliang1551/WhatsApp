"""Align WABA-scoped uniqueness to official snapshot IDs.

Revision ID: 20260609_0045
Revises: 20260609_0044
Create Date: 2026-06-09 05:40:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260609_0045"
down_revision = "20260609_0044"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        WITH ranked AS (
            SELECT
                id,
                ROW_NUMBER() OVER (
                    PARTITION BY account_id, waba_id, meta_template_id
                    ORDER BY updated_at DESC, created_at DESC, id DESC
                ) AS row_number
            FROM message_templates
            WHERE waba_id IS NOT NULL
              AND meta_template_id IS NOT NULL
        )
        DELETE FROM message_templates
        WHERE id IN (
            SELECT id
            FROM ranked
            WHERE row_number > 1
        )
        """
    )
    op.execute(
        """
        WITH ranked AS (
            SELECT
                id,
                ROW_NUMBER() OVER (
                    PARTITION BY account_id, waba_id, name, language
                    ORDER BY updated_at DESC, created_at DESC, id DESC
                ) AS row_number
            FROM message_templates
            WHERE waba_id IS NOT NULL
        )
        DELETE FROM message_templates
        WHERE id IN (
            SELECT id
            FROM ranked
            WHERE row_number > 1
        )
        """
    )
    op.execute(
        """
        WITH ranked AS (
            SELECT
                id,
                ROW_NUMBER() OVER (
                    PARTITION BY account_id, waba_id, callback_url
                    ORDER BY updated_at DESC, created_at DESC, id DESC
                ) AS row_number
            FROM webhook_subscriptions
        )
        DELETE FROM webhook_subscriptions
        WHERE id IN (
            SELECT id
            FROM ranked
            WHERE row_number > 1
        )
        """
    )

    op.drop_index(
        "uq_message_templates_account_waba_meta_template_id",
        table_name="message_templates",
    )
    op.drop_index(
        "uq_message_templates_account_waba_name_language",
        table_name="message_templates",
    )
    op.drop_index(
        "uq_webhook_subscriptions_waba_callback",
        table_name="webhook_subscriptions",
    )

    op.create_index(
        "uq_message_templates_account_waba_meta_template_id",
        "message_templates",
        ["account_id", "waba_id", "meta_template_id"],
        unique=True,
        sqlite_where=sa.text("waba_id IS NOT NULL AND meta_template_id IS NOT NULL"),
        postgresql_where=sa.text("waba_id IS NOT NULL AND meta_template_id IS NOT NULL"),
    )
    op.create_index(
        "uq_message_templates_account_waba_name_language",
        "message_templates",
        ["account_id", "waba_id", "name", "language"],
        unique=True,
        sqlite_where=sa.text("waba_id IS NOT NULL"),
        postgresql_where=sa.text("waba_id IS NOT NULL"),
    )
    op.create_index(
        "uq_webhook_subscriptions_waba_callback",
        "webhook_subscriptions",
        ["account_id", "waba_id", "callback_url"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "uq_message_templates_account_waba_meta_template_id",
        table_name="message_templates",
    )
    op.drop_index(
        "uq_message_templates_account_waba_name_language",
        table_name="message_templates",
    )
    op.drop_index(
        "uq_webhook_subscriptions_waba_callback",
        table_name="webhook_subscriptions",
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
        "uq_webhook_subscriptions_waba_callback",
        "webhook_subscriptions",
        ["waba_account_id", "callback_url"],
        unique=True,
    )
