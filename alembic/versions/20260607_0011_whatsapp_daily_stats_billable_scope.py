"""include billable in whatsapp daily stats unique scope

Revision ID: 20260607_0011
Revises: 20260607_0010
Create Date: 2026-06-08 10:15:00
"""

from collections.abc import Sequence

from alembic import op


revision: str = "20260607_0011"
down_revision: str | None = "20260607_0010"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("whatsapp_daily_stats") as batch_op:
        batch_op.drop_constraint("uq_whatsapp_daily_stats_scope", type_="unique")
        batch_op.create_unique_constraint(
            "uq_whatsapp_daily_stats_scope",
            [
                "date",
                "account_id",
                "waba_id",
                "phone_number_id",
                "conversation_origin_type",
                "conversation_category",
                "pricing_model",
                "billable",
                "hour_bucket",
            ],
        )


def downgrade() -> None:
    with op.batch_alter_table("whatsapp_daily_stats") as batch_op:
        batch_op.drop_constraint("uq_whatsapp_daily_stats_scope", type_="unique")
        batch_op.create_unique_constraint(
            "uq_whatsapp_daily_stats_scope",
            [
                "date",
                "account_id",
                "waba_id",
                "phone_number_id",
                "conversation_origin_type",
                "conversation_category",
                "pricing_model",
                "hour_bucket",
            ],
        )
