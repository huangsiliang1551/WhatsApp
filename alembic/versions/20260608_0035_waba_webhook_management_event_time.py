"""Track WABA webhook management event receipt time."""

from alembic import op
import sqlalchemy as sa


revision = "20260608_0035"
down_revision = "20260608_0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "whatsapp_business_accounts",
        sa.Column("webhook_last_management_event_at", sa.DateTime(timezone=False), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("whatsapp_business_accounts", "webhook_last_management_event_at")
