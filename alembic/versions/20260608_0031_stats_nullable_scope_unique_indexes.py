"""add normalized unique indexes for nullable stats scopes

Revision ID: 20260608_0031
Revises: 20260608_0030
Create Date: 2026-06-08 23:59:30
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260608_0031"
down_revision = "20260608_0030"
branch_labels = None
depends_on = None


INDEX_DEFINITIONS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "ux_template_daily_stats_scope_nulls_not_distinct",
        "template_daily_stats",
        (
            "date",
            "account_id",
            "coalesce(template_id, '__NULL__')",
            "coalesce(waba_id, '__NULL__')",
            "coalesce(phone_number_id, '__NULL__')",
            "template_name",
            "template_language",
        ),
    ),
    (
        "ux_template_hourly_stats_scope_nulls_not_distinct",
        "template_hourly_stats",
        (
            "date",
            "hour_bucket",
            "account_id",
            "coalesce(template_id, '__NULL__')",
            "coalesce(waba_id, '__NULL__')",
            "coalesce(phone_number_id, '__NULL__')",
            "template_name",
            "template_language",
        ),
    ),
    (
        "ux_template_failure_stats_scope_nulls_not_distinct",
        "template_failure_stats",
        (
            "date",
            "account_id",
            "coalesce(template_id, '__NULL__')",
            "coalesce(waba_id, '__NULL__')",
            "coalesce(phone_number_id, '__NULL__')",
            "template_name",
            "template_language",
            "error_code",
        ),
    ),
    (
        "ux_whatsapp_daily_stats_scope_nulls_not_distinct",
        "whatsapp_daily_stats",
        (
            "date",
            "account_id",
            "coalesce(waba_id, '__NULL__')",
            "coalesce(phone_number_id, '__NULL__')",
            "coalesce(conversation_origin_type, '__NULL__')",
            "coalesce(conversation_category, '__NULL__')",
            "coalesce(pricing_model, '__NULL__')",
            "billable",
            "coalesce(hour_bucket, -1)",
        ),
    ),
    (
        "ux_whatsapp_conversation_stats_scope_nulls_not_distinct",
        "whatsapp_conversation_stats",
        (
            "date",
            "account_id",
            "conversation_id",
            "coalesce(waba_id, '__NULL__')",
            "coalesce(phone_number_id, '__NULL__')",
            "coalesce(conversation_origin_type, '__NULL__')",
            "coalesce(conversation_category, '__NULL__')",
            "coalesce(pricing_model, '__NULL__')",
            "billable",
            "coalesce(billable_key, '__NULL__')",
            "coalesce(hour_bucket, -1)",
        ),
    ),
)


def upgrade() -> None:
    for index_name, table_name, expressions in INDEX_DEFINITIONS:
        op.create_index(
            index_name,
            table_name,
            [sa.text(expression) for expression in expressions],
            unique=True,
        )


def downgrade() -> None:
    for index_name, table_name, _expressions in reversed(INDEX_DEFINITIONS):
        op.drop_index(index_name, table_name=table_name)
