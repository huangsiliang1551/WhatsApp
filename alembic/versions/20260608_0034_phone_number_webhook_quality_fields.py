"""Add phone number webhook quality payload fields."""

from alembic import op
import sqlalchemy as sa


revision = "20260608_0034"
down_revision = "20260608_0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "whatsapp_phone_numbers",
        sa.Column("quality_event", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "whatsapp_phone_numbers",
        sa.Column("previous_quality_rating", sa.String(length=16), nullable=True),
    )
    op.add_column(
        "whatsapp_phone_numbers",
        sa.Column("messaging_limit_tier", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "whatsapp_phone_numbers",
        sa.Column("max_daily_conversations_per_business", sa.Integer(), nullable=True),
    )
    op.add_column(
        "whatsapp_phone_numbers",
        sa.Column("last_quality_event_at", sa.DateTime(timezone=False), nullable=True),
    )
    op.add_column(
        "whatsapp_phone_numbers",
        sa.Column("last_status_payload", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("whatsapp_phone_numbers", "last_status_payload")
    op.drop_column("whatsapp_phone_numbers", "last_quality_event_at")
    op.drop_column("whatsapp_phone_numbers", "max_daily_conversations_per_business")
    op.drop_column("whatsapp_phone_numbers", "messaging_limit_tier")
    op.drop_column("whatsapp_phone_numbers", "previous_quality_rating")
    op.drop_column("whatsapp_phone_numbers", "quality_event")
